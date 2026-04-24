"""
Comprehensive audit logging system for NexaFi
Implements immutable audit trails for financial transactions and system events
"""

import hashlib
import json
import logging
import queue
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of audit events"""

    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_REGISTRATION = "user_registration"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    ACCOUNT_CREATE = "account_create"
    ACCOUNT_UPDATE = "account_update"
    ACCOUNT_DELETE = "account_delete"
    TRANSACTION_CREATE = "transaction_create"
    TRANSACTION_UPDATE = "transaction_update"
    TRANSACTION_DELETE = "transaction_delete"
    JOURNAL_ENTRY_CREATE = "journal_entry_create"
    JOURNAL_ENTRY_POST = "journal_entry_post"
    JOURNAL_ENTRY_REVERSE = "journal_entry_reverse"
    PAYMENT_CREATE = "payment_create"
    PAYMENT_PROCESS = "payment_process"
    PAYMENT_FAIL = "payment_fail"
    PAYMENT_REFUND = "payment_refund"
    REPORT_GENERATE = "report_generate"
    REPORT_EXPORT = "report_export"
    SYSTEM_CONFIG_CHANGE = "system_config_change"
    SECURITY_VIOLATION = "security_violation"
    API_ACCESS = "api_access"
    DATA_EXPORT = "data_export"
    DATA_IMPORT = "data_import"
    DATA_DELETE = "data_delete"


class AuditSeverity(Enum):
    """Severity levels for audit events"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Audit event data structure"""

    event_id: str
    event_type: AuditEventType
    severity: AuditSeverity
    timestamp: datetime
    user_id: Optional[str]
    session_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    resource_type: Optional[str]
    resource_id: Optional[str]
    action: str
    details: Dict[str, Any]
    before_state: Optional[Dict[str, Any]]
    after_state: Optional[Dict[str, Any]]
    success: bool
    error_message: Optional[str]
    correlation_id: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert audit event to dictionary"""
        data = asdict(self)
        data["event_type"] = self.event_type.value
        data["severity"] = self.severity.value
        data["timestamp"] = self.timestamp.isoformat()
        return data

    def calculate_hash(self) -> str:
        """Calculate hash of audit event for integrity verification"""
        canonical_data = {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "action": self.action,
            "details": json.dumps(self.details, sort_keys=True),
            "success": self.success,
        }
        canonical_string = json.dumps(canonical_data, sort_keys=True)
        return hashlib.sha256(canonical_string.encode()).hexdigest()


class AuditLogger:
    """Audit logging system with integrity verification"""

    def __init__(self, storage_backend: object = None) -> None:
        self.storage_backend = storage_backend
        self.event_queue = queue.Queue()
        self.worker_thread = None
        self.running = False
        self.previous_hash = None
        self.start_worker()

    def start_worker(self) -> object:
        """Start background worker thread for processing audit events"""
        self.running = True
        self.worker_thread = threading.Thread(target=self._process_events, daemon=True)
        self.worker_thread.start()

    def stop_worker(self) -> object:
        """Stop background worker thread"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join()

    def _process_events(self) -> object:
        """Background worker to process audit events"""
        while self.running:
            try:
                event = self.event_queue.get(timeout=1)
                self._store_event(event)
                self.event_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.info(f"Error processing audit event: {e}")

    def _store_event(self, event: AuditEvent) -> object:
        """Store audit event with integrity chain"""
        event_hash = event.calculate_hash()
        if self.previous_hash:
            chain_hash = hashlib.sha256(
                (self.previous_hash + event_hash).encode()
            ).hexdigest()
        else:
            chain_hash = event_hash
        event_data = event.to_dict()
        event_data["event_hash"] = event_hash
        event_data["chain_hash"] = chain_hash
        event_data["previous_hash"] = self.previous_hash
        if self.storage_backend:
            self.storage_backend.store(event_data)
        else:
            self._write_to_file(event_data)
        self.previous_hash = chain_hash

    def _write_to_file(self, event_data: Dict[str, Any]) -> object:
        """Write audit event to file"""
        import os

        log_dir = os.environ.get(
            "AUDIT_LOG_DIR", os.path.join(os.path.expanduser("~"), "logs", "audit")
        )
        os.makedirs(log_dir, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(log_dir, f"audit_{date_str}.jsonl")
        with open(log_file, "a") as f:
            f.write(json.dumps(event_data) + "\n")

    def log_event(
        self,
        event_type: AuditEventType,
        action: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        severity: AuditSeverity = AuditSeverity.MEDIUM,
        correlation_id: Optional[str] = None,
    ) -> object:
        """Log an audit event"""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            severity=severity,
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            details=details or {},
            before_state=before_state,
            after_state=after_state,
            success=success,
            error_message=error_message,
            correlation_id=correlation_id,
        )
        self.event_queue.put(event)

    def log_user_action(
        self,
        event_type: AuditEventType,
        user_id: str,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> object:
        """Log user-related action"""
        self.log_event(
            event_type=event_type,
            action=action,
            user_id=user_id,
            resource_type="user",
            resource_id=user_id,
            details=details,
            **kwargs,
        )

    def log_financial_transaction(
        self,
        event_type: AuditEventType,
        user_id: str,
        transaction_id: str,
        amount: str,
        currency: str,
        details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> object:
        """Log financial transaction"""
        transaction_details = {
            "amount": amount,
            "currency": currency,
            **(details or {}),
        }
        self.log_event(
            event_type=event_type,
            action=f"financial_transaction_{event_type.value}",
            user_id=user_id,
            resource_type="transaction",
            resource_id=transaction_id,
            details=transaction_details,
            severity=AuditSeverity.HIGH,
            **kwargs,
        )

    def log_security_event(
        self,
        action: str,
        ip_address: str,
        details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> object:
        """Log security-related event"""
        self.log_event(
            event_type=AuditEventType.SECURITY_VIOLATION,
            action=action,
            ip_address=ip_address,
            details=details,
            severity=AuditSeverity.CRITICAL,
            **kwargs,
        )

    def log_api_access(
        self,
        user_id: Optional[str],
        endpoint: str,
        method: str,
        status_code: int,
        ip_address: str,
        user_agent: str,
        response_time: float,
        **kwargs,
    ) -> object:
        """Log API access"""
        details = {
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "response_time_ms": response_time * 1000,
        }
        self.log_event(
            event_type=AuditEventType.API_ACCESS,
            action=f"{method} {endpoint}",
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
            success=status_code < 400,
            severity=AuditSeverity.LOW,
            **kwargs,
        )


audit_logger = AuditLogger()


def audit_action(
    event_type: AuditEventType,
    action: str,
    resource_type: Optional[str] = None,
    severity: AuditSeverity = AuditSeverity.MEDIUM,
) -> object:
    """Decorator for automatic audit logging of function calls"""

    def decorator(f):
        from functools import wraps

        from flask import g, request

        @wraps(f)
        def decorated_function(*args, **kwargs):
            start_time = time.time()
            user_id = getattr(g, "current_user", {}).get("user_id")
            ip_address = request.environ.get(
                "HTTP_X_FORWARDED_FOR", request.remote_addr
            )
            user_agent = request.headers.get("User-Agent", "")
            try:
                result = f(*args, **kwargs)
                audit_logger.log_event(
                    event_type=event_type,
                    action=action,
                    user_id=user_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    resource_type=resource_type,
                    success=True,
                    severity=severity,
                    details={"execution_time_ms": (time.time() - start_time) * 1000},
                )
                return result
            except Exception as e:
                audit_logger.log_event(
                    event_type=event_type,
                    action=action,
                    user_id=user_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    resource_type=resource_type,
                    success=False,
                    error_message=str(e),
                    severity=AuditSeverity.HIGH,
                    details={"execution_time_ms": (time.time() - start_time) * 1000},
                )
                raise

        return decorated_function

    return decorator
