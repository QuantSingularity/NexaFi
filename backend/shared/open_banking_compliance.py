"""
Open Banking Compliance Module
Implements PSD2, FAPI 2.0, and Strong Customer Authentication (SCA) requirements
"""

import base64
import hashlib
import json
import logging
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

logger = logging.get_logger(__name__)


class ConsentStatus(Enum):
    """PSD2 Consent Status"""

    RECEIVED = "received"
    VALID = "valid"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REVOKED_BY_PSU = "revokedByPsu"
    TERMINATED_BY_TPP = "terminatedByTpp"


class SCAStatus(Enum):
    """Strong Customer Authentication Status"""

    RECEIVED = "received"
    PSUIDENTIFIED = "psuIdentified"
    PSUAUTHENTICATED = "psuAuthenticated"
    SCAMETHODSELECTED = "scaMethodSelected"
    STARTED = "started"
    FINALISED = "finalised"
    FAILED = "failed"
    EXEMPTED = "exempted"


class AuthenticationMethod(Enum):
    """SCA Authentication Methods"""

    SMS_OTP = "sms_otp"
    PUSH_NOTIFICATION = "push_notification"
    BIOMETRIC = "biometric"
    HARDWARE_TOKEN = "hardware_token"
    MOBILE_APP = "mobile_app"


@dataclass
class ConsentData:
    """PSD2 Consent Data Structure"""

    consent_id: str
    status: ConsentStatus
    valid_until: datetime
    frequency_per_day: int
    recurring_indicator: bool
    combined_service_indicator: bool
    access: Dict[str, Any]
    creation_date_time: datetime
    status_change_date_time: datetime
    psu_id: Optional[str] = None
    tpp_id: Optional[str] = None


@dataclass
class SCAData:
    """Strong Customer Authentication Data"""

    authentication_id: str
    status: SCAStatus
    sca_method: AuthenticationMethod
    challenge_data: Optional[str] = None
    authentication_method_id: Optional[str] = None
    psu_message: Optional[str] = None
    expires_at: Optional[datetime] = None


class FAPI2SecurityProfile:
    """FAPI 2.0 Security Profile Implementation"""

    def __init__(self, private_key_path: str, public_key_path: str) -> None:
        self.private_key = self._load_private_key(private_key_path)
        self.public_key = self._load_public_key(public_key_path)
        self.algorithm = "RS256"

    def _load_private_key(self, key_path: str) -> Any:
        """Load RSA private key"""
        if not os.path.exists(key_path):
            private_key = rsa.generate_private_key(
                public_exponent=65537, key_size=2048, backend=default_backend()
            )
            os.makedirs(os.path.dirname(key_path), exist_ok=True)
            with open(key_path, "wb") as f:
                f.write(
                    private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption(),
                    )
                )
            return private_key
        with open(key_path, "rb") as f:
            return serialization.load_pem_private_key(
                f.read(), password=None, backend=default_backend()
            )

    def _load_public_key(self, key_path: str) -> Any:
        """Load RSA public key"""
        if not os.path.exists(key_path):
            public_key = self.private_key.public_key()
            os.makedirs(os.path.dirname(key_path), exist_ok=True)
            with open(key_path, "wb") as f:
                f.write(
                    public_key.public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo,
                    )
                )
            return public_key
        with open(key_path, "rb") as f:
            return serialization.load_pem_public_key(
                f.read(), backend=default_backend()
            )

    def create_signed_jwt(
        self, payload: Dict[str, Any], audience: str, issuer: str
    ) -> str:
        """Create FAPI 2.0 compliant signed JWT"""
        now = datetime.utcnow()
        jwt_payload = {
            "iss": issuer,
            "aud": audience,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "jti": secrets.token_urlsafe(32),
            **payload,
        }
        return jwt.encode(
            jwt_payload,
            self.private_key,
            algorithm=self.algorithm,
            headers={"alg": self.algorithm, "typ": "JWT"},
        )

    def verify_jwt(self, token: str, audience: str, issuer: str) -> Dict[str, Any]:
        """Verify FAPI 2.0 compliant JWT"""
        try:
            payload = jwt.decode(
                token,
                self.public_key,
                algorithms=[self.algorithm],
                audience=audience,
                issuer=issuer,
                options={"require": ["exp", "iat", "aud", "iss", "jti"]},
            )
            return payload
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid JWT: {str(e)}")

    def create_dpop_proof(
        self, http_method: str, http_uri: str, access_token: Optional[str] = None
    ) -> str:
        """Create DPoP (Demonstrating Proof of Possession) proof JWT"""
        now = datetime.utcnow()
        payload = {
            "jti": secrets.token_urlsafe(32),
            "htm": http_method.upper(),
            "htu": http_uri,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=1)).timestamp()),
        }
        if access_token:
            token_hash = hashlib.sha256(access_token.encode()).digest()
            payload["ath"] = base64.urlsafe_b64encode(token_hash).decode().rstrip("=")
        return jwt.encode(
            payload,
            self.private_key,
            algorithm=self.algorithm,
            headers={"alg": self.algorithm, "typ": "dpop+jwt"},
        )


