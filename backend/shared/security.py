import base64
import json
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional, Tuple

import pyotp
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from nexafi_logging.logger import get_logger

logger = get_logger(__name__)


class SecurityLevel(Enum):
    """Security levels for different operations"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatLevel(Enum):
    """Threat assessment levels"""

    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityEventType(Enum):
    """Types of security events"""

    LOGIN_ATTEMPT = "login_attempt"
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    PASSWORD_CHANGE = "password_change"
    ACCOUNT_LOCKOUT = "account_lockout"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    FRAUD_DETECTION = "fraud_detection"
    DATA_ACCESS = "data_access"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    SECURITY_VIOLATION = "security_violation"


@dataclass
class SecurityEvent:
    """Security event data structure"""

    event_type: SecurityEventType
    user_id: Optional[str]
    ip_address: str
    user_agent: str
    timestamp: datetime
    details: Dict[str, Any]
    threat_level: ThreatLevel
    session_id: Optional[str] = None
    location: Optional[str] = None


class RobustEncryption:
    """Robust encryption utilities for sensitive data"""

    def __init__(self, master_key: Optional[str] = None) -> None:
        if master_key:
            self.master_key = master_key.encode()
        else:
            self.master_key = os.environ.get(
                "MASTER_ENCRYPTION_KEY", "default-key-change-in-production"
            ).encode()

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"nexafi_salt_2024",
            iterations=100000,
            backend=default_backend(),
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.master_key))
        self.fernet = Fernet(key)

    def encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive data with timestamp"""
        timestamp = int(time.time())
        data_with_timestamp = f"{timestamp}:{data}"
        encrypted = self.fernet.encrypt(data_with_timestamp.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data and verify timestamp"""
        try:
            decoded = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self.fernet.decrypt(decoded).decode()
            timestamp_str, data = decrypted.split(":", 1)

            # Check if data is too old (e.g., 24 hours)
            timestamp = int(timestamp_str)
            if int(time.time()) - timestamp > 86400:
                logger.warning("Decrypted data has expired")

            return data
        except Exception as e:
            logger.error(f"Decryption failed: {str(e)}")
            raise ValueError("Invalid or expired encrypted data")


class FraudDetectionEngine:
    """Engine for detecting fraudulent activities"""

    def __init__(self, db_manager: Any) -> None:
        self.db_manager = db_manager
        self.risk_thresholds = {
            "velocity": 10,  # transactions per minute
            "amount": 10000.0,  # single transaction limit
            "location": True,  # check for impossible travel
        }
        self._initialize_fraud_tables()

    def _initialize_fraud_tables(self) -> Any:
        """Initialize fraud detection tables"""
        statements = [
            """
            CREATE TABLE IF NOT EXISTS fraud_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                alert_type TEXT NOT NULL,
                risk_score REAL NOT NULL,
                details TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS transaction_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                pattern_type TEXT NOT NULL,
                pattern_data TEXT NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_fraud_alerts_user_id ON fraud_alerts(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_fraud_alerts_status ON fraud_alerts(status)",
            "CREATE INDEX IF NOT EXISTS idx_transaction_patterns_user_id ON transaction_patterns(user_id)",
        ]
        for statement in statements:
            self.db_manager.execute_query(statement)

    def analyze_transaction(
        self, user_id: str, transaction_data: Dict[str, Any]
    ) -> float:
        """Analyze transaction for fraud risk"""
        risk_score = 0.0

        # Velocity check
        if self._check_velocity(user_id):
            risk_score += 0.4

        # Amount check
        if float(transaction_data.get("amount", 0)) > self.risk_thresholds["amount"]:
            risk_score += 0.3

        # Location check
        if self._check_location_anomaly(user_id, transaction_data.get("location")):
            risk_score += 0.5

        if risk_score >= 0.7:
            self._create_fraud_alert(
                user_id, "high_risk_transaction", risk_score, transaction_data
            )

        return min(risk_score, 1.0)

    def _check_velocity(self, user_id: str) -> bool:
        """Check transaction velocity for user"""
        # Implementation placeholder
        return False

    def _check_location_anomaly(
        self, user_id: str, current_location: Optional[str]
    ) -> bool:
        """Check for impossible travel or suspicious location"""
        # Implementation placeholder
        return False

    def _create_fraud_alert(
        self, user_id: str, alert_type: str, risk_score: float, details: Dict[str, Any]
    ) -> Any:
        """Create a new fraud alert in database"""
        insert_sql = """
        INSERT INTO fraud_alerts (user_id, alert_type, risk_score, details)
        VALUES (?, ?, ?, ?)
        """
        self.db_manager.execute_query(
            insert_sql, (user_id, alert_type, risk_score, json.dumps(details))
        )


class SecurityManager:
    """Centralized security management system"""

    def __init__(self, db_manager: Any) -> None:
        self.db_manager = db_manager
        self.encryption = RobustEncryption()
        self.fraud_engine = FraudDetectionEngine(db_manager)
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.failed_attempts = defaultdict(lambda: deque(maxlen=5))
        self._lock = threading.Lock()
        self._initialize_monitoring_tables()

    def _initialize_monitoring_tables(self) -> Any:
        """Initialize security monitoring tables"""
        statements = [
            """
            CREATE TABLE IF NOT EXISTS security_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                user_id TEXT,
                ip_address TEXT NOT NULL,
                user_agent TEXT,
                session_id TEXT,
                threat_level TEXT NOT NULL,
                details TEXT NOT NULL,
                location TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS threat_indicators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                indicator_type TEXT NOT NULL,
                indicator_value TEXT NOT NULL,
                threat_level TEXT NOT NULL,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                occurrence_count INTEGER DEFAULT 1,
                status TEXT DEFAULT 'active'
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS secure_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                user_id TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                user_agent TEXT,
                device_fingerprint TEXT,
                security_level TEXT NOT NULL,
                mfa_verified BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                session_data TEXT
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_security_events_user_id ON security_events(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_security_events_ip_address ON security_events(ip_address)",
            "CREATE INDEX IF NOT EXISTS idx_security_events_created_at ON security_events(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_threat_indicators_value ON threat_indicators(indicator_value)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON secure_sessions(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON secure_sessions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON secure_sessions(expires_at)",
        ]
        for statement in statements:
            self.db_manager.execute_query(statement)

    def create_session(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        device_fingerprint: Optional[str] = None,
        security_level: SecurityLevel = SecurityLevel.MEDIUM,
    ) -> str:
        """Create a new secure session"""
        session_id = secrets.token_urlsafe(32)

        # Set expiration based on security level
        if security_level == SecurityLevel.LOW:
            expires_at = datetime.utcnow() + timedelta(days=7)
        elif security_level == SecurityLevel.MEDIUM:
            expires_at = datetime.utcnow() + timedelta(hours=24)
        elif security_level == SecurityLevel.HIGH:
            expires_at = datetime.utcnow() + timedelta(hours=8)
        elif security_level == SecurityLevel.CRITICAL:
            expires_at = datetime.utcnow() + timedelta(hours=2)
        else:
            expires_at = datetime.utcnow() + timedelta(hours=24)

        session_data: Dict[str, Any] = {
            "created_ip": ip_address,
            "security_level": security_level.value,
            "permissions": [],
        }

        insert_sql = """
        INSERT INTO secure_sessions
        (session_id, user_id, ip_address, user_agent, device_fingerprint,
         expires_at, security_level, session_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.db_manager.execute_query(
            insert_sql,
            (
                session_id,
                user_id,
                ip_address,
                user_agent,
                device_fingerprint,
                expires_at,
                security_level.value,
                self.encryption.encrypt_sensitive_data(json.dumps(session_data)),
            ),
        )

        with self._lock:
            self.active_sessions[session_id] = {
                "user_id": user_id,
                "expires_at": expires_at,
                "security_level": security_level,
                "mfa_verified": False,
            }

        return session_id

    def validate_session(
        self,
        session_id: str,
        ip_address: Optional[str] = None,
        require_mfa: bool = False,
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """Validate session with security checks"""
        with self._lock:
            if session_id in self.active_sessions:
                cached_session = self.active_sessions[session_id]
                if datetime.utcnow() > cached_session["expires_at"]:
                    del self.active_sessions[session_id]
                    return (False, None, {})

        query_sql = """
        SELECT user_id, ip_address, expires_at, is_active, security_level,
               mfa_verified, session_data, device_fingerprint
        FROM secure_sessions
        WHERE session_id = ? AND is_active = 1
        """
        result = self.db_manager.fetch_one(query_sql, (session_id,))

        if not result:
            return (False, None, {})

        expires_at = datetime.fromisoformat(result["expires_at"])
        if datetime.utcnow() > expires_at:
            self.invalidate_session(session_id)
            return (False, None, {})

        if ip_address and result["ip_address"] != ip_address:
            logger.warning(
                f"Session IP mismatch: {result['ip_address']} vs {ip_address}"
            )
            # Could trigger security event here

        if require_mfa and (not result["mfa_verified"]):
            return (False, result["user_id"], {"requires_mfa": True})

        try:
            session_data = json.loads(
                self.encryption.decrypt_sensitive_data(result["session_data"])
            )
        except Exception:
            session_data = {}

        self._update_session_activity(session_id)

        return (
            True,
            result["user_id"],
            {
                "security_level": result["security_level"],
                "mfa_verified": result["mfa_verified"],
                "session_data": session_data,
            },
        )

    def mark_mfa_verified(self, session_id: str) -> Any:
        """Mark session as MFA verified"""
        update_sql = "UPDATE secure_sessions SET mfa_verified = 1 WHERE session_id = ?"
        self.db_manager.execute_query(update_sql, (session_id,))
        with self._lock:
            if session_id in self.active_sessions:
                self.active_sessions[session_id]["mfa_verified"] = True

    def invalidate_session(self, session_id: str) -> Any:
        """Invalidate session"""
        update_sql = "UPDATE secure_sessions SET is_active = 0 WHERE session_id = ?"
        self.db_manager.execute_query(update_sql, (session_id,))
        with self._lock:
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]

    def invalidate_all_user_sessions(self, user_id: str) -> Any:
        """Invalidate all sessions for a user"""
        update_sql = "UPDATE secure_sessions SET is_active = 0 WHERE user_id = ?"
        self.db_manager.execute_query(update_sql, (user_id,))
        with self._lock:
            to_remove = [
                sid
                for sid, data in self.active_sessions.items()
                if data["user_id"] == user_id
            ]
            for sid in to_remove:
                del self.active_sessions[sid]

    def _update_session_activity(self, session_id: str) -> Any:
        """Update session last activity timestamp"""
        update_sql = "UPDATE secure_sessions SET last_activity = ? WHERE session_id = ?"
        self.db_manager.execute_query(update_sql, (datetime.utcnow(), session_id))

    def cleanup_expired_sessions(self) -> Any:
        """Clean up expired sessions"""
        cutoff_time = datetime.utcnow()
        delete_sql = "DELETE FROM secure_sessions WHERE expires_at < ? OR is_active = 0"
        self.db_manager.execute_query(delete_sql, (cutoff_time,))

        with self._lock:
            expired_sessions = [
                sid
                for sid, data in self.active_sessions.items()
                if datetime.utcnow() > data["expires_at"]
            ]
            for sid in expired_sessions:
                del self.active_sessions[sid]

    def log_security_event(self, event: SecurityEvent) -> Any:
        """Log security event to database"""
        insert_sql = """
        INSERT INTO security_events
        (event_type, user_id, ip_address, user_agent, session_id,
         threat_level, details, location)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.db_manager.execute_query(
            insert_sql,
            (
                event.event_type.value,
                event.user_id,
                event.ip_address,
                event.user_agent,
                event.session_id,
                event.threat_level.value,
                json.dumps(event.details),
                event.location,
            ),
        )

        if event.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
            logger.warning(f"High threat security event: {event.event_type.value}")

    def generate_mfa_secret(self) -> str:
        """Generate a new MFA secret"""
        return pyotp.random_base32()

    def verify_mfa_token(self, secret: str, token: str) -> bool:
        """Verify MFA token"""
        totp = pyotp.TOTP(secret)
        return totp.verify(token)
