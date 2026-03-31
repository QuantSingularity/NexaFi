"""
Base Enterprise Integration Framework for NexaFi
Provides common functionality for all enterprise system integrations
"""

import hashlib
import json
import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import redis
import requests
import schedule
from circuit_breaker import CircuitBreaker
from cryptography.fernet import Fernet
from nexafi_logging.logger import get_logger
from prometheus_client import Counter, Gauge, Histogram
from requests.adapters import HTTPAdapter
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from urllib3.util.retry import Retry

logger = get_logger(__name__)
INTEGRATION_REQUESTS = Counter(
    "integration_requests_total", "Total integration requests", ["system", "operation"]
)
INTEGRATION_DURATION = Histogram(
    "integration_request_duration_seconds", "Request duration", ["system", "operation"]
)
INTEGRATION_ERRORS = Counter(
    "integration_errors_total", "Total integration errors", ["system", "error_type"]
)
INTEGRATION_SYNC_STATUS = Gauge(
    "integration_sync_status", "Sync status", ["system", "entity"]
)


class IntegrationStatus(Enum):
    """Integration status enumeration"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    SYNCING = "syncing"
    MAINTENANCE = "maintenance"


class AuthMethod(Enum):
    """Authentication method enumeration"""

    OAUTH2 = "oauth2"
    BASIC = "basic"
    API_KEY = "api_key"
    JWT = "jwt"
    SAML = "saml"
    CERTIFICATE = "certificate"
    CUSTOM = "custom"


@dataclass
class IntegrationConfig:
    """Integration configuration"""

    system_name: str
    base_url: str
    auth_method: AuthMethod
    credentials: Dict[str, Any]
    timeout: int = 30
    retry_attempts: int = 3
    rate_limit: int = 100
    batch_size: int = 100
    sync_interval: int = 300
    encryption_key: Optional[str] = None
    custom_headers: Optional[Dict[str, str]] = None
    webhook_url: Optional[str] = None
    enable_caching: bool = True
    cache_ttl: int = 3600
    enable_circuit_breaker: bool = True
    circuit_breaker_threshold: int = 5
    enable_monitoring: bool = True
    data_mapping: Optional[Dict[str, str]] = None
    field_transformations: Optional[Dict[str, Callable]] = None


@dataclass
class SyncResult:
    """Synchronization result"""

    system_name: str
    entity_type: str
    operation: str
    success: bool
    records_processed: int
    records_failed: int
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    error_message: Optional[str] = None
    warnings: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


Base = declarative_base()


class IntegrationLog(Base):
    """Integration log model"""

    __tablename__ = "integration_logs"
    id = Column(Integer, primary_key=True)
    system_name = Column(String(100), nullable=False)
    operation = Column(String(100), nullable=False)
    entity_type = Column(String(100))
    status = Column(String(50), nullable=False)
    request_data = Column(Text)
    response_data = Column(Text)
    error_message = Column(Text)
    duration_ms = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow)
    correlation_id = Column(String(100))
    user_id = Column(String(100))


class IntegrationState(Base):
    """Integration state tracking"""

    __tablename__ = "integration_states"
    id = Column(Integer, primary_key=True)
    system_name = Column(String(100), nullable=False)
    entity_type = Column(String(100), nullable=False)
    last_sync_time = Column(DateTime)
    last_sync_status = Column(String(50))
    last_sync_record_count = Column(Integer)
    next_sync_time = Column(DateTime)
    sync_token = Column(String(500))
    configuration = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SecurityManager:
    """Security manager for enterprise integrations"""

    def __init__(self, encryption_key: Optional[str] = None) -> None:
        self.encryption_key = encryption_key or os.getenv("INTEGRATION_ENCRYPTION_KEY")
        if self.encryption_key:
            self.cipher = Fernet(self.encryption_key.encode())
        else:
            self.cipher = None
        self.logger = logging.getLogger(__name__)

    def encrypt_credentials(self, credentials: Dict[str, Any]) -> str:
        """Encrypt sensitive credentials"""
        if not self.cipher:
            self.logger.warning(
                "No encryption key provided, storing credentials in plain text"
            )
            return json.dumps(credentials)
        try:
            credentials_json = json.dumps(credentials)
            encrypted = self.cipher.encrypt(credentials_json.encode())
            return encrypted.decode()
        except Exception as e:
            self.logger.error(f"Failed to encrypt credentials: {str(e)}")
            raise

    def decrypt_credentials(self, encrypted_credentials: str) -> Dict[str, Any]:
        """Decrypt sensitive credentials"""
        if not self.cipher:
            return json.loads(encrypted_credentials)
        try:
            decrypted = self.cipher.decrypt(encrypted_credentials.encode())
            return json.loads(decrypted.decode())
        except Exception as e:
            self.logger.error(f"Failed to decrypt credentials: {str(e)}")
            raise

    def generate_api_signature(
        self,
        method: str,
        url: str,
        body: str,
        secret: str,
        timestamp: Optional[str] = None,
    ) -> str:
        """Generate API signature for secure requests"""
        if not timestamp:
            timestamp = str(int(datetime.utcnow().timestamp()))
        message = f"{method}\n{url}\n{body}\n{timestamp}"
        signature = hashlib.hmac.new(
            secret.encode(), message.encode(), hashlib.sha256
        ).hexdigest()
        return signature

    def validate_webhook_signature(
        self, payload: str, signature: str, secret: str
    ) -> bool:
        """Validate webhook signature"""
        expected_signature = hashlib.hmac.new(
            secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        return signature == expected_signature


class RateLimiter:
    """Rate limiter for API requests"""

    def __init__(self, redis_client: redis.Redis, rate_limit: int = 100) -> None:
        self.redis_client = redis_client
        self.rate_limit = rate_limit
        self.window_size = 60

    def is_allowed(self, key: str) -> bool:
        """Check if request is allowed under rate limit"""
        try:
            current_time = int(time.time())
            window_start = current_time - self.window_size
            self.redis_client.zremrangebyscore(key, 0, window_start)
            current_requests = self.redis_client.zcard(key)
            if current_requests >= self.rate_limit:
                return False
            self.redis_client.zadd(key, {str(current_time): current_time})
            self.redis_client.expire(key, self.window_size)
            return True
        except Exception as e:
            logging.error(f"Rate limiter error: {str(e)}")
            return True


class DataTransformer:
    """Data transformation utilities"""

    @staticmethod
    def apply_field_mapping(
        data: Dict[str, Any], mapping: Dict[str, str]
    ) -> Dict[str, Any]:
        """Apply field mapping to data"""
        if not mapping:
            return data
        transformed: Dict[str, Any] = {}
        for source_field, target_field in mapping.items():
            if source_field in data:
                transformed[target_field] = data[source_field]
        return transformed

    @staticmethod
    def apply_transformations(
        data: Dict[str, Any], transformations: Dict[str, Callable]
    ) -> Dict[str, Any]:
        """Apply field transformations"""
        if not transformations:
            return data
        transformed = data.copy()
        for field, transform_func in transformations.items():
            if field in transformed:
                try:
                    transformed[field] = transform_func(transformed[field])
                except Exception as e:
                    logging.error(f"Transformation error for field {field}: {str(e)}")
        return transformed

    @staticmethod
    def normalize_date_format(date_value: Any, target_format: str = "%Y-%m-%d") -> str:
        """Normalize date format"""
        if isinstance(date_value, datetime):
            return date_value.strftime(target_format)
        elif isinstance(date_value, str):
            formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"]
            for fmt in formats:
                try:
                    parsed_date = datetime.strptime(date_value, fmt)
                    return parsed_date.strftime(target_format)
                except ValueError:
                    continue
        return str(date_value)

    @staticmethod
    def sanitize_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize data for security"""
        sanitized: Dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, str):
                sanitized[key] = value.replace("<", "&lt;").replace(">", "&gt;")
            elif isinstance(value, dict):
                sanitized[key] = DataTransformer.sanitize_data(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    (
                        DataTransformer.sanitize_data(item)
                        if isinstance(item, dict)
                        else item
                    )
                    for item in value
                ]
            else:
                sanitized[key] = value
        return sanitized


