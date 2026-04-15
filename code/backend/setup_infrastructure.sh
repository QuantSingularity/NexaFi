#!/bin/bash

# NexaFi Backend Infrastructure Setup
# This script sets up the infrastructure components for the backend

echo "🚀 Setting up NexaFi Backend Infrastructure..."

# Create infrastructure directory
mkdir -p infrastructure/redis
mkdir -p infrastructure/monitoring
mkdir -p infrastructure/logging
mkdir -p infrastructure/message-queue

# Create Redis configuration
cat > infrastructure/redis/redis.conf << 'EOF'
# Redis configuration for NexaFi
port 6379
bind 0.0.0.0
protected-mode no
save 900 1
save 300 10
save 60 10000
rdbcompression yes
rdbchecksum yes
dbfilename nexafi.rdb
dir ./
maxmemory 256mb
maxmemory-policy allkeys-lru
appendonly yes
appendfsync everysec
EOF

# Create Docker Compose for infrastructure services
cat > infrastructure/docker-compose.yml << 'EOF'
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    container_name: nexafi-redis
    ports:
      - "6379:6379"
    volumes:
      - ./redis/redis.conf:/usr/local/etc/redis/redis.conf
      - redis_data:/data
    command: redis-server /usr/local/etc/redis/redis.conf
    restart: unless-stopped
    networks:
      - nexafi-network

  rabbitmq:
    image: rabbitmq:3-management-alpine
    container_name: nexafi-rabbitmq
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      RABBITMQ_DEFAULT_USER: nexafi
      RABBITMQ_DEFAULT_PASS: nexafi123
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    restart: unless-stopped
    networks:
      - nexafi-network

  elasticsearch:
    image: elasticsearch:8.11.0
    container_name: nexafi-elasticsearch
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    ports:
      - "9200:9200"
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data
    restart: unless-stopped
    networks:
      - nexafi-network

  kibana:
    image: kibana:8.11.0
    container_name: nexafi-kibana
    ports:
      - "5601:5601"
    environment:
      ELASTICSEARCH_HOSTS: http://elasticsearch:9200
    depends_on:
      - elasticsearch
    restart: unless-stopped
    networks:
      - nexafi-network

volumes:
  redis_data:
  rabbitmq_data:
  elasticsearch_data:

networks:
  nexafi-network:
    driver: bridge
EOF

# Create infrastructure startup script
cat > infrastructure/start-infrastructure.sh << 'EOF'
#!/bin/bash

echo "🚀 Starting NexaFi Infrastructure Services..."

# Start infrastructure services
docker-compose up -d

echo "⏳ Waiting for services to be ready..."
sleep 30

# Check service health
echo "🔍 Checking service health..."

# Check Redis
if redis-cli -h localhost -p 6379 ping | grep -q PONG; then
    echo "✅ Redis is running"
else
    echo "❌ Redis is not responding"
fi

# Check RabbitMQ
if curl -s http://localhost:15672 > /dev/null; then
    echo "✅ RabbitMQ is running"
else
    echo "❌ RabbitMQ is not responding"
fi

# Check Elasticsearch
if curl -s http://localhost:9200 > /dev/null; then
    echo "✅ Elasticsearch is running"
else
    echo "❌ Elasticsearch is not responding"
fi

# Check Kibana
if curl -s http://localhost:5601 > /dev/null; then
    echo "✅ Kibana is running"
else
    echo "❌ Kibana is not responding"
fi

echo "🎉 Infrastructure setup complete!"
echo "📊 Access Kibana at: http://localhost:5601"
echo "🐰 Access RabbitMQ Management at: http://localhost:15672 (nexafi/nexafi123)"
EOF

chmod +x infrastructure/start-infrastructure.sh

# Create infrastructure stop script
cat > infrastructure/stop-infrastructure.sh << 'EOF'
#!/bin/bash

echo "🛑 Stopping NexaFi Infrastructure Services..."

# Stop infrastructure services
docker-compose down

echo "🎉 Infrastructure services stopped!"
EOF

chmod +x infrastructure/stop-infrastructure.sh

# Create shared utilities for all services
mkdir -p shared/utils
mkdir -p shared/middleware
mkdir -p shared/config

# Create shared configuration
cat > shared/config/infrastructure.py << 'EOF'
"""
Shared infrastructure configuration for NexaFi services
"""
import os
from typing import Dict, Any