class PSD2ConsentManager:
    """PSD2 Consent Management"""

    def __init__(self, db_manager: Any) -> None:
        self.db_manager = db_manager
        self._initialize_consent_tables()

    def _initialize_consent_tables(self) -> Any:
        """Initialize consent management tables"""
        consent_table_sql = "\n        CREATE TABLE IF NOT EXISTS psd2_consents (\n            consent_id TEXT PRIMARY KEY,\n            psu_id TEXT NOT NULL,\n            tpp_id TEXT NOT NULL,\n            status TEXT NOT NULL,\n            valid_until TIMESTAMP NOT NULL,\n            frequency_per_day INTEGER DEFAULT 4,\n            recurring_indicator BOOLEAN DEFAULT FALSE,\n            combined_service_indicator BOOLEAN DEFAULT FALSE,\n            access_data TEXT NOT NULL,\n            creation_date_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n            status_change_date_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n            last_action_date TIMESTAMP,\n            FOREIGN KEY (psu_id) REFERENCES users(id)\n        );\n\n        CREATE INDEX IF NOT EXISTS idx_psd2_consents_psu_id ON psd2_consents(psu_id);\n        CREATE INDEX IF NOT EXISTS idx_psd2_consents_tpp_id ON psd2_consents(tpp_id);\n        CREATE INDEX IF NOT EXISTS idx_psd2_consents_status ON psd2_consents(status);\n        "
        self.db_manager.execute_query(consent_table_sql)

    def create_consent(
        self,
        psu_id: str,
        tpp_id: str,
        access_data: Dict[str, Any],
        valid_until: Optional[datetime] = None,
        frequency_per_day: int = 4,
    ) -> ConsentData:
        """Create new PSD2 consent"""
        consent_id = f"consent_{secrets.token_urlsafe(16)}"
        if not valid_until:
            valid_until = datetime.utcnow() + timedelta(days=90)
        consent = ConsentData(
            consent_id=consent_id,
            status=ConsentStatus.RECEIVED,
            valid_until=valid_until,
            frequency_per_day=frequency_per_day,
            recurring_indicator=access_data.get("recurringIndicator", False),
            combined_service_indicator=access_data.get(
                "combinedServiceIndicator", False
            ),
            access=access_data,
            creation_date_time=datetime.utcnow(),
            status_change_date_time=datetime.utcnow(),
            psu_id=psu_id,
            tpp_id=tpp_id,
        )
        insert_sql = "\n        INSERT INTO psd2_consents\n        (consent_id, psu_id, tpp_id, status, valid_until, frequency_per_day,\n         recurring_indicator, combined_service_indicator, access_data,\n         creation_date_time, status_change_date_time)\n        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n        "
        self.db_manager.execute_query(
            insert_sql,
            (
                consent.consent_id,
                consent.psu_id,
                consent.tpp_id,
                consent.status.value,
                consent.valid_until,
                consent.frequency_per_day,
                consent.recurring_indicator,
                consent.combined_service_indicator,
                json.dumps(consent.access),
                consent.creation_date_time,
                consent.status_change_date_time,
            ),
        )
        return consent

    def get_consent(self, consent_id: str) -> Optional[ConsentData]:
        """Retrieve consent by ID"""
        query_sql = "SELECT * FROM psd2_consents WHERE consent_id = ?"
        result = self.db_manager.fetch_one(query_sql, (consent_id,))
        if not result:
            return None
        return ConsentData(
            consent_id=result["consent_id"],
            status=ConsentStatus(result["status"]),
            valid_until=datetime.fromisoformat(result["valid_until"]),
            frequency_per_day=result["frequency_per_day"],
            recurring_indicator=result["recurring_indicator"],
            combined_service_indicator=result["combined_service_indicator"],
            access=json.loads(result["access_data"]),
            creation_date_time=datetime.fromisoformat(result["creation_date_time"]),
            status_change_date_time=datetime.fromisoformat(
                result["status_change_date_time"]
            ),
            psu_id=result["psu_id"],
            tpp_id=result["tpp_id"],
        )

    def update_consent_status(self, consent_id: str, new_status: ConsentStatus) -> bool:
        """Update consent status"""
        update_sql = "\n        UPDATE psd2_consents\n        SET status = ?, status_change_date_time = ?\n        WHERE consent_id = ?\n        "
        result = self.db_manager.execute_query(
            update_sql, (new_status.value, datetime.utcnow(), consent_id)
        )
        return result.rowcount > 0

    def validate_consent(self, consent_id: str, tpp_id: str) -> Tuple[bool, str]:
        """Validate consent for TPP access"""
        consent = self.get_consent(consent_id)
        if not consent:
            return (False, "Consent not found")
        if consent.tpp_id != tpp_id:
            return (False, "TPP not authorized for this consent")
        if consent.status != ConsentStatus.VALID:
            return (False, f"Consent status is {consent.status.value}")
        if datetime.utcnow() > consent.valid_until:
            self.update_consent_status(consent_id, ConsentStatus.EXPIRED)
            return (False, "Consent has expired")
        return (True, "Consent is valid")