class BaseIntegration(ABC):
    """Base class for all enterprise integrations"""

    def __init__(
        self,
        config: IntegrationConfig,
        db_session: Any = None,
        redis_client: Any = None,
    ) -> None:
        self.config = config
        self.db_session = db_session
        self.redis_client = redis_client
        self.logger = logging.getLogger(f"{__name__}.{config.system_name}")
        self.security_manager = SecurityManager(config.encryption_key)
        self.rate_limiter = (
            RateLimiter(redis_client, config.rate_limit) if redis_client else None
        )
        self.data_transformer = DataTransformer()
        if config.enable_circuit_breaker:
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=config.circuit_breaker_threshold,
                recovery_timeout=60,
                expected_exception=Exception,
            )
        else:
            self.circuit_breaker = None
        self.session = requests.Session()
        retry_strategy = Retry(
            total=config.retry_attempts,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        if config.custom_headers:
            self.session.headers.update(config.custom_headers)
        self._initialize_state()

    def _initialize_state(self) -> Any:
        """Initialize integration state"""
        if not self.db_session:
            return
        try:
            state = (
                self.db_session.query(IntegrationState)
                .filter_by(system_name=self.config.system_name)
                .first()
            )
            if not state:
                state = IntegrationState(
                    system_name=self.config.system_name,
                    entity_type="default",
                    configuration=json.dumps(asdict(self.config)),
                )
                self.db_session.add(state)
                self.db_session.commit()
        except Exception as e:
            self.logger.error(f"Failed to initialize state: {str(e)}")

    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with the enterprise system"""

    @abstractmethod
    def test_connection(self) -> bool:
        """Test connection to the enterprise system"""

    @abstractmethod
    def sync_data(self, entity_type: str, **kwargs) -> SyncResult:
        """Sync data with the enterprise system"""

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> requests.Response:
        """Make authenticated request to enterprise system"""
        if self.rate_limiter:
            rate_limit_key = f"rate_limit:{self.config.system_name}"
            if not self.rate_limiter.is_allowed(rate_limit_key):
                raise Exception("Rate limit exceeded")
        url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        request_headers = headers or {}
        auth_headers = self._get_auth_headers()
        request_headers.update(auth_headers)
        if self.circuit_breaker:
            response = self.circuit_breaker(self._execute_request)(
                method, url, data, params, request_headers
            )
        else:
            response = self._execute_request(method, url, data, params, request_headers)
        self._log_request(method, endpoint, data, response)
        if self.config.enable_monitoring:
            INTEGRATION_REQUESTS.labels(
                system=self.config.system_name, operation=endpoint
            ).inc()
        return response

    def _execute_request(
        self,
        method: str,
        url: str,
        data: Dict[str, Any],
        params: Dict[str, Any],
        headers: Dict[str, str],
    ) -> requests.Response:
        """Execute HTTP request"""
        start_time = time.time()
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=headers,
                timeout=self.config.timeout,
            )
            duration = time.time() - start_time
            if self.config.enable_monitoring:
                INTEGRATION_DURATION.labels(
                    system=self.config.system_name, operation=url.split("/")[-1]
                ).observe(duration)
            response.raise_for_status()
            return response
        except Exception as e:
            duration = time.time() - start_time
            if self.config.enable_monitoring:
                INTEGRATION_ERRORS.labels(
                    system=self.config.system_name, error_type=type(e).__name__
                ).inc()
            self.logger.error(f"Request failed: {str(e)}")
            raise

    @abstractmethod
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers"""

    def _log_request(
        self,
        method: str,
        endpoint: str,
        data: Dict[str, Any],
        response: requests.Response,
    ) -> Any:
        """Log request details"""
        if not self.db_session:
            return
        try:
            log_entry = IntegrationLog(
                system_name=self.config.system_name,
                operation=f"{method} {endpoint}",
                status="success" if response.status_code < 400 else "error",
                request_data=json.dumps(data) if data else None,
                response_data=response.text[:1000],
                duration_ms=int(response.elapsed.total_seconds() * 1000),
                correlation_id=response.headers.get("X-Correlation-ID"),
            )
            self.db_session.add(log_entry)
            self.db_session.commit()
        except Exception as e:
            self.logger.error(f"Failed to log request: {str(e)}")

    def get_cached_data(self, cache_key: str) -> Optional[Any]:
        """Get data from cache"""
        if not self.redis_client or not self.config.enable_caching:
            return None
        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            self.logger.error(f"Cache retrieval error: {str(e)}")
        return None

    def set_cached_data(
        self, cache_key: str, data: Any, ttl: Optional[int] = None
    ) -> Any:
        """Set data in cache"""
        if not self.redis_client or not self.config.enable_caching:
            return
        try:
            ttl = ttl or self.config.cache_ttl
            self.redis_client.setex(cache_key, ttl, json.dumps(data, default=str))
        except Exception as e:
            self.logger.error(f"Cache storage error: {str(e)}")

    def update_sync_state(self, entity_type: str, sync_result: SyncResult) -> Any:
        """Update synchronization state"""
        if not self.db_session:
            return
        try:
            state = (
                self.db_session.query(IntegrationState)
                .filter_by(system_name=self.config.system_name, entity_type=entity_type)
                .first()
            )
            if not state:
                state = IntegrationState(
                    system_name=self.config.system_name, entity_type=entity_type
                )
                self.db_session.add(state)
            state.last_sync_time = sync_result.end_time
            state.last_sync_status = "success" if sync_result.success else "error"
            state.last_sync_record_count = sync_result.records_processed
            state.next_sync_time = datetime.utcnow() + timedelta(
                seconds=self.config.sync_interval
            )
            state.updated_at = datetime.utcnow()
            self.db_session.commit()
            if self.config.enable_monitoring:
                INTEGRATION_SYNC_STATUS.labels(
                    system=self.config.system_name, entity=entity_type
                ).set(1 if sync_result.success else 0)
        except Exception as e:
            self.logger.error(f"Failed to update sync state: {str(e)}")

    def schedule_sync(
        self, entity_type: str, interval_minutes: Optional[int] = None
    ) -> Any:
        """Schedule periodic synchronization"""
        interval = interval_minutes or self.config.sync_interval // 60

        def sync_job():
            try:
                result = self.sync_data(entity_type)
                self.logger.info(f"Scheduled sync completed: {result}")
            except Exception as e:
                self.logger.error(f"Scheduled sync failed: {str(e)}")

        schedule.every(interval).minutes.do(sync_job)
        self.logger.info(f"Scheduled sync for {entity_type} every {interval} minutes")

    def process_webhook(
        self, payload: Dict[str, Any], signature: Optional[str] = None
    ) -> bool:
        """Process incoming webhook"""
        try:
            if signature and hasattr(self.config.credentials, "webhook_secret"):
                if not self.security_manager.validate_webhook_signature(
                    json.dumps(payload),
                    signature,
                    self.config.credentials["webhook_secret"],
                ):
                    self.logger.warning("Invalid webhook signature")
                    return False
            self._process_webhook_data(payload)
            return True
        except Exception as e:
            self.logger.error(f"Webhook processing failed: {str(e)}")
            return False

    @abstractmethod
    def _process_webhook_data(self, payload: Dict[str, Any]) -> Any:
        """Process webhook data (to be implemented by subclasses)"""

    def get_integration_status(self) -> Dict[str, Any]:
        """Get integration status and health"""
        try:
            connection_ok = self.test_connection()
            last_sync_status = None
            if self.db_session:
                state = (
                    self.db_session.query(IntegrationState)
                    .filter_by(system_name=self.config.system_name)
                    .first()
                )
                if state:
                    last_sync_status = {
                        "last_sync_time": (
                            state.last_sync_time.isoformat()
                            if state.last_sync_time
                            else None
                        ),
                        "status": state.last_sync_status,
                        "record_count": state.last_sync_record_count,
                        "next_sync_time": (
                            state.next_sync_time.isoformat()
                            if state.next_sync_time
                            else None
                        ),
                    }
            return {
                "system_name": self.config.system_name,
                "status": (
                    IntegrationStatus.ACTIVE.value
                    if connection_ok
                    else IntegrationStatus.ERROR.value
                ),
                "connection_ok": connection_ok,
                "last_sync": last_sync_status,
                "configuration": {
                    "base_url": self.config.base_url,
                    "auth_method": self.config.auth_method.value,
                    "rate_limit": self.config.rate_limit,
                    "sync_interval": self.config.sync_interval,
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            self.logger.error(f"Failed to get integration status: {str(e)}")
            return {
                "system_name": self.config.system_name,
                "status": IntegrationStatus.ERROR.value,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }


class IntegrationManager:
    """Manager for multiple enterprise integrations"""

    def __init__(self, db_session: Any = None, redis_client: Any = None) -> None:
        self.db_session = db_session
        self.redis_client = redis_client
        self.integrations: Dict[str, BaseIntegration] = {}
        self.logger = logging.getLogger(__name__)
        self.scheduler_thread = None
        self.is_running = False

    def register_integration(self, integration: BaseIntegration) -> Any:
        """Register an integration"""
        self.integrations[integration.config.system_name] = integration
        self.logger.info(f"Registered integration: {integration.config.system_name}")

    def get_integration(self, system_name: str) -> Optional[BaseIntegration]:
        """Get integration by system name"""
        return self.integrations.get(system_name)

    def start_scheduler(self) -> Any:
        """Start the integration scheduler"""
        if self.is_running:
            return
        self.is_running = True

        def run_scheduler():
            while self.is_running:
                schedule.run_pending()
                time.sleep(1)

        self.scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        self.scheduler_thread.start()
        self.logger.info("Integration scheduler started")

    def stop_scheduler(self) -> Any:
        """Stop the integration scheduler"""
        self.is_running = False
        if self.scheduler_thread:
            self.scheduler_thread.join()
        self.logger.info("Integration scheduler stopped")

    def sync_all(self, entity_type: Optional[str] = None) -> Dict[str, SyncResult]:
        """Sync all integrations"""
        results: Dict[str, Any] = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_system: Dict[str, Any] = {}
            for system_name, integration in self.integrations.items():
                if entity_type:
                    future = executor.submit(integration.sync_data, entity_type)
                else:
                    future = executor.submit(integration.sync_data, "default")
                future_to_system[future] = system_name
            for future in as_completed(future_to_system):
                system_name = future_to_system[future]
                try:
                    result = future.result()
                    results[system_name] = result
                except Exception as e:
                    self.logger.error(f"Sync failed for {system_name}: {str(e)}")
                    results[system_name] = SyncResult(
                        system_name=system_name,
                        entity_type=entity_type or "default",
                        operation="sync",
                        success=False,
                        records_processed=0,
                        records_failed=0,
                        start_time=datetime.utcnow(),
                        end_time=datetime.utcnow(),
                        duration_seconds=0,
                        error_message=str(e),
                    )
        return results

    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all integrations"""
        status: Dict[str, Any] = {}
        for system_name, integration in self.integrations.items():
            status[system_name] = integration.get_integration_status()
        return status

    def health_check(self) -> Dict[str, Any]:
        """Perform health check on all integrations"""
        healthy_count = 0
        total_count = len(self.integrations)
        system_status: Dict[str, Any] = {}
        for system_name, integration in self.integrations.items():
            try:
                is_healthy = integration.test_connection()
                system_status[system_name] = "healthy" if is_healthy else "unhealthy"
                if is_healthy:
                    healthy_count += 1
            except Exception as e:
                system_status[system_name] = f"error: {str(e)}"
        overall_health = (
            "healthy"
            if healthy_count == total_count
            else "degraded" if healthy_count > 0 else "unhealthy"
        )
        return {
            "overall_health": overall_health,
            "healthy_systems": healthy_count,
            "total_systems": total_count,
            "system_status": system_status,
            "timestamp": datetime.utcnow().isoformat(),
        }


def create_integration_config_from_env(system_name: str) -> IntegrationConfig:
    """Create integration config from environment variables"""
    prefix = f"{system_name.upper()}_"
    return IntegrationConfig(
        system_name=system_name,
        base_url=os.getenv(f"{prefix}BASE_URL"),
        auth_method=AuthMethod(os.getenv(f"{prefix}AUTH_METHOD", "oauth2")),
        credentials={
            "client_id": os.getenv(f"{prefix}CLIENT_ID"),
            "client_secret": os.getenv(f"{prefix}CLIENT_SECRET"),
            "username": os.getenv(f"{prefix}USERNAME"),
            "password": os.getenv(f"{prefix}PASSWORD"),
            "api_key": os.getenv(f"{prefix}API_KEY"),
        },
        timeout=int(os.getenv(f"{prefix}TIMEOUT", "30")),
        retry_attempts=int(os.getenv(f"{prefix}RETRY_ATTEMPTS", "3")),
        rate_limit=int(os.getenv(f"{prefix}RATE_LIMIT", "100")),
        batch_size=int(os.getenv(f"{prefix}BATCH_SIZE", "100")),
        sync_interval=int(os.getenv(f"{prefix}SYNC_INTERVAL", "300")),
        encryption_key=os.getenv(f"{prefix}ENCRYPTION_KEY"),
        enable_caching=os.getenv(f"{prefix}ENABLE_CACHING", "true").lower() == "true",
        cache_ttl=int(os.getenv(f"{prefix}CACHE_TTL", "3600")),
        enable_circuit_breaker=os.getenv(
            f"{prefix}ENABLE_CIRCUIT_BREAKER", "true"
        ).lower()
        == "true",
        enable_monitoring=os.getenv(f"{prefix}ENABLE_MONITORING", "true").lower()
        == "true",
    )


def setup_database(database_url: str) -> Any:
    """Setup database for integration logging"""
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    db_session = setup_database("sqlite:///integrations.db")
    redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
    manager = IntegrationManager(db_session, redis_client)
    manager.start_scheduler()
    logger.info("Enterprise Integration Framework initialized")