class InfrastructureConfig:
    """Infrastructure configuration settings"""

    # Redis Configuration
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB = int(os.getenv('REDIS_DB', 0))
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')
    REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

    # RabbitMQ Configuration
    RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
    RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', 5672))
    RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'nexafi')
    RABBITMQ_PASSWORD = os.getenv('RABBITMQ_PASSWORD', 'nexafi123')
    RABBITMQ_VHOST = os.getenv('RABBITMQ_VHOST', '/')
    RABBITMQ_URL = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}{RABBITMQ_VHOST}"

    # Elasticsearch Configuration
    ELASTICSEARCH_HOST = os.getenv('ELASTICSEARCH_HOST', 'localhost')
    ELASTICSEARCH_PORT = int(os.getenv('ELASTICSEARCH_PORT', 9200))
    ELASTICSEARCH_URL = f"http://{ELASTICSEARCH_HOST}:{ELASTICSEARCH_PORT}"

    # Logging Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # Cache Configuration
    CACHE_DEFAULT_TIMEOUT = int(os.getenv('CACHE_DEFAULT_TIMEOUT', 300))
    CACHE_KEY_PREFIX = os.getenv('CACHE_KEY_PREFIX', 'nexafi:')

    # Rate Limiting Configuration
    RATE_LIMIT_STORAGE_URL = REDIS_URL
    RATE_LIMIT_DEFAULT = os.getenv('RATE_LIMIT_DEFAULT', '100 per hour')

    # Circuit Breaker Configuration
    CIRCUIT_BREAKER_FAILURE_THRESHOLD = int(os.getenv('CIRCUIT_BREAKER_FAILURE_THRESHOLD', 5))
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT = int(os.getenv('CIRCUIT_BREAKER_RECOVERY_TIMEOUT', 60))

    @classmethod
    def get_redis_config(cls) -> Dict[str, Any]:
        """Get Redis connection configuration"""
        config = {
            'host': cls.REDIS_HOST,
            'port': cls.REDIS_PORT,
            'db': cls.REDIS_DB,
            'decode_responses': True
        }
        if cls.REDIS_PASSWORD:
            config['password'] = cls.REDIS_PASSWORD
        return config

    @classmethod
    def get_rabbitmq_config(cls) -> Dict[str, Any]:
        """Get RabbitMQ connection configuration"""
        return {
            'host': cls.RABBITMQ_HOST,
            'port': cls.RABBITMQ_PORT,
            'virtual_host': cls.RABBITMQ_VHOST,
            'credentials': {
                'username': cls.RABBITMQ_USER,
                'password': cls.RABBITMQ_PASSWORD
            }
        }

    @classmethod
    def get_elasticsearch_config(cls) -> Dict[str, Any]:
        """Get Elasticsearch connection configuration"""
        return {
            'hosts': [cls.ELASTICSEARCH_URL],
            'timeout': 30,
            'max_retries': 3,
            'retry_on_timeout': True
        }
EOF

# Create shared cache utility
cat > shared/utils/cache.py << 'EOF'
"""
Shared caching utilities for NexaFi services
"""
import json
import redis
from typing import Any, Optional, Union
from functools import wraps
import hashlib
from ..config.infrastructure import InfrastructureConfig

class CacheManager:
    """Redis-based cache manager"""

    def __init__(self):
        self.redis_client = redis.Redis(**InfrastructureConfig.get_redis_config())
        self.default_timeout = InfrastructureConfig.CACHE_DEFAULT_TIMEOUT
        self.key_prefix = InfrastructureConfig.CACHE_KEY_PREFIX

    def _make_key(self, key: str) -> str:
        """Create a prefixed cache key"""
        return f"{self.key_prefix}{key}"

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            value = self.redis_client.get(self._make_key(key))
            if value:
                return json.loads(value)
            return None
        except Exception:
            return None

    def set(self, key: str, value: Any, timeout: Optional[int] = None) -> bool:
        """Set value in cache"""
        try:
            timeout = timeout or self.default_timeout
            serialized_value = json.dumps(value, default=str)
            return self.redis_client.setex(
                self._make_key(key),
                timeout,
                serialized_value
            )
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            return bool(self.redis_client.delete(self._make_key(key)))
        except Exception:
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            return bool(self.redis_client.exists(self._make_key(key)))
        except Exception:
            return False

    def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        try:
            keys = self.redis_client.keys(self._make_key(pattern))
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception:
            return 0

    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment a counter"""
        try:
            return self.redis_client.incr(self._make_key(key), amount)
        except Exception:
            return None

    def expire(self, key: str, timeout: int) -> bool:
        """Set expiration for a key"""
        try:
            return bool(self.redis_client.expire(self._make_key(key), timeout))
        except Exception:
            return False

# Global cache instance
cache = CacheManager()

def cached(timeout: Optional[int] = None, key_func: Optional[callable] = None):
    """Decorator for caching function results"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generation
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
                cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()

            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            return result

        return wrapper
    return decorator