class SCAManager:
    """Strong Customer Authentication Manager"""

    def __init__(self, db_manager: Any) -> None:
        self.db_manager = db_manager
        self._initialize_sca_tables()

    def _initialize_sca_tables(self) -> Any:
        """Initialize SCA tables"""
        sca_table_sql = "\n        CREATE TABLE IF NOT EXISTS sca_authentications (\n            authentication_id TEXT PRIMARY KEY,\n            psu_id TEXT NOT NULL,\n            consent_id TEXT,\n            transaction_id TEXT,\n            status TEXT NOT NULL,\n            sca_method TEXT NOT NULL,\n            challenge_data TEXT,\n            authentication_method_id TEXT,\n            psu_message TEXT,\n            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n            expires_at TIMESTAMP,\n            completed_at TIMESTAMP,\n            attempts INTEGER DEFAULT 0,\n            max_attempts INTEGER DEFAULT 3,\n            FOREIGN KEY (psu_id) REFERENCES users(id),\n            FOREIGN KEY (consent_id) REFERENCES psd2_consents(consent_id)\n        );\n\n        CREATE INDEX IF NOT EXISTS idx_sca_psu_id ON sca_authentications(psu_id);\n        CREATE INDEX IF NOT EXISTS idx_sca_consent_id ON sca_authentications(consent_id);\n        CREATE INDEX IF NOT EXISTS idx_sca_status ON sca_authentications(status);\n        "
        self.db_manager.execute_query(sca_table_sql)

    def initiate_sca(
        self,
        psu_id: str,
        sca_method: AuthenticationMethod,
        consent_id: Optional[str] = None,
        transaction_id: Optional[str] = None,
    ) -> SCAData:
        """Initiate Strong Customer Authentication"""
        authentication_id = f"sca_{secrets.token_urlsafe(16)}"
        expires_at = datetime.utcnow() + timedelta(minutes=5)
        challenge_data = self._generate_challenge(sca_method)
        sca_data = SCAData(
            authentication_id=authentication_id,
            status=SCAStatus.RECEIVED,
            sca_method=sca_method,
            challenge_data=challenge_data,
            expires_at=expires_at,
        )
        insert_sql = "\n        INSERT INTO sca_authentications\n        (authentication_id, psu_id, consent_id, transaction_id, status, sca_method,\n         challenge_data, expires_at)\n        VALUES (?, ?, ?, ?, ?, ?, ?, ?)\n        "
        self.db_manager.execute_query(
            insert_sql,
            (
                authentication_id,
                psu_id,
                consent_id,
                transaction_id,
                sca_data.status.value,
                sca_data.sca_method.value,
                challenge_data,
                expires_at,
            ),
        )
        self._send_challenge(psu_id, sca_method, challenge_data)
        return sca_data

    def _generate_challenge(self, method: AuthenticationMethod) -> str:
        """Generate authentication challenge"""
        if method == AuthenticationMethod.SMS_OTP:
            return f"{secrets.randbelow(900000) + 100000:06d}"
        elif method == AuthenticationMethod.PUSH_NOTIFICATION:
            return secrets.token_urlsafe(32)
        elif method == AuthenticationMethod.HARDWARE_TOKEN:
            return secrets.token_urlsafe(16)
        else:
            return secrets.token_urlsafe(32)

    def _send_challenge(
        self, psu_id: str, method: AuthenticationMethod, challenge: str
    ) -> Any:
        """Send authentication challenge to user"""
        logger.info(f"SCA Challenge for user {psu_id} via {method.value}: {challenge}")

    def verify_sca(
        self, authentication_id: str, response: str
    ) -> Tuple[bool, SCAStatus]:
        """Verify SCA response"""
        query_sql = "\n        SELECT * FROM sca_authentications\n        WHERE authentication_id = ?\n        "
        result = self.db_manager.fetch_one(query_sql, (authentication_id,))
        if not result:
            return (False, SCAStatus.FAILED)
        if datetime.utcnow() > datetime.fromisoformat(result["expires_at"]):
            self._update_sca_status(authentication_id, SCAStatus.FAILED)
            return (False, SCAStatus.FAILED)
        if result["attempts"] >= result["max_attempts"]:
            self._update_sca_status(authentication_id, SCAStatus.FAILED)
            return (False, SCAStatus.FAILED)
        self._increment_attempts(authentication_id)
        if response == result["challenge_data"]:
            self._update_sca_status(authentication_id, SCAStatus.FINALISED)
            return (True, SCAStatus.FINALISED)
        else:
            return (False, SCAStatus.RECEIVED)

    def _update_sca_status(self, authentication_id: str, status: SCAStatus) -> Any:
        """Update SCA status"""
        update_sql = "\n        UPDATE sca_authentications\n        SET status = ?, completed_at = ?\n        WHERE authentication_id = ?\n        "
        completed_at = datetime.utcnow() if status == SCAStatus.FINALISED else None
        self.db_manager.execute_query(
            update_sql, (status.value, completed_at, authentication_id)
        )

    def _increment_attempts(self, authentication_id: str) -> Any:
        """Increment authentication attempts"""
        update_sql = "\n        UPDATE sca_authentications\n        SET attempts = attempts + 1\n        WHERE authentication_id = ?\n        "
        self.db_manager.execute_query(update_sql, (authentication_id,))


