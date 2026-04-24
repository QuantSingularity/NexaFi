"""
Shared message queue utilities for NexaFi services
"""

import json
import logging
from typing import Any, Callable, Dict, Optional

import pika

from ..config.infrastructure import InfrastructureConfig

logger = logging.getLogger(__name__)


class MessageQueue:
    """RabbitMQ message queue manager"""

    def __init__(self) -> None:
        self.connection = None
        self.channel = None
        self.config = InfrastructureConfig.get_rabbitmq_config()

    def connect(self) -> object:
        """Establish connection to RabbitMQ"""
        try:
            credentials = pika.PlainCredentials(
                self.config["credentials"]["username"],
                self.config["credentials"]["password"],
            )
            parameters = pika.ConnectionParameters(
                host=self.config["host"],
                port=self.config["port"],
                virtual_host=self.config["virtual_host"],
                credentials=credentials,
            )
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            logger.info("Connected to RabbitMQ")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    def disconnect(self) -> object:
        """Close connection to RabbitMQ"""
        if self.connection and (not self.connection.is_closed):
            self.connection.close()
            logger.info("Disconnected from RabbitMQ")

    def declare_queue(self, queue_name: str, durable: bool = True) -> object:
        """Declare a queue"""
        if not self.channel:
            self.connect()
        self.channel.queue_declare(queue=queue_name, durable=durable)
        logger.info(f"Declared queue: {queue_name}")

    def declare_exchange(
        self, exchange_name: str, exchange_type: str = "direct"
    ) -> object:
        """Declare an exchange"""
        if not self.channel:
            self.connect()
        self.channel.exchange_declare(
            exchange=exchange_name, exchange_type=exchange_type, durable=True
        )
        logger.info(f"Declared exchange: {exchange_name}")

    def publish_message(
        self,
        queue_name: str,
        message: Dict[str, Any],
        exchange: str = "",
        routing_key: Optional[str] = None,
    ) -> object:
        """Publish a message to a queue"""
        if not self.channel:
            self.connect()
        routing_key = routing_key or queue_name
        self.channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2, content_type="application/json"
            ),
        )
        logger.info(f"Published message to {queue_name}: {message}")

    def consume_messages(self, queue_name: str, callback: Callable) -> object:
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

        self.channel.basic_consume(queue=queue_name, on_message_callback=wrapper)
        logger.info(f"Started consuming from {queue_name}")
        self.channel.start_consuming()


mq = MessageQueue()


class Queues:
    REPORT_GENERATION = "report_generation"
    EMAIL_NOTIFICATIONS = "email_notifications"
    CREDIT_SCORING = "credit_scoring"
    DOCUMENT_PROCESSING = "document_processing"
    ANALYTICS_CALCULATION = "analytics_calculation"
    PAYMENT_PROCESSING = "payment_processing"
    AUDIT_LOGGING = "audit_logging"


def publish_task(queue_name: str, task_data: Dict[str, Any]) -> object:
    """Publish a task to a queue"""
    try:
        mq.publish_message(queue_name, task_data)
        return True
    except Exception as e:
        logger.error(f"Failed to publish task to {queue_name}: {e}")
        return False


def setup_queues() -> object:
    """Setup all required queues"""
    queues = [
        Queues.REPORT_GENERATION,
        Queues.EMAIL_NOTIFICATIONS,
        Queues.CREDIT_SCORING,
        Queues.DOCUMENT_PROCESSING,
        Queues.ANALYTICS_CALCULATION,
        Queues.PAYMENT_PROCESSING,
        Queues.AUDIT_LOGGING,
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