def cache_key_for_user(user_id: str, *args, **kwargs) -> str:
    """Generate cache key for user-specific data"""
    key_parts = [str(user_id)]
    key_parts.extend(str(arg) for arg in args)
    key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
    return hashlib.md5(":".join(key_parts).encode()).hexdigest()
EOF

# Create shared message queue utility
cat > shared/utils/message_queue.py << 'EOF'
"""
Shared message queue utilities for NexaFi services
"""
import pika
import json
import logging
from typing import Dict, Any, Callable, Optional
from ..config.infrastructure import InfrastructureConfig

logger = logging.getLogger(__name__)

class MessageQueue:
    """RabbitMQ message queue manager"""

    def __init__(self):
        self.connection = None
        self.channel = None
        self.config = InfrastructureConfig.get_rabbitmq_config()

    def connect(self):
        """Establish connection to RabbitMQ"""
        try:
            credentials = pika.PlainCredentials(
                self.config['credentials']['username'],
                self.config['credentials']['password']
            )
            parameters = pika.ConnectionParameters(
                host=self.config['host'],
                port=self.config['port'],
                virtual_host=self.config['virtual_host'],
                credentials=credentials
            )
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            logger.info("Connected to RabbitMQ")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    def disconnect(self):
        """Close connection to RabbitMQ"""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("Disconnected from RabbitMQ")

    def declare_queue(self, queue_name: str, durable: bool = True):
        """Declare a queue"""
        if not self.channel:
            self.connect()

        self.channel.queue_declare(queue=queue_name, durable=durable)
        logger.info(f"Declared queue: {queue_name}")

    def declare_exchange(self, exchange_name: str, exchange_type: str = 'direct'):
        """Declare an exchange"""
        if not self.channel:
            self.connect()

        self.channel.exchange_declare(
            exchange=exchange_name,
            exchange_type=exchange_type,
            durable=True
        )
        logger.info(f"Declared exchange: {exchange_name}")

    def publish_message(self, queue_name: str, message: Dict[str, Any],
                       exchange: str = '', routing_key: Optional[str] = None):
        """Publish a message to a queue"""
        if not self.channel:
            self.connect()

        routing_key = routing_key or queue_name

        self.channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
                content_type='application/json'
            )
        )
        logger.info(f"Published message to {queue_name}: {message}")

    def consume_messages(self, queue_name: str, callback: Callable):
        """Consume messages from a queue"""
        if not self.channel:
            self.connect()

        def wrapper(ch, method, properties, body):
            try:
                message = json.loads(body)
                callback(message)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        self.channel.basic_consume(
            queue=queue_name,
            on_message_callback=wrapper
        )

        logger.info(f"Started consuming from {queue_name}")
        self.channel.start_consuming()

# Global message queue instance
mq = MessageQueue()

# Queue names
class Queues:
    REPORT_GENERATION = 'report_generation'
    EMAIL_NOTIFICATIONS = 'email_notifications'
    CREDIT_SCORING = 'credit_scoring'
    DOCUMENT_PROCESSING = 'document_processing'
    ANALYTICS_CALCULATION = 'analytics_calculation'
    PAYMENT_PROCESSING = 'payment_processing'
    AUDIT_LOGGING = 'audit_logging'

def publish_task(queue_name: str, task_data: Dict[str, Any]):
    """Publish a task to a queue"""
    try:
        mq.publish_message(queue_name, task_data)
        return True
    except Exception as e:
        logger.error(f"Failed to publish task to {queue_name}: {e}")
        return False