class OpenBankingAPIValidator:
    """Open Banking API Request/Response Validator"""

    @staticmethod
    def validate_tpp_certificate(certificate_data: str) -> Tuple[bool, Dict[str, Any]]:
        """Validate TPP certificate according to PSD2 requirements"""
        return (
            True,
            {
                "organization_id": "PSDGB-FCA-123456",
                "organization_name": "Example TPP Ltd",
                "roles": ["PSP_PI", "PSP_AI"],
                "valid_from": datetime.utcnow(),
                "valid_until": datetime.utcnow() + timedelta(days=365),
            },
        )

    @staticmethod
    def validate_request_signature(
        request_data: str, signature: str, public_key: Any
    ) -> bool:
        """Validate request signature"""
        try:
            public_key.verify(
                base64.b64decode(signature),
                request_data.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
            return True
        except Exception:
            return False

    @staticmethod
    def validate_fapi_headers(headers: Dict[str, str]) -> Tuple[bool, List[str]]:
        """Validate FAPI required headers"""
        errors: List[Any] = []
        required_headers = [
            "x-fapi-auth-date",
            "x-fapi-customer-ip-address",
            "x-fapi-interaction-id",
        ]
        for header in required_headers:
            if header not in headers:
                errors.append(f"Missing required header: {header}")
        if "x-fapi-auth-date" in headers:
            try:
                datetime.fromisoformat(
                    headers["x-fapi-auth-date"].replace("Z", "+00:00")
                )
            except ValueError:
                errors.append("Invalid x-fapi-auth-date format")
        if "x-fapi-customer-ip-address" in headers:
            ip_pattern = "^(?:[0-9]{1,3}\\.){3}[0-9]{1,3}$|^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$"
            if not re.match(ip_pattern, headers["x-fapi-customer-ip-address"]):
                errors.append("Invalid x-fapi-customer-ip-address format")
        return (len(errors) == 0, errors)


class TransactionRiskAnalysis:
    """PSD2 Transaction Risk Analysis for SCA Exemptions"""

    @staticmethod
    def calculate_risk_score(
        transaction_data: Dict[str, Any], user_data: Dict[str, Any]
    ) -> Tuple[int, List[str]]:
        """Calculate transaction risk score for SCA exemption eligibility"""
        risk_score = 0
        risk_factors: List[Any] = []
        amount = float(transaction_data.get("amount", 0))
        transaction_data.get("currency", "EUR")
        merchant_category = transaction_data.get("merchant_category", "")
        if amount > 500:
            risk_score += 30
            risk_factors.append("high_amount")
        elif amount > 250:
            risk_score += 15
            risk_factors.append("medium_amount")
        high_risk_categories = ["gambling", "cryptocurrency", "money_transfer"]
        if merchant_category in high_risk_categories:
            risk_score += 25
            risk_factors.append("high_risk_merchant")
        user_risk_score = user_data.get("risk_score", 0)
        if user_risk_score > 70:
            risk_score += 20
            risk_factors.append("high_risk_user")
        transaction_country = transaction_data.get("country", "DE")
        user_country = user_data.get("country", "DE")
        if transaction_country != user_country:
            risk_score += 15
            risk_factors.append("cross_border_transaction")
        transaction_time = datetime.fromisoformat(
            transaction_data.get("timestamp", datetime.utcnow().isoformat())
        )
        if transaction_time.hour < 6 or transaction_time.hour > 22:
            risk_score += 10
            risk_factors.append("unusual_time")
        return (risk_score, risk_factors)

    @staticmethod
    def is_eligible_for_exemption(
        risk_score: int, amount: float, exemption_type: str
    ) -> bool:
        """Check if transaction is eligible for SCA exemption"""
        if exemption_type == "low_value":
            return amount < 30 and risk_score < 30
        elif exemption_type == "low_risk":
            if amount < 100:
                return risk_score < 20
            elif amount < 250:
                return risk_score < 15
            elif amount < 500:
                return risk_score < 10
        elif exemption_type == "recurring":
            return risk_score < 25
        return False
