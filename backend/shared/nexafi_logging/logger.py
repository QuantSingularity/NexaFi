"""
Structured logging system for NexaFi
Implements comprehensive logging with correlation IDs and security event tracking
"""

import logging
import os
import sys
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from flask import g, has_request_context, request
from pythonjsonlogger import jsonlogger


class CorrelationIdFilter(logging.Filter):
    """Add correlation ID to log records"""

    def filter(self, record: Any) -> Any:
        correlation_id = None
        if has_request_context():
            correlation_id = getattr(g, "correlation_id", None)
            if not correlation_id:
                correlation_id = str(uuid.uuid4())
                g.correlation_id = correlation_id
        if not correlation_id:
            correlation_id = getattr(
                threading.current_thread(), "correlation_id", str(uuid.uuid4())
            )
        record.correlation_id = correlation_id
        return True


class SecurityFilter(logging.Filter):
    """Filter for security-related log events"""

    def filter(self, record: Any) -> Any:
        if has_request_context():
            record.ip_address = request.environ.get(
                "HTTP_X_FORWARDED_FOR", request.remote_addr
            )
            record.user_agent = request.headers.get("User-Agent", "")
            record.endpoint = request.endpoint
            record.method = request.method
            if hasattr(g, "current_user"):
                record.user_id = g.current_user.get("user_id")
                record.user_email = g.current_user.get("email")
                record.user_roles = g.current_user.get("roles", [])
        return True


class NexaFiFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for NexaFi logs"""

    def add_fields(self, log_record: Any, record: Any, message_dict: Any) -> Any:
        super().add_fields(log_record, record, message_dict)
        log_record["timestamp"] = datetime.now(timezone.utc).isoformat()
        log_record["service"] = os.environ.get("SERVICE_NAME", "unknown")
        log_record["version"] = os.environ.get("SERVICE_VERSION", "1.0.0")
        if has_request_context():
            log_record["request_id"] = getattr(g, "request_id", None)
            log_record["session_id"] = getattr(g, "session_id", None)
        if "level" not in log_record:
            log_record["level"] = record.levelname


class LoggerManager:
    """Centralized logger management for NexaFi"""

    def __init__(self) -> None:
        self.loggers = {}
        self.setup_root_logger()

    def setup_root_logger(self) -> Any:
        """Setup root logger configuration"""
        log_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = NexaFiFormatter(
            "%(timestamp)s %(level)s %(name)s %(correlation_id)s %(message)s"
        )
        console_handler.setFormatter(console_formatter)
        console_handler.addFilter(CorrelationIdFilter())
        console_handler.addFilter(SecurityFilter())
        file_handler = logging.FileHandler(f"{log_dir}/nexafi.log")
        file_handler.setLevel(logging.INFO)
        file_formatter = NexaFiFormatter(
            "%(timestamp)s %(level)s %(name)s %(correlation_id)s %(message)s %(ip_address)s %(user_id)s"
        )
        file_handler.setFormatter(file_formatter)
        file_handler.addFilter(CorrelationIdFilter())
        file_handler.addFilter(SecurityFilter())
        error_handler = logging.FileHandler(f"{log_dir}/error.log")
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        error_handler.addFilter(CorrelationIdFilter())
        error_handler.addFilter(SecurityFilter())
        security_handler = logging.FileHandler(f"{log_dir}/security.log")
        security_handler.setLevel(logging.WARNING)
        security_handler.setFormatter(file_formatter)
        security_handler.addFilter(CorrelationIdFilter())
        security_handler.addFilter(SecurityFilter())
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(error_handler)
        security_logger = logging.getLogger("security")
        security_logger.addHandler(security_handler)
        security_logger.setLevel(logging.WARNING)
        security_logger.propagate = False

    def get_logger(self, name: str) -> logging.Logger:
        """Get or create a logger with the specified name"""
        if name not in self.loggers:
            logger = logging.getLogger(name)
            self.loggers[name] = logger
        return self.loggers[name]

    def log_request_start(self, logger: logging.Logger) -> Any:
        """Log request start"""
        if has_request_context():
            logger.info(
                "Request started",
                extra={
                    "event_type": "request_start",
                    "method": request.method,
                    "path": request.path,
                    "query_string": request.query_string.decode(),
                    "content_length": request.content_length,
                },
            )

    def log_request_end(
        self, logger: logging.Logger, status_code: int, response_time: float
    ) -> Any:
        """Log request end"""
        if has_request_context():
            logger.info(
                "Request completed",
                extra={
                    "event_type": "request_end",
                    "status_code": status_code,
                    "response_time_ms": response_time * 1000,
                },
            )

    def log_security_event(
        self, event_type: str, message: str, details: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Log security event"""
        security_logger = logging.getLogger("security")
        security_logger.warning(
            message,
            extra={
                "event_type": f"security_{event_type}",
                "security_details": details or {},
            },
        )

    def log_financial_transaction(
        self,
        logger: logging.Logger,
        transaction_type: str,
        amount: str,
        currency: str,
        transaction_id: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Log financial transaction"""
        logger.info(
            f"Financial transaction: {transaction_type}",
            extra={
                "event_type": "financial_transaction",
                "transaction_type": transaction_type,
                "amount": amount,
                "currency": currency,
                "transaction_id": transaction_id,
                "transaction_details": details or {},
            },
        )

    def log_database_operation(
        self,
        logger: logging.Logger,
        operation: str,
        table: str,
        record_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Log database operation"""
        logger.info(
            f"Database operation: {operation} on {table}",
            extra={
                "event_type": "database_operation",
                "operation": operation,
                "table": table,
                "record_id": record_id,
                "db_details": details or {},
            },
        )

    def log_api_call(
        self,
        logger: logging.Logger,
        service: str,
        endpoint: str,
        method: str,
        status_code: int,
        response_time: float,
    ) -> Any:
        """Log external API call"""
        logger.info(
            f"External API call: {method} {service}{endpoint}",
            extra={
                "event_type": "external_api_call",
                "service": service,
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "response_time_ms": response_time * 1000,
            },
        )


logger_manager = LoggerManager()


def get_logger(name: str) -> logging.Logger:
    """Get logger instance"""
    return logger_manager.get_logger(name)


def log_security_event(
    event_type: str, message: str, details: Optional[Dict[str, Any]] = None
) -> Any:
    """Log security event"""
    logger_manager.log_security_event(event_type, message, details)


def log_financial_transaction(
    transaction_type: str,
    amount: str,
    currency: str,
    transaction_id: str,
    details: Optional[Dict[str, Any]] = None,
) -> Any:
    """Log financial transaction"""
    logger = get_logger("financial")
    logger_manager.log_financial_transaction(
        logger, transaction_type, amount, currency, transaction_id, details
    )


def setup_request_logging(app: Any) -> Any:
    """Setup request logging middleware for Flask app"""

    @app.before_request
    def before_request():
        g.request_start_time = datetime.now()
        g.request_id = str(uuid.uuid4())
        logger = get_logger("requests")
        logger_manager.log_request_start(logger)

    @app.after_request
    def after_request(response):
        if hasattr(g, "request_start_time"):
            response_time = (datetime.now() - g.request_start_time).total_seconds()
            logger = get_logger("requests")
            logger_manager.log_request_end(logger, response.status_code, response_time)
        return response

    return app


def log_function_call(
    logger_name: Optional[str] = None, log_args: bool = False, log_result: bool = False
) -> Any:
    """Decorator to log function calls"""

    def decorator(f):
        from functools import wraps

        @wraps(f)
        def decorated_function(*args, **kwargs):
            logger = get_logger(logger_name or f.__module__)
            log_data = {"function": f.__name__, "module": f.__module__}
            if log_args:
                log_data["args"] = str(args)
                log_data["kwargs"] = str(kwargs)
            logger.info(f"Function call: {f.__name__}", extra=log_data)
            try:
                result = f(*args, **kwargs)
                if log_result:
                    log_data["result"] = str(result)
                logger.info(f"Function completed: {f.__name__}", extra=log_data)
                return result
            except Exception as e:
                log_data["error"] = str(e)
                logger.error(f"Function failed: {f.__name__}", extra=log_data)
                raise

        return decorated_function

    return decorator