def setup_queues():
    """Setup all required queues"""
    queues = [
        Queues.REPORT_GENERATION,
        Queues.EMAIL_NOTIFICATIONS,
        Queues.CREDIT_SCORING,
        Queues.DOCUMENT_PROCESSING,
        Queues.ANALYTICS_CALCULATION,
        Queues.PAYMENT_PROCESSING,
        Queues.AUDIT_LOGGING
    ]

    try:
        mq.connect()
        for queue in queues:
            mq.declare_queue(queue)
        logger.info("All queues setup successfully")
    except Exception as e:
        logger.error(f"Failed to setup queues: {e}")
    finally:
        mq.disconnect()
EOF

# Create shared circuit breaker utility
cat > shared/utils/circuit_breaker.py << 'EOF'
"""
Circuit breaker pattern implementation for NexaFi services
"""
import time
import threading
from enum import Enum
from typing import Callable, Any
from functools import wraps
from ..config.infrastructure import InfrastructureConfig

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    """Circuit breaker implementation"""

    def __init__(self, failure_threshold: int = None, recovery_timeout: int = None):
        self.failure_threshold = failure_threshold or InfrastructureConfig.CIRCUIT_BREAKER_FAILURE_THRESHOLD
        self.recovery_timeout = recovery_timeout or InfrastructureConfig.CIRCUIT_BREAKER_RECOVERY_TIMEOUT

        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self.lock = threading.Lock()

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        with self.lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                else:
                    raise Exception("Circuit breaker is OPEN")

            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except Exception as e:
                self._on_failure()
                raise e

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        return (time.time() - self.last_failure_time) >= self.recovery_timeout

    def _on_success(self):
        """Handle successful call"""
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

def circuit_breaker(failure_threshold: int = None, recovery_timeout: int = None):
    """Decorator for circuit breaker protection"""
    def decorator(func):
        breaker = CircuitBreaker(failure_threshold, recovery_timeout)

        @wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)

        return wrapper
    return decorator
EOF

# Create shared logging utility
cat > shared/utils/logging.py << 'EOF'
"""
Shared logging utilities for NexaFi services
"""
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
from ..config.infrastructure import InfrastructureConfig

class StructuredLogger:
    """Structured logging for better log analysis"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.logger = logging.getLogger(service_name)
        self.logger.setLevel(getattr(logging, InfrastructureConfig.LOG_LEVEL))

        # Create formatter
        formatter = logging.Formatter(InfrastructureConfig.LOG_FORMAT)

        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # Create file handler
        file_handler = logging.FileHandler(f'logs/{service_name}.log')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def _create_log_entry(self, level: str, message: str,
                         extra_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create structured log entry"""
        entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'service': self.service_name,
            'level': level,
            'message': message
        }

        if extra_data:
            entry.update(extra_data)

        return entry

    def info(self, message: str, **kwargs):
        """Log info message"""
        entry = self._create_log_entry('INFO', message, kwargs)
        self.logger.info(json.dumps(entry))

    def warning(self, message: str, **kwargs):
        """Log warning message"""
        entry = self._create_log_entry('WARNING', message, kwargs)
        self.logger.warning(json.dumps(entry))

    def error(self, message: str, **kwargs):
        """Log error message"""
        entry = self._create_log_entry('ERROR', message, kwargs)
        self.logger.error(json.dumps(entry))

    def debug(self, message: str, **kwargs):
        """Log debug message"""
        entry = self._create_log_entry('DEBUG', message, kwargs)
        self.logger.debug(json.dumps(entry))

    def critical(self, message: str, **kwargs):
        """Log critical message"""
        entry = self._create_log_entry('CRITICAL', message, kwargs)
        self.logger.critical(json.dumps(entry))

def get_logger(service_name: str) -> StructuredLogger:
    """Get structured logger for service"""
    return StructuredLogger(service_name)
EOF

echo "✅ Infrastructure setup files created successfully!"
echo ""
echo "📁 Created infrastructure components:"
echo "   - Redis configuration"
echo "   - Docker Compose for infrastructure services"
echo "   - Shared utilities (cache, message queue, circuit breaker, logging)"
echo "   - Configuration management"
echo ""
echo "🚀 To start infrastructure services:"
echo "   cd infrastructure && ./start-infrastructure.sh"
echo ""
echo "🛑 To stop infrastructure services:"
echo "   cd infrastructure && ./stop-infrastructure.sh"
