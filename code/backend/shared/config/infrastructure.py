"""
Shared infrastructure configuration for NexaFi services
"""

import os
from typing import Any, Dict


class InfrastructureConfig:
    """Infrastructure configuration settings"""

    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
    REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
    RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
    RABBITMQ_USER = os.getenv("RABBITMQ_USER", "nexafi")
    RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "nexafi123")
    RABBITMQ_VHOST = os.getenv("RABBITMQ_VHOST", "/")
    RABBITMQ_URL = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}{RABBITMQ_VHOST}"
    ELASTICSEARCH_HOST = os.getenv("ELASTICSEARCH_HOST", "localhost")
    ELASTICSEARCH_PORT = int(os.getenv("ELASTICSEARCH_PORT", 9200))
    ELASTICSEARCH_URL = f"http://{ELASTICSEARCH_HOST}:{ELASTICSEARCH_PORT}"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    CACHE_DEFAULT_TIMEOUT = int(os.getenv("CACHE_DEFAULT_TIMEOUT", 300))
    CACHE_KEY_PREFIX = os.getenv("CACHE_KEY_PREFIX", "nexafi:")
    RATE_LIMIT_STORAGE_URL = REDIS_URL
    RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "100 per hour")
    CIRCUIT_BREAKER_FAILURE_THRESHOLD = int(
        os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", 5)
    )
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT = int(
        os.getenv("CIRCUIT_BREAKER_RECOVERY_TIMEOUT", 60)
    )

    @classmethod
    def get_redis_config(cls: Any) -> Dict[str, Any]:
        """Get Redis connection configuration"""
        config = {
            "host": cls.REDIS_HOST,
            "port": cls.REDIS_PORT,
            "db": cls.REDIS_DB,
            "decode_responses": True,
        }
        if cls.REDIS_PASSWORD:
            config["password"] = cls.REDIS_PASSWORD
        return config

    @classmethod
    def get_rabbitmq_config(cls: Any) -> Dict[str, Any]:
        """Get RabbitMQ connection configuration"""
        return {
            "host": cls.RABBITMQ_HOST,
            "port": cls.RABBITMQ_PORT,
            "virtual_host": cls.RABBITMQ_VHOST,
            "credentials": {
                "username": cls.RABBITMQ_USER,
                "password": cls.RABBITMQ_PASSWORD,
            },
        }

    @classmethod
    def get_elasticsearch_config(cls: Any) -> Dict[str, Any]:
        """Get Elasticsearch connection configuration"""
        return {
            "hosts": [cls.ELASTICSEARCH_URL],
            "timeout": 30,
            "max_retries": 3,
            "retry_on_timeout": True,
        }
