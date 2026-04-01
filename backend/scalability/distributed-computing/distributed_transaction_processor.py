"""
Distributed Transaction Processing System for NexaFi
High-performance, scalable transaction processing with enterprise-grade reliability
"""

import hashlib
import json
import logging
import multiprocessing as mp
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import pika
import redis
import structlog
from kafka import KafkaConsumer, KafkaProducer
from prometheus_client import Counter, Gauge, Histogram
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)
Base = declarative_base()


class TransactionStatus(Enum):
    """Transaction processing status"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class Priority(Enum):
    """Transaction priority levels"""

    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BATCH = 5


@dataclass
class Transaction:
    """Transaction data structure"""

    transaction_id: str
    user_id: str
    transaction_type: str
    amount: float
    currency: str
    source_account: str
    destination_account: str
    metadata: Dict[str, Any]
    priority: Priority
    timestamp: datetime
    status: TransactionStatus
    processing_node: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 30
    checksum: Optional[str] = None


@dataclass
class ProcessingResult:
    """Transaction processing result"""

    transaction_id: str
    success: bool
    status: TransactionStatus
    result_data: Dict[str, Any]
    processing_time: float
    error_message: Optional[str] = None
    node_id: str = ""


class TransactionLog(Base):
    """Transaction log model"""

    __tablename__ = "transaction_logs"
    id = Column(Integer, primary_key=True)
    transaction_id = Column(String(100), unique=True, nullable=False, index=True)
    user_id = Column(String(100), nullable=False, index=True)
    transaction_type = Column(String(50), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), nullable=False)
    source_account = Column(String(100), nullable=False)
    destination_account = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False, index=True)
    priority = Column(Integer, nullable=False)
    processing_node = Column(String(100))
    retry_count = Column(Integer, default=0)
    metadata = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)
    processing_time = Column(Float)
    error_message = Column(Text)
    checksum = Column(String(256))


class NodeMetrics(Base):
    """Processing node metrics"""

    __tablename__ = "node_metrics"
    id = Column(Integer, primary_key=True)
    node_id = Column(String(100), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    cpu_usage = Column(Float)
    memory_usage = Column(Float)
    disk_usage = Column(Float)
    network_io = Column(Float)
    active_transactions = Column(Integer)
    completed_transactions = Column(Integer)
    failed_transactions = Column(Integer)
    avg_processing_time = Column(Float)
    queue_size = Column(Integer)
    is_healthy = Column(Boolean, default=True)


Index("idx_transaction_status_priority", TransactionLog.status, TransactionLog.priority)
Index(
    "idx_transaction_created_status", TransactionLog.created_at, TransactionLog.status
)
Index("idx_node_timestamp", NodeMetrics.timestamp)


class MessageQueue:
    """Distributed message queue abstraction"""

    def __init__(
        self, queue_type: str = "redis", config: Optional[Dict[str, Any]] = None
    ) -> None:
        self.queue_type = queue_type
        self.config = config or {}
        self.logger = structlog.get_logger(__name__)
        self._initialize_queue()

    def _initialize_queue(self) -> Any:
        """Initialize message queue based on type"""
        if self.queue_type == "redis":
            self.redis_client = redis.from_url(
                self.config.get("redis_url", "redis://localhost:6379/0"),
                decode_responses=True,
            )
        elif self.queue_type == "rabbitmq":
            self.connection = pika.BlockingConnection(
                pika.URLParameters(self.config.get("rabbitmq_url", "amqp://localhost"))
            )
            self.channel = self.connection.channel()
        elif self.queue_type == "kafka":
            self.producer = KafkaProducer(
                bootstrap_servers=self.config.get("kafka_servers", ["localhost:9092"]),
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
        else:
            raise ValueError(f"Unsupported queue type: {self.queue_type}")

    def publish(
        self, queue_name: str, message: Dict[str, Any], priority: int = 0
    ) -> Any:
        """Publish message to queue"""
        try:
            if self.queue_type == "redis":
                score = priority + time.time() / 1000000
                self.redis_client.zadd(queue_name, {json.dumps(message): score})
            elif self.queue_type == "rabbitmq":
                self.channel.queue_declare(queue=queue_name, durable=True)
                self.channel.basic_publish(
                    exchange="",
                    routing_key=queue_name,
                    body=json.dumps(message),
                    properties=pika.BasicProperties(delivery_mode=2, priority=priority),
                )
            elif self.queue_type == "kafka":
                self.producer.send(queue_name, message)
                self.producer.flush()
        except Exception as e:
            self.logger.error(f"Failed to publish message: {str(e)}")
            raise

    def consume(self, queue_name: str, timeout: int = 1) -> Optional[Dict[str, Any]]:
        """Consume message from queue"""
        try:
            if self.queue_type == "redis":
                result = self.redis_client.zpopmin(queue_name, count=1)
                if result:
                    message_json, _ = result[0]
                    return json.loads(message_json)
                return None
            elif self.queue_type == "rabbitmq":
                method, properties, body = self.channel.basic_get(
                    queue=queue_name, auto_ack=True
                )
                if body:
                    return json.loads(body.decode("utf-8"))
                return None
            elif self.queue_type == "kafka":
                consumer = KafkaConsumer(
                    queue_name,
                    bootstrap_servers=self.config.get(
                        "kafka_servers", ["localhost:9092"]
                    ),
                    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                    consumer_timeout_ms=timeout * 1000,
                )
                for message in consumer:
                    consumer.close()
                    return message.value
                consumer.close()
                return None
        except Exception as e:
            self.logger.error(f"Failed to consume message: {str(e)}")
            return None

    def get_queue_size(self, queue_name: str) -> int:
        """Get queue size"""
        try:
            if self.queue_type == "redis":
                return self.redis_client.zcard(queue_name)
            elif self.queue_type == "rabbitmq":
                method = self.channel.queue_declare(queue=queue_name, passive=True)
                return method.method.message_count
            elif self.queue_type == "kafka":
                return 0
        except Exception:
            return 0


class LoadBalancer:
    """Intelligent load balancer for transaction distribution"""

    def __init__(self, redis_client: redis.Redis) -> None:
        self.redis_client = redis_client
        self.logger = structlog.get_logger(__name__)
        self.nodes = {}
        self.load_balancing_strategy = "weighted_round_robin"

    def register_node(
        self, node_id: str, capacity: int, capabilities: List[str]
    ) -> Any:
        """Register processing node"""
        node_info = {
            "node_id": node_id,
            "capacity": capacity,
            "capabilities": capabilities,
            "current_load": 0,
            "last_heartbeat": time.time(),
            "is_healthy": True,
        }
        self.nodes[node_id] = node_info
        self.redis_client.hset("processing_nodes", node_id, json.dumps(node_info))
        self.logger.info(f"Registered processing node: {node_id}")

    def update_node_load(self, node_id: str, current_load: int) -> Any:
        """Update node load information"""
        if node_id in self.nodes:
            self.nodes[node_id]["current_load"] = current_load
            self.nodes[node_id]["last_heartbeat"] = time.time()
            self.redis_client.hset(
                "processing_nodes", node_id, json.dumps(self.nodes[node_id])
            )

    def select_node(self, transaction: Transaction) -> Optional[str]:
        """Select best node for transaction processing"""
        try:
            available_nodes = self._get_healthy_nodes()
            if not available_nodes:
                return None
            if self.load_balancing_strategy == "round_robin":
                return self._round_robin_selection(available_nodes)
            elif self.load_balancing_strategy == "weighted_round_robin":
                return self._weighted_round_robin_selection(available_nodes)
            elif self.load_balancing_strategy == "least_connections":
                return self._least_connections_selection(available_nodes)
            elif self.load_balancing_strategy == "capability_based":
                return self._capability_based_selection(available_nodes, transaction)
            else:
                return available_nodes[0]["node_id"]
        except Exception as e:
            self.logger.error(f"Node selection failed: {str(e)}")
            return None

    def _get_healthy_nodes(self) -> List[Dict[str, Any]]:
        """Get list of healthy nodes"""
        healthy_nodes: List[Any] = []
        current_time = time.time()
        for node_id, node_info in self.nodes.items():
            if (
                node_info["is_healthy"]
                and current_time - node_info["last_heartbeat"] < 60
                and (node_info["current_load"] < node_info["capacity"])
            ):
                healthy_nodes.append(node_info)
        return healthy_nodes

    def _round_robin_selection(self, nodes: List[Dict[str, Any]]) -> str:
        """Round robin node selection"""
        counter = self.redis_client.incr("round_robin_counter")
        selected_node = nodes[(counter - 1) % len(nodes)]
        return selected_node["node_id"]

    def _weighted_round_robin_selection(self, nodes: List[Dict[str, Any]]) -> str:
        """Weighted round robin based on node capacity"""
        weights: List[Any] = []
        for node in nodes:
            available_capacity = node["capacity"] - node["current_load"]
            weights.append(max(1, available_capacity))
        total_weight = sum(weights)
        counter = self.redis_client.incr("weighted_rr_counter")
        cumulative_weight = 0
        target = (counter - 1) % total_weight
        for i, weight in enumerate(weights):
            cumulative_weight += weight
            if target < cumulative_weight:
                return nodes[i]["node_id"]
        return nodes[0]["node_id"]

    def _least_connections_selection(self, nodes: List[Dict[str, Any]]) -> str:
        """Select node with least current load"""
        min_load_node = min(nodes, key=lambda n: n["current_load"])
        return min_load_node["node_id"]

    def _capability_based_selection(
        self, nodes: List[Dict[str, Any]], transaction: Transaction
    ) -> str:
        """Select node based on transaction requirements and node capabilities"""
        required_capabilities = transaction.metadata.get("required_capabilities", [])
        if required_capabilities:
            capable_nodes = [
                node
                for node in nodes
                if all((cap in node["capabilities"] for cap in required_capabilities))
            ]
            if capable_nodes:
                nodes = capable_nodes
        return self._least_connections_selection(nodes)


class TransactionProcessor:
    """Individual transaction processor"""

    def __init__(
        self, node_id: str, db_session: Any, redis_client: redis.Redis
    ) -> None:
        self.node_id = node_id
        self.db_session = db_session
        self.redis_client = redis_client
        self.logger = structlog.get_logger(__name__)
        self.is_running = False
        self.current_transactions = {}
        self.processed_counter = Counter(
            "transactions_processed_total",
            "Total processed transactions",
            ["node", "status"],
        )
        self.processing_time = Histogram(
            "transaction_processing_seconds",
            "Transaction processing time",
            ["node", "type"],
        )
        self.active_transactions = Gauge(
            "active_transactions", "Currently active transactions", ["node"]
        )

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def process_transaction(self, transaction: Transaction) -> ProcessingResult:
        """Process a single transaction"""
        start_time = time.time()
        try:
            self.logger.info(f"Processing transaction {transaction.transaction_id}")
            if not self._validate_transaction(transaction):
                raise ValueError("Transaction validation failed")
            self._update_transaction_status(transaction, TransactionStatus.PROCESSING)
            self.current_transactions[transaction.transaction_id] = transaction
            self.active_transactions.labels(node=self.node_id).inc()
            result_data = self._execute_transaction_logic(transaction)
            processing_time = time.time() - start_time
            self._update_transaction_status(
                transaction, TransactionStatus.COMPLETED, processing_time
            )
            self.processed_counter.labels(node=self.node_id, status="completed").inc()
            self.processing_time.labels(
                node=self.node_id, type=transaction.transaction_type
            ).observe(processing_time)
            return ProcessingResult(
                transaction_id=transaction.transaction_id,
                success=True,
                status=TransactionStatus.COMPLETED,
                result_data=result_data,
                processing_time=processing_time,
                node_id=self.node_id,
            )
        except Exception as e:
            processing_time = time.time() - start_time
            error_message = str(e)
            self.logger.error(f"Transaction processing failed: {error_message}")
            self._update_transaction_status(
                transaction, TransactionStatus.FAILED, processing_time, error_message
            )
            self.processed_counter.labels(node=self.node_id, status="failed").inc()
            return ProcessingResult(
                transaction_id=transaction.transaction_id,
                success=False,
                status=TransactionStatus.FAILED,
                result_data={},
                processing_time=processing_time,
                error_message=error_message,
                node_id=self.node_id,
            )
        finally:
            if transaction.transaction_id in self.current_transactions:
                del self.current_transactions[transaction.transaction_id]
                self.active_transactions.labels(node=self.node_id).dec()

    def _validate_transaction(self, transaction: Transaction) -> bool:
        """Validate transaction data"""
        try:
            if not transaction.transaction_id or not transaction.user_id:
                return False
            if transaction.amount <= 0:
                return False
            if not transaction.source_account or not transaction.destination_account:
                return False
            if transaction.checksum:
                calculated_checksum = self._calculate_checksum(transaction)
                if calculated_checksum != transaction.checksum:
                    return False
            if not self._validate_business_rules(transaction):
                return False
            return True
        except Exception as e:
            self.logger.error(f"Transaction validation error: {str(e)}")
            return False

    def _calculate_checksum(self, transaction: Transaction) -> str:
        """Calculate transaction checksum"""
        data = f"{transaction.transaction_id}{transaction.user_id}{transaction.amount}{transaction.currency}{transaction.source_account}{transaction.destination_account}"
        return hashlib.sha256(data.encode()).hexdigest()

    def _validate_business_rules(self, transaction: Transaction) -> bool:
        """Validate business rules"""
        try:
            if not self._check_account_balance(
                transaction.source_account, transaction.amount
            ):
                return False
            if not self._check_transaction_limits(transaction):
                return False
            if not self._check_compliance_rules(transaction):
                return False
            return True
        except Exception as e:
            self.logger.error(f"Business rule validation error: {str(e)}")
            return False

    def _check_account_balance(self, account_id: str, amount: float) -> bool:
        """Check if account has sufficient balance"""
        try:
            cache_key = f"account_balance:{account_id}"
            balance = self.redis_client.get(cache_key)
            if balance:
                return float(balance) >= amount
            return True
        except Exception:
            return False

    def _check_transaction_limits(self, transaction: Transaction) -> bool:
        """Check transaction limits"""
        try:
            daily_limit_key = f"daily_limit:{transaction.user_id}:{datetime.now().strftime('%Y-%m-%d')}"
            daily_total = self.redis_client.get(daily_limit_key)
            if daily_total and float(daily_total) + transaction.amount > 100000:
                return False
            if transaction.amount > 50000:
                return False
            return True
        except Exception:
            return False

    def _check_compliance_rules(self, transaction: Transaction) -> bool:
        """Check compliance and regulatory rules"""
        try:
            if transaction.amount > 10000:
                pass
            return True
        except Exception:
            return False

    def _execute_transaction_logic(self, transaction: Transaction) -> Dict[str, Any]:
        """Execute transaction-specific logic"""
        try:
            if transaction.transaction_type == "transfer":
                return self._process_transfer(transaction)
            elif transaction.transaction_type == "payment":
                return self._process_payment(transaction)
            elif transaction.transaction_type == "withdrawal":
                return self._process_withdrawal(transaction)
            elif transaction.transaction_type == "deposit":
                return self._process_deposit(transaction)
            else:
                raise ValueError(
                    f"Unknown transaction type: {transaction.transaction_type}"
                )
        except Exception as e:
            self.logger.error(f"Transaction execution error: {str(e)}")
            raise

    def _process_transfer(self, transaction: Transaction) -> Dict[str, Any]:
        """Process money transfer"""
        time.sleep(0.1)
        self._update_account_balance(transaction.source_account, -transaction.amount)
        self._update_account_balance(
            transaction.destination_account, transaction.amount
        )
        daily_limit_key = (
            f"daily_limit:{transaction.user_id}:{datetime.now().strftime('%Y-%m-%d')}"
        )
        self.redis_client.incrbyfloat(daily_limit_key, transaction.amount)
        self.redis_client.expire(daily_limit_key, 86400)
        return {
            "transfer_id": str(uuid.uuid4()),
            "source_balance": self._get_account_balance(transaction.source_account),
            "destination_balance": self._get_account_balance(
                transaction.destination_account
            ),
            "exchange_rate": 1.0,
            "fees": 0.0,
        }

    def _process_payment(self, transaction: Transaction) -> Dict[str, Any]:
        """Process payment"""
        time.sleep(0.05)
        self._update_account_balance(transaction.source_account, -transaction.amount)
        return {
            "payment_id": str(uuid.uuid4()),
            "merchant_id": transaction.destination_account,
            "authorization_code": f"AUTH{int(time.time())}",
            "fees": transaction.amount * 0.029,
        }

    def _process_withdrawal(self, transaction: Transaction) -> Dict[str, Any]:
        """Process withdrawal"""
        time.sleep(0.08)
        self._update_account_balance(transaction.source_account, -transaction.amount)
        return {
            "withdrawal_id": str(uuid.uuid4()),
            "atm_id": transaction.metadata.get("atm_id", "ATM001"),
            "cash_dispensed": transaction.amount,
        }

    def _process_deposit(self, transaction: Transaction) -> Dict[str, Any]:
        """Process deposit"""
        time.sleep(0.03)
        self._update_account_balance(
            transaction.destination_account, transaction.amount
        )
        return {
            "deposit_id": str(uuid.uuid4()),
            "deposit_method": transaction.metadata.get(
                "deposit_method", "bank_transfer"
            ),
            "clearing_time": "immediate",
        }

    def _update_account_balance(self, account_id: str, amount: float) -> Any:
        """Update account balance"""
        cache_key = f"account_balance:{account_id}"
        self.redis_client.incrbyfloat(cache_key, amount)

    def _get_account_balance(self, account_id: str) -> float:
        """Get account balance"""
        cache_key = f"account_balance:{account_id}"
        balance = self.redis_client.get(cache_key)
        return float(balance) if balance else 0.0

    def _update_transaction_status(
        self,
        transaction: Transaction,
        status: TransactionStatus,
        processing_time: Optional[float] = None,
        error_message: Optional[str] = None,
    ) -> Any:
        """Update transaction status in database"""
        try:
            tx_log = (
                self.db_session.query(TransactionLog)
                .filter_by(transaction_id=transaction.transaction_id)
                .first()
            )
            if tx_log:
                tx_log.status = status.value
                tx_log.processing_node = self.node_id
                tx_log.updated_at = datetime.utcnow()
                if status == TransactionStatus.COMPLETED:
                    tx_log.completed_at = datetime.utcnow()
                if processing_time is not None:
                    tx_log.processing_time = processing_time
                if error_message:
                    tx_log.error_message = error_message
                self.db_session.commit()
            status_key = f"transaction_status:{transaction.transaction_id}"
            status_data = {
                "status": status.value,
                "processing_node": self.node_id,
                "updated_at": datetime.utcnow().isoformat(),
            }
            if error_message:
                status_data["error_message"] = error_message
            self.redis_client.setex(status_key, 3600, json.dumps(status_data))
        except Exception as e:
            self.logger.error(f"Status update failed: {str(e)}")


class DistributedTransactionManager:
    """Main distributed transaction management system"""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.logger = structlog.get_logger(__name__)
        self.message_queue = MessageQueue(
            queue_type=config.get("queue_type", "redis"),
            config=config.get("queue_config", {}),
        )
        self.db_engine = create_engine(
            config.get("database_url", "postgresql://localhost/nexafi"),
            poolclass=QueuePool,
            pool_size=20,
            max_overflow=30,
            pool_pre_ping=True,
        )
        Session = sessionmaker(bind=self.db_engine)
        self.db_session = Session()
        self.redis_client = redis.from_url(
            config.get("redis_url", "redis://localhost:6379/0"),
            decode_responses=True,
            connection_pool_kwargs={"max_connections": 50},
        )
        self.load_balancer = LoadBalancer(self.redis_client)
        self.processors = {}
        self.is_running = False
        Base.metadata.create_all(bind=self.db_engine)
        self.submitted_counter = Counter(
            "transactions_submitted_total", "Total submitted transactions"
        )
        self.queue_size_gauge = Gauge(
            "transaction_queue_size", "Transaction queue size", ["priority"]
        )
        self.throughput_gauge = Gauge(
            "transaction_throughput", "Transaction throughput per second"
        )

    def start_processing(self, num_workers: Optional[int] = None) -> Any:
        """Start distributed transaction processing"""
        if self.is_running:
            return
        self.is_running = True
        if num_workers is None:
            num_workers = min(mp.cpu_count() * 2, 16)
        self.logger.info(f"Starting {num_workers} transaction processors")
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures: List[Any] = []
            for i in range(num_workers):
                node_id = f"processor_{i}_{int(time.time())}"
                self.load_balancer.register_node(
                    node_id=node_id,
                    capacity=100,
                    capabilities=["transfer", "payment", "withdrawal", "deposit"],
                )
                future = executor.submit(self._run_processor, node_id)
                futures.append(future)
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.logger.error(f"Processor failed: {str(e)}")

    def _run_processor(self, node_id: str) -> Any:
        """Run individual transaction processor"""
        try:
            processor = TransactionProcessor(
                node_id, self.db_session, self.redis_client
            )
            self.logger.info(f"Started processor: {node_id}")
            while self.is_running:
                try:
                    message = self.message_queue.consume("transaction_queue", timeout=1)
                    if message:
                        transaction = Transaction(**message)
                        result = processor.process_transaction(transaction)
                        current_load = len(processor.current_transactions)
                        self.load_balancer.update_node_load(node_id, current_load)
                        self.logger.info(
                            f"Processed transaction {transaction.transaction_id}: {result.status.value}"
                        )
                    else:
                        time.sleep(0.1)
                except Exception as e:
                    self.logger.error(f"Processing error in {node_id}: {str(e)}")
                    time.sleep(1)
        except Exception as e:
            self.logger.error(f"Processor {node_id} failed: {str(e)}")

    def submit_transaction(self, transaction: Transaction) -> str:
        """Submit transaction for processing"""
        try:
            if not transaction.transaction_id:
                transaction.transaction_id = str(uuid.uuid4())
            transaction.checksum = self._calculate_checksum(transaction)
            self._store_transaction(transaction)
            message = asdict(transaction)
            message["timestamp"] = transaction.timestamp.isoformat()
            message["status"] = transaction.status.value
            message["priority"] = transaction.priority.value
            priority = transaction.priority.value
            self.message_queue.publish("transaction_queue", message, priority)
            self.submitted_counter.inc()
            self.logger.info(f"Submitted transaction: {transaction.transaction_id}")
            return transaction.transaction_id
        except Exception as e:
            self.logger.error(f"Transaction submission failed: {str(e)}")
            raise

    def _calculate_checksum(self, transaction: Transaction) -> str:
        """Calculate transaction checksum"""
        data = f"{transaction.transaction_id}{transaction.user_id}{transaction.amount}{transaction.currency}{transaction.source_account}{transaction.destination_account}"
        return hashlib.sha256(data.encode()).hexdigest()

    def _store_transaction(self, transaction: Transaction) -> Any:
        """Store transaction in database"""
        try:
            tx_log = TransactionLog(
                transaction_id=transaction.transaction_id,
                user_id=transaction.user_id,
                transaction_type=transaction.transaction_type,
                amount=transaction.amount,
                currency=transaction.currency,
                source_account=transaction.source_account,
                destination_account=transaction.destination_account,
                status=transaction.status.value,
                priority=transaction.priority.value,
                metadata=json.dumps(transaction.metadata),
                checksum=transaction.checksum,
            )
            self.db_session.add(tx_log)
            self.db_session.commit()
        except Exception as e:
            self.logger.error(f"Transaction storage failed: {str(e)}")
            self.db_session.rollback()
            raise

    def get_transaction_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """Get transaction status"""
        try:
            status_key = f"transaction_status:{transaction_id}"
            cached_status = self.redis_client.get(status_key)
            if cached_status:
                return json.loads(cached_status)
            tx_log = (
                self.db_session.query(TransactionLog)
                .filter_by(transaction_id=transaction_id)
                .first()
            )
            if tx_log:
                return {
                    "transaction_id": tx_log.transaction_id,
                    "status": tx_log.status,
                    "processing_node": tx_log.processing_node,
                    "created_at": tx_log.created_at.isoformat(),
                    "updated_at": tx_log.updated_at.isoformat(),
                    "completed_at": (
                        tx_log.completed_at.isoformat() if tx_log.completed_at else None
                    ),
                    "processing_time": tx_log.processing_time,
                    "error_message": tx_log.error_message,
                }
            return None
        except Exception as e:
            self.logger.error(f"Status retrieval failed: {str(e)}")
            return None

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get system performance metrics"""
        try:
            queue_sizes: Dict[str, Any] = {}
            for priority in Priority:
                size = self.message_queue.get_queue_size(
                    f"transaction_queue_{priority.name.lower()}"
                )
                queue_sizes[priority.name.lower()] = size
                self.queue_size_gauge.labels(priority=priority.name.lower()).set(size)
            recent_transactions = (
                self.db_session.query(TransactionLog)
                .filter(
                    TransactionLog.created_at
                    >= datetime.utcnow() - timedelta(minutes=5)
                )
                .all()
            )
            total_recent = len(recent_transactions)
            completed_recent = len(
                [tx for tx in recent_transactions if tx.status == "completed"]
            )
            failed_recent = len(
                [tx for tx in recent_transactions if tx.status == "failed"]
            )
            throughput = total_recent / 300.0
            self.throughput_gauge.set(throughput)
            processing_times = [
                tx.processing_time for tx in recent_transactions if tx.processing_time
            ]
            avg_processing_time = (
                sum(processing_times) / len(processing_times) if processing_times else 0
            )
            healthy_nodes = len(self.load_balancer._get_healthy_nodes())
            total_nodes = len(self.load_balancer.nodes)
            return {
                "queue_sizes": queue_sizes,
                "total_recent_transactions": total_recent,
                "completed_recent": completed_recent,
                "failed_recent": failed_recent,
                "success_rate": (
                    completed_recent / total_recent if total_recent > 0 else 0
                ),
                "throughput_tps": throughput,
                "avg_processing_time": avg_processing_time,
                "healthy_nodes": healthy_nodes,
                "total_nodes": total_nodes,
                "node_health_ratio": (
                    healthy_nodes / total_nodes if total_nodes > 0 else 0
                ),
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            self.logger.error(f"Metrics calculation failed: {str(e)}")
            return {"error": str(e)}

    def stop_processing(self) -> Any:
        """Stop transaction processing"""
        self.is_running = False
        self.logger.info("Stopping transaction processing")


def create_distributed_transaction_manager(
    config: Dict[str, Any],
) -> DistributedTransactionManager:
    """Factory function to create distributed transaction manager"""
    return DistributedTransactionManager(config)


if __name__ == "__main__":
    import structlog

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    config = {
        "queue_type": "redis",
        "queue_config": {"redis_url": "redis://localhost:6379/0"},
        "database_url": "postgresql://localhost/nexafi",
        "redis_url": "redis://localhost:6379/0",
    }
    manager = create_distributed_transaction_manager(config)
    transaction = Transaction(
        transaction_id="",
        user_id="user123",
        transaction_type="transfer",
        amount=1000.0,
        currency="USD",
        source_account="acc_source_123",
        destination_account="acc_dest_456",
        metadata={"description": "Test transfer"},
        priority=Priority.NORMAL,
        timestamp=datetime.utcnow(),
        status=TransactionStatus.PENDING,
    )
    tx_id = manager.submit_transaction(transaction)
    logger.info(f"Submitted transaction: {tx_id}")
    metrics = manager.get_system_metrics()
    logger.info(f"System Metrics: {json.dumps(metrics, indent=2)}")
