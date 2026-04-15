"""
Advanced Threat Detection Engine for NexaFi
Real-time threat detection, anomaly detection, and automated response system
"""

import json
import logging
import os
import re
import smtplib
import time
import warnings
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import redis
import requests
import slack_sdk
from prometheus_client import Counter, Histogram
from scipy import stats
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from twilio.rest import Client as TwilioClient

logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore")
Base = declarative_base()


class ThreatType(Enum):
    """Types of threats"""

    MALWARE = "malware"
    PHISHING = "phishing"
    BRUTE_FORCE = "brute_force"
    DDoS = "ddos"
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    CSRF = "csrf"
    DATA_EXFILTRATION = "data_exfiltration"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    LATERAL_MOVEMENT = "lateral_movement"
    ANOMALOUS_BEHAVIOR = "anomalous_behavior"
    INSIDER_THREAT = "insider_threat"
    APT = "apt"
    ZERO_DAY = "zero_day"


class Severity(Enum):
    """Threat severity levels"""

    CRITICAL = 5
    HIGH = 4
    MEDIUM = 3
    LOW = 2
    INFO = 1


class ResponseAction(Enum):
    """Automated response actions"""

    BLOCK_IP = "block_ip"
    BLOCK_USER = "block_user"
    QUARANTINE_DEVICE = "quarantine_device"
    ALERT_ADMIN = "alert_admin"
    LOG_ONLY = "log_only"
    RATE_LIMIT = "rate_limit"
    CHALLENGE_USER = "challenge_user"
    FORCE_LOGOUT = "force_logout"
    DISABLE_ACCOUNT = "disable_account"
    ISOLATE_NETWORK = "isolate_network"


@dataclass
class ThreatEvent:
    """Threat event data structure"""

    event_id: str
    threat_type: ThreatType
    severity: Severity
    confidence: float
    source_ip: str
    target_resource: str
    user_id: Optional[str]
    session_id: Optional[str]
    timestamp: datetime
    description: str
    indicators: Dict[str, Any]
    raw_data: Dict[str, Any]
    response_actions: List[ResponseAction]
    mitre_tactics: List[str]
    mitre_techniques: List[str]


@dataclass
class AnomalyDetectionResult:
    """Anomaly detection result"""

    is_anomaly: bool
    anomaly_score: float
    feature_contributions: Dict[str, float]
    baseline_comparison: Dict[str, Any]
    explanation: str


class ThreatIntelligenceDB(Base):
    """Threat intelligence database model"""

    __tablename__ = "threat_intelligence_db"
    id = Column(Integer, primary_key=True)
    indicator_type = Column(String(50), nullable=False)
    indicator_value = Column(String(500), nullable=False)
    threat_type = Column(String(100))
    severity = Column(String(50))
    confidence = Column(Float)
    source = Column(String(100))
    description = Column(Text)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    metadata = Column(Text)
    tags = Column(Text)


class ThreatEventLog(Base):
    """Threat event log model"""

    __tablename__ = "threat_events"
    id = Column(Integer, primary_key=True)
    event_id = Column(String(100), unique=True, nullable=False)
    threat_type = Column(String(100), nullable=False)
    severity = Column(String(50), nullable=False)
    confidence = Column(Float)
    source_ip = Column(String(50))
    target_resource = Column(String(200))
    user_id = Column(String(100))
    session_id = Column(String(100))
    description = Column(Text)
    indicators = Column(Text)
    raw_data = Column(Text)
    response_actions = Column(Text)
    mitre_tactics = Column(Text)
    mitre_techniques = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    resolved = Column(Boolean, default=False)
    false_positive = Column(Boolean, default=False)


class AnomalyModel(Base):
    """Anomaly detection model metadata"""

    __tablename__ = "anomaly_models"
    id = Column(Integer, primary_key=True)
    model_name = Column(String(100), unique=True, nullable=False)
    model_type = Column(String(50))
    features = Column(Text)
    training_data_size = Column(Integer)
    accuracy = Column(Float)
    precision = Column(Float)
    recall = Column(Float)
    f1_score = Column(Float)
    model_path = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    last_trained = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class ThreatIntelligenceCollector:
    """Collects threat intelligence from various sources"""

    def __init__(self, db_session: Any, redis_client: redis.Redis) -> None:
        self.db_session = db_session
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
        self.sources = []
        self._initialize_sources()

    def _initialize_sources(self) -> Any:
        """Initialize threat intelligence sources"""
        self.sources = [
            {
                "name": "abuse_ch",
                "url": "https://feodotracker.abuse.ch/downloads/ipblocklist.txt",
                "type": "ip",
                "format": "text",
            },
            {
                "name": "malware_domains",
                "url": "https://mirror1.malwaredomains.com/files/justdomains",
                "type": "domain",
                "format": "text",
            },
            {
                "name": "emerging_threats",
                "url": "https://rules.emergingthreats.net/fwrules/emerging-Block-IPs.txt",
                "type": "ip",
                "format": "text",
            },
        ]

    def collect_threat_intelligence(self) -> Any:
        """Collect threat intelligence from all sources"""
        try:
            for source in self.sources:
                self._collect_from_source(source)
            self.logger.info("Threat intelligence collection completed")
        except Exception as e:
            self.logger.error(f"Threat intelligence collection failed: {str(e)}")

    def _collect_from_source(self, source: Dict[str, Any]) -> Any:
        """Collect threat intelligence from a specific source"""
        try:
            response = requests.get(source["url"], timeout=30)
            response.raise_for_status()
            if source["format"] == "text":
                indicators = response.text.strip().split("\n")
                for indicator in indicators:
                    indicator = indicator.strip()
                    if indicator and (not indicator.startswith("#")):
                        self._store_indicator(
                            indicator_type=source["type"],
                            indicator_value=indicator,
                            source=source["name"],
                            threat_type="malicious",
                            severity="medium",
                            confidence=0.8,
                        )
            self.logger.info(f"Collected threat intelligence from {source['name']}")
        except Exception as e:
            self.logger.error(f"Failed to collect from {source['name']}: {str(e)}")

    def _store_indicator(
        self,
        indicator_type: str,
        indicator_value: str,
        source: str,
        threat_type: str,
        severity: str,
        confidence: float,
    ) -> Any:
        """Store threat indicator in database"""
        try:
            existing = (
                self.db_session.query(ThreatIntelligenceDB)
                .filter_by(
                    indicator_type=indicator_type, indicator_value=indicator_value
                )
                .first()
            )
            if existing:
                existing.last_seen = datetime.utcnow()
                existing.confidence = max(existing.confidence, confidence)
            else:
                indicator = ThreatIntelligenceDB(
                    indicator_type=indicator_type,
                    indicator_value=indicator_value,
                    threat_type=threat_type,
                    severity=severity,
                    confidence=confidence,
                    source=source,
                )
                self.db_session.add(indicator)
            self.db_session.commit()
        except Exception as e:
            self.logger.error(f"Failed to store indicator: {str(e)}")
            self.db_session.rollback()

    def check_indicator(
        self, indicator_type: str, indicator_value: str
    ) -> Optional[Dict[str, Any]]:
        """Check if indicator is in threat intelligence"""
        try:
            indicator = (
                self.db_session.query(ThreatIntelligenceDB)
                .filter_by(
                    indicator_type=indicator_type,
                    indicator_value=indicator_value,
                    is_active=True,
                )
                .first()
            )
            if indicator:
                return {
                    "threat_type": indicator.threat_type,
                    "severity": indicator.severity,
                    "confidence": indicator.confidence,
                    "source": indicator.source,
                    "first_seen": indicator.first_seen.isoformat(),
                    "last_seen": indicator.last_seen.isoformat(),
                }
            return None
        except Exception as e:
            self.logger.error(f"Indicator check failed: {str(e)}")
            return None


class AnomalyDetector:
    """Machine learning-based anomaly detection"""

    def __init__(self, db_session: Any, redis_client: redis.Redis) -> None:
        self.db_session = db_session
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
        self.models = {}
        self.scalers = {}
        self.feature_extractors = {}
        self._initialize_models()

    def _initialize_models(self) -> Any:
        """Initialize anomaly detection models"""
        self.models["user_behavior"] = IsolationForest(
            contamination=0.1, random_state=42, n_estimators=100
        )
        self.models["network_traffic"] = IsolationForest(
            contamination=0.05, random_state=42, n_estimators=150
        )
        self.models["api_usage"] = IsolationForest(
            contamination=0.08, random_state=42, n_estimators=120
        )
        for model_name in self.models.keys():
            self.scalers[model_name] = StandardScaler()

    def train_models(self) -> Any:
        """Train anomaly detection models"""
        try:
            self._train_user_behavior_model()
            self._train_network_traffic_model()
            self._train_api_usage_model()
            self.logger.info("Anomaly detection models trained successfully")
        except Exception as e:
            self.logger.error(f"Model training failed: {str(e)}")

    def _train_user_behavior_model(self) -> Any:
        """Train user behavior anomaly detection model"""
        try:
            np.random.seed(42)
            n_samples = 10000
            normal_data = np.random.normal(0, 1, (int(n_samples * 0.9), 10))
            anomaly_data = np.random.normal(3, 2, (int(n_samples * 0.1), 10))
            X = np.vstack([normal_data, anomaly_data])
            X_scaled = self.scalers["user_behavior"].fit_transform(X)
            self.models["user_behavior"].fit(X_scaled)
            self._save_model("user_behavior")
            self.logger.info("User behavior model trained")
        except Exception as e:
            self.logger.error(f"User behavior model training failed: {str(e)}")

    def _train_network_traffic_model(self) -> Any:
        """Train network traffic anomaly detection model"""
        try:
            np.random.seed(42)
            n_samples = 8000
            normal_data = np.random.normal(0, 1, (int(n_samples * 0.95), 15))
            anomaly_data = np.random.normal(4, 3, (int(n_samples * 0.05), 15))
            X = np.vstack([normal_data, anomaly_data])
            X_scaled = self.scalers["network_traffic"].fit_transform(X)
            self.models["network_traffic"].fit(X_scaled)
            self._save_model("network_traffic")
            self.logger.info("Network traffic model trained")
        except Exception as e:
            self.logger.error(f"Network traffic model training failed: {str(e)}")

    def _train_api_usage_model(self) -> Any:
        """Train API usage anomaly detection model"""
        try:
            np.random.seed(42)
            n_samples = 12000
            normal_data = np.random.normal(0, 1, (int(n_samples * 0.92), 12))
            anomaly_data = np.random.normal(3.5, 2.5, (int(n_samples * 0.08), 12))
            X = np.vstack([normal_data, anomaly_data])
            X_scaled = self.scalers["api_usage"].fit_transform(X)
            self.models["api_usage"].fit(X_scaled)
            self._save_model("api_usage")
            self.logger.info("API usage model trained")
        except Exception as e:
            self.logger.error(f"API usage model training failed: {str(e)}")

    def _save_model(self, model_name: str) -> Any:
        """Save trained model to disk"""
        try:
            model_dir = f"/tmp/anomaly_models/{model_name}"
            os.makedirs(model_dir, exist_ok=True)
            model_path = f"{model_dir}/model.joblib"
            joblib.dump(self.models[model_name], model_path)
            scaler_path = f"{model_dir}/scaler.joblib"
            joblib.dump(self.scalers[model_name], scaler_path)
            metadata = AnomalyModel(
                model_name=model_name,
                model_type="IsolationForest",
                features=json.dumps([f"feature_{i}" for i in range(10)]),
                training_data_size=10000,
                model_path=model_path,
            )
            self.db_session.add(metadata)
            self.db_session.commit()
        except Exception as e:
            self.logger.error(f"Model saving failed: {str(e)}")

    def detect_anomaly(
        self, model_name: str, features: List[float]
    ) -> AnomalyDetectionResult:
        """Detect anomaly using specified model"""
        try:
            if model_name not in self.models:
                raise ValueError(f"Unknown model: {model_name}")
            features_array = np.array(features).reshape(1, -1)
            features_scaled = self.scalers[model_name].transform(features_array)
            anomaly_score = self.models[model_name].decision_function(features_scaled)[
                0
            ]
            is_anomaly = self.models[model_name].predict(features_scaled)[0] == -1
            feature_contributions = {
                f"feature_{i}": abs(features[i]) for i in range(len(features))
            }
            explanation = self._generate_anomaly_explanation(
                model_name, is_anomaly, anomaly_score, feature_contributions
            )
            return AnomalyDetectionResult(
                is_anomaly=is_anomaly,
                anomaly_score=float(anomaly_score),
                feature_contributions=feature_contributions,
                baseline_comparison={},
                explanation=explanation,
            )
        except Exception as e:
            self.logger.error(f"Anomaly detection failed: {str(e)}")
            return AnomalyDetectionResult(
                is_anomaly=False,
                anomaly_score=0.0,
                feature_contributions={},
                baseline_comparison={},
                explanation=f"Detection failed: {str(e)}",
            )

    def _generate_anomaly_explanation(
        self,
        model_name: str,
        is_anomaly: bool,
        anomaly_score: float,
        feature_contributions: Dict[str, float],
    ) -> str:
        """Generate human-readable explanation for anomaly detection"""
        if not is_anomaly:
            return f"Normal behavior detected for {model_name} (score: {anomaly_score:.3f})"
        top_features = sorted(
            feature_contributions.items(), key=lambda x: x[1], reverse=True
        )[:3]
        top_feature_names = [f[0] for f in top_features]
        return f"Anomaly detected in {model_name} (score: {anomaly_score:.3f}). Top contributing factors: {', '.join(top_feature_names)}"


class ThreatDetectionRules:
    """Rule-based threat detection engine"""

    def __init__(self, db_session: Any, redis_client: redis.Redis) -> None:
        self.db_session = db_session
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
        self.rules = []
        self._initialize_rules()

    def _initialize_rules(self) -> Any:
        """Initialize threat detection rules"""
        self.rules = [
            {
                "name": "brute_force_detection",
                "description": "Detect brute force attacks",
                "function": self._detect_brute_force,
                "enabled": True,
            },
            {
                "name": "sql_injection_detection",
                "description": "Detect SQL injection attempts",
                "function": self._detect_sql_injection,
                "enabled": True,
            },
            {
                "name": "xss_detection",
                "description": "Detect XSS attempts",
                "function": self._detect_xss,
                "enabled": True,
            },
            {
                "name": "ddos_detection",
                "description": "Detect DDoS attacks",
                "function": self._detect_ddos,
                "enabled": True,
            },
            {
                "name": "data_exfiltration_detection",
                "description": "Detect data exfiltration attempts",
                "function": self._detect_data_exfiltration,
                "enabled": True,
            },
            {
                "name": "privilege_escalation_detection",
                "description": "Detect privilege escalation attempts",
                "function": self._detect_privilege_escalation,
                "enabled": True,
            },
        ]

    def evaluate_rules(self, event_data: Dict[str, Any]) -> List[ThreatEvent]:
        """Evaluate all rules against event data"""
        threats: List[Any] = []
        for rule in self.rules:
            if not rule["enabled"]:
                continue
            try:
                threat = rule["function"](event_data)
                if threat:
                    threats.append(threat)
            except Exception as e:
                self.logger.error(
                    f"Rule evaluation failed for {rule['name']}: {str(e)}"
                )
        return threats

    def _detect_brute_force(self, event_data: Dict[str, Any]) -> Optional[ThreatEvent]:
        """Detect brute force attacks"""
        try:
            ip_address = event_data.get("ip_address")
            user_id = event_data.get("user_id")
            action = event_data.get("action")
            success = event_data.get("success", True)
            if action != "login" or success:
                return None
            cache_key = f"failed_logins:{ip_address}"
            failed_count = self.redis_client.get(cache_key)
            if failed_count:
                failed_count = int(failed_count)
                if failed_count >= 5:
                    return ThreatEvent(
                        event_id=f"bf_{int(time.time())}_{hash(ip_address) % 10000}",
                        threat_type=ThreatType.BRUTE_FORCE,
                        severity=Severity.HIGH,
                        confidence=0.9,
                        source_ip=ip_address,
                        target_resource="/login",
                        user_id=user_id,
                        session_id=event_data.get("session_id"),
                        timestamp=datetime.utcnow(),
                        description=f"Brute force attack detected from {ip_address} ({failed_count} failed attempts)",
                        indicators={"failed_attempts": failed_count, "threshold": 5},
                        raw_data=event_data,
                        response_actions=[
                            ResponseAction.BLOCK_IP,
                            ResponseAction.ALERT_ADMIN,
                        ],
                        mitre_tactics=["TA0006"],
                        mitre_techniques=["T1110"],
                    )
            return None
        except Exception as e:
            self.logger.error(f"Brute force detection failed: {str(e)}")
            return None

    def _detect_sql_injection(
        self, event_data: Dict[str, Any]
    ) -> Optional[ThreatEvent]:
        """Detect SQL injection attempts"""
        try:
            request_data = event_data.get("request_data", {})
            query_params = request_data.get("query_params", "")
            post_data = request_data.get("post_data", "")
            sql_patterns = [
                "(\\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\\b)",
                "(\\b(UNION|OR|AND)\\s+\\d+\\s*=\\s*\\d+)",
                "(\\'|\\\")(\\s*)(OR|AND)(\\s*)(\\'|\\\")(\\s*)(=|LIKE)",
                "(\\b(EXEC|EXECUTE)\\b)",
                "(--|\\#|\\/\\*|\\*\\/)",
                "(\\b(INFORMATION_SCHEMA|SYSOBJECTS|SYSCOLUMNS)\\b)",
            ]
            combined_input = f"{query_params} {post_data}".lower()
            for pattern in sql_patterns:
                if re.search(pattern, combined_input, re.IGNORECASE):
                    return ThreatEvent(
                        event_id=f"sqli_{int(time.time())}_{hash(combined_input) % 10000}",
                        threat_type=ThreatType.SQL_INJECTION,
                        severity=Severity.HIGH,
                        confidence=0.8,
                        source_ip=event_data.get("ip_address"),
                        target_resource=event_data.get("resource"),
                        user_id=event_data.get("user_id"),
                        session_id=event_data.get("session_id"),
                        timestamp=datetime.utcnow(),
                        description=f"SQL injection attempt detected: {pattern}",
                        indicators={"pattern": pattern, "input": combined_input[:200]},
                        raw_data=event_data,
                        response_actions=[
                            ResponseAction.BLOCK_IP,
                            ResponseAction.ALERT_ADMIN,
                        ],
                        mitre_tactics=["TA0001"],
                        mitre_techniques=["T1190"],
                    )
            return None
        except Exception as e:
            self.logger.error(f"SQL injection detection failed: {str(e)}")
            return None

    def _detect_xss(self, event_data: Dict[str, Any]) -> Optional[ThreatEvent]:
        """Detect XSS attempts"""
        try:
            request_data = event_data.get("request_data", {})
            query_params = request_data.get("query_params", "")
            post_data = request_data.get("post_data", "")
            xss_patterns = [
                "<script[^>]*>.*?</script>",
                "javascript:",
                "on\\w+\\s*=",
                "<iframe[^>]*>",
                "<object[^>]*>",
                "<embed[^>]*>",
                "<link[^>]*>",
                "<meta[^>]*>",
                "expression\\s*\\(",
                "vbscript:",
                "data:text/html",
            ]
            combined_input = f"{query_params} {post_data}"
            for pattern in xss_patterns:
                if re.search(pattern, combined_input, re.IGNORECASE):
                    return ThreatEvent(
                        event_id=f"xss_{int(time.time())}_{hash(combined_input) % 10000}",
                        threat_type=ThreatType.XSS,
                        severity=Severity.MEDIUM,
                        confidence=0.7,
                        source_ip=event_data.get("ip_address"),
                        target_resource=event_data.get("resource"),
                        user_id=event_data.get("user_id"),
                        session_id=event_data.get("session_id"),
                        timestamp=datetime.utcnow(),
                        description=f"XSS attempt detected: {pattern}",
                        indicators={"pattern": pattern, "input": combined_input[:200]},
                        raw_data=event_data,
                        response_actions=[
                            ResponseAction.BLOCK_IP,
                            ResponseAction.ALERT_ADMIN,
                        ],
                        mitre_tactics=["TA0001"],
                        mitre_techniques=["T1190"],
                    )
            return None
        except Exception as e:
            self.logger.error(f"XSS detection failed: {str(e)}")
            return None

    def _detect_ddos(self, event_data: Dict[str, Any]) -> Optional[ThreatEvent]:
        """Detect DDoS attacks"""
        try:
            ip_address = event_data.get("ip_address")
            cache_key = f"request_rate:{ip_address}"
            request_count = self.redis_client.get(cache_key)
            if request_count and int(request_count) > 1000:
                return ThreatEvent(
                    event_id=f"ddos_{int(time.time())}_{hash(ip_address) % 10000}",
                    threat_type=ThreatType.DDoS,
                    severity=Severity.CRITICAL,
                    confidence=0.9,
                    source_ip=ip_address,
                    target_resource=event_data.get("resource"),
                    user_id=event_data.get("user_id"),
                    session_id=event_data.get("session_id"),
                    timestamp=datetime.utcnow(),
                    description=f"DDoS attack detected from {ip_address} ({request_count} requests)",
                    indicators={"request_count": int(request_count), "threshold": 1000},
                    raw_data=event_data,
                    response_actions=[
                        ResponseAction.BLOCK_IP,
                        ResponseAction.RATE_LIMIT,
                        ResponseAction.ALERT_ADMIN,
                    ],
                    mitre_tactics=["TA0040"],
                    mitre_techniques=["T1499"],
                )
            return None
        except Exception as e:
            self.logger.error(f"DDoS detection failed: {str(e)}")
            return None

    def _detect_data_exfiltration(
        self, event_data: Dict[str, Any]
    ) -> Optional[ThreatEvent]:
        """Detect data exfiltration attempts"""
        try:
            user_id = event_data.get("user_id")
            resource = event_data.get("resource", "")
            action = event_data.get("action", "")
            if action == "download" and "bulk" in resource.lower():
                cache_key = f"download_volume:{user_id}"
                download_count = self.redis_client.get(cache_key)
                if download_count and int(download_count) > 100:
                    return ThreatEvent(
                        event_id=f"exfil_{int(time.time())}_{hash(user_id) % 10000}",
                        threat_type=ThreatType.DATA_EXFILTRATION,
                        severity=Severity.HIGH,
                        confidence=0.7,
                        source_ip=event_data.get("ip_address"),
                        target_resource=resource,
                        user_id=user_id,
                        session_id=event_data.get("session_id"),
                        timestamp=datetime.utcnow(),
                        description=f"Potential data exfiltration by user {user_id} ({download_count} downloads)",
                        indicators={
                            "download_count": int(download_count),
                            "threshold": 100,
                        },
                        raw_data=event_data,
                        response_actions=[
                            ResponseAction.ALERT_ADMIN,
                            ResponseAction.CHALLENGE_USER,
                        ],
                        mitre_tactics=["TA0010"],
                        mitre_techniques=["T1041"],
                    )
            return None
        except Exception as e:
            self.logger.error(f"Data exfiltration detection failed: {str(e)}")
            return None

    def _detect_privilege_escalation(
        self, event_data: Dict[str, Any]
    ) -> Optional[ThreatEvent]:
        """Detect privilege escalation attempts"""
        try:
            user_id = event_data.get("user_id")
            action = event_data.get("action", "")
            resource = event_data.get("resource", "")
            admin_actions = [
                "create_user",
                "delete_user",
                "modify_permissions",
                "access_admin_panel",
            ]
            if action in admin_actions:
                cache_key = f"user_role:{user_id}"
                user_role = self.redis_client.get(cache_key)
                if user_role and user_role != "admin":
                    return ThreatEvent(
                        event_id=f"privesc_{int(time.time())}_{hash(user_id) % 10000}",
                        threat_type=ThreatType.PRIVILEGE_ESCALATION,
                        severity=Severity.HIGH,
                        confidence=0.8,
                        source_ip=event_data.get("ip_address"),
                        target_resource=resource,
                        user_id=user_id,
                        session_id=event_data.get("session_id"),
                        timestamp=datetime.utcnow(),
                        description=f"Privilege escalation attempt by user {user_id} (role: {user_role})",
                        indicators={"user_role": user_role, "attempted_action": action},
                        raw_data=event_data,
                        response_actions=[
                            ResponseAction.BLOCK_USER,
                            ResponseAction.ALERT_ADMIN,
                        ],
                        mitre_tactics=["TA0004"],
                        mitre_techniques=["T1068"],
                    )
            return None
        except Exception as e:
            self.logger.error(f"Privilege escalation detection failed: {str(e)}")
            return None


class AutomatedResponseSystem:
    """Automated threat response system"""

    def __init__(self, redis_client: redis.Redis, config: Dict[str, Any]) -> None:
        self.redis_client = redis_client
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.response_handlers = {
            ResponseAction.BLOCK_IP: self._block_ip,
            ResponseAction.BLOCK_USER: self._block_user,
            ResponseAction.QUARANTINE_DEVICE: self._quarantine_device,
            ResponseAction.ALERT_ADMIN: self._alert_admin,
            ResponseAction.LOG_ONLY: self._log_only,
            ResponseAction.RATE_LIMIT: self._rate_limit,
            ResponseAction.CHALLENGE_USER: self._challenge_user,
            ResponseAction.FORCE_LOGOUT: self._force_logout,
            ResponseAction.DISABLE_ACCOUNT: self._disable_account,
            ResponseAction.ISOLATE_NETWORK: self._isolate_network,
        }

    def execute_response(self, threat_event: ThreatEvent) -> Dict[str, Any]:
        """Execute automated response actions"""
        results: Dict[str, Any] = {}
        for action in threat_event.response_actions:
            try:
                if action in self.response_handlers:
                    result = self.response_handlers[action](threat_event)
                    results[action.value] = result
                else:
                    self.logger.warning(f"Unknown response action: {action}")
            except Exception as e:
                self.logger.error(f"Response action {action.value} failed: {str(e)}")
                results[action.value] = {"success": False, "error": str(e)}
        return results

    def _block_ip(self, threat_event: ThreatEvent) -> Dict[str, Any]:
        """Block IP address"""
        try:
            ip_address = threat_event.source_ip
            self.redis_client.sadd("blocked_ips", ip_address)
            self.redis_client.expire(f"blocked_ip:{ip_address}", 86400)
            self.logger.info(f"Blocked IP address: {ip_address}")
            return {"success": True, "action": "ip_blocked", "ip": ip_address}
        except Exception as e:
            self.logger.error(f"IP blocking failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _block_user(self, threat_event: ThreatEvent) -> Dict[str, Any]:
        """Block user account"""
        try:
            user_id = threat_event.user_id
            if not user_id:
                return {"success": False, "error": "No user ID provided"}
            self.redis_client.sadd("blocked_users", user_id)
            self.redis_client.setex(f"blocked_user:{user_id}", 3600, "true")
            self.logger.info(f"Blocked user: {user_id}")
            return {"success": True, "action": "user_blocked", "user_id": user_id}
        except Exception as e:
            self.logger.error(f"User blocking failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _quarantine_device(self, threat_event: ThreatEvent) -> Dict[str, Any]:
        """Quarantine device"""
        try:
            device_id = threat_event.raw_data.get("device_id")
            if not device_id:
                return {"success": False, "error": "No device ID provided"}
            self.redis_client.sadd("quarantined_devices", device_id)
            self.logger.info(f"Quarantined device: {device_id}")
            return {
                "success": True,
                "action": "device_quarantined",
                "device_id": device_id,
            }
        except Exception as e:
            self.logger.error(f"Device quarantine failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _alert_admin(self, threat_event: ThreatEvent) -> Dict[str, Any]:
        """Send alert to administrators"""
        try:
            alert_message = f"\n            SECURITY ALERT: {threat_event.threat_type.value.upper()}\n\n            Severity: {threat_event.severity.value}\n            Confidence: {threat_event.confidence}\n            Source IP: {threat_event.source_ip}\n            Target: {threat_event.target_resource}\n            User: {threat_event.user_id or 'Unknown'}\n            Time: {threat_event.timestamp}\n\n            Description: {threat_event.description}\n\n            MITRE ATT&CK:\n            Tactics: {', '.join(threat_event.mitre_tactics)}\n            Techniques: {', '.join(threat_event.mitre_techniques)}\n            "
            if self.config.get("email_alerts_enabled"):
                self._send_email_alert(alert_message, threat_event)
            if self.config.get("slack_alerts_enabled"):
                self._send_slack_alert(alert_message, threat_event)
            if threat_event.severity == Severity.CRITICAL and self.config.get(
                "sms_alerts_enabled"
            ):
                self._send_sms_alert(alert_message, threat_event)
            self.logger.info(f"Admin alert sent for threat: {threat_event.event_id}")
            return {"success": True, "action": "alert_sent"}
        except Exception as e:
            self.logger.error(f"Admin alert failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _log_only(self, threat_event: ThreatEvent) -> Dict[str, Any]:
        """Log threat event only"""
        try:
            self.logger.warning(f"Threat detected: {threat_event.description}")
            return {"success": True, "action": "logged"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _rate_limit(self, threat_event: ThreatEvent) -> Dict[str, Any]:
        """Apply rate limiting"""
        try:
            ip_address = threat_event.source_ip
            self.redis_client.setex(f"rate_limit:{ip_address}", 3600, "10")
            self.logger.info(f"Rate limit applied to IP: {ip_address}")
            return {"success": True, "action": "rate_limited", "ip": ip_address}
        except Exception as e:
            self.logger.error(f"Rate limiting failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _challenge_user(self, threat_event: ThreatEvent) -> Dict[str, Any]:
        """Challenge user with additional authentication"""
        try:
            user_id = threat_event.user_id
            session_id = threat_event.session_id
            if not user_id:
                return {"success": False, "error": "No user ID provided"}
            self.redis_client.setex(f"challenge_user:{user_id}", 1800, "true")
            if session_id:
                self.redis_client.setex(f"challenge_session:{session_id}", 1800, "true")
            self.logger.info(f"User challenge initiated: {user_id}")
            return {"success": True, "action": "user_challenged", "user_id": user_id}
        except Exception as e:
            self.logger.error(f"User challenge failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _force_logout(self, threat_event: ThreatEvent) -> Dict[str, Any]:
        """Force user logout"""
        try:
            user_id = threat_event.user_id
            session_id = threat_event.session_id
            if session_id:
                self.redis_client.delete(f"session:{session_id}")
            if user_id:
                self.redis_client.delete(f"user_sessions:{user_id}")
            self.logger.info(f"Forced logout for user: {user_id}")
            return {"success": True, "action": "forced_logout", "user_id": user_id}
        except Exception as e:
            self.logger.error(f"Force logout failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _disable_account(self, threat_event: ThreatEvent) -> Dict[str, Any]:
        """Disable user account"""
        try:
            user_id = threat_event.user_id
            if not user_id:
                return {"success": False, "error": "No user ID provided"}
            self.redis_client.setex(f"disabled_account:{user_id}", 86400, "true")
            self.logger.info(f"Disabled account: {user_id}")
            return {"success": True, "action": "account_disabled", "user_id": user_id}
        except Exception as e:
            self.logger.error(f"Account disable failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _isolate_network(self, threat_event: ThreatEvent) -> Dict[str, Any]:
        """Isolate network segment"""
        try:
            ip_address = threat_event.source_ip
            self.redis_client.sadd("isolated_networks", ip_address)
            self.logger.info(f"Network isolation applied to: {ip_address}")
            return {"success": True, "action": "network_isolated", "ip": ip_address}
        except Exception as e:
            self.logger.error(f"Network isolation failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _send_email_alert(self, message: str, threat_event: ThreatEvent) -> Any:
        """Send email alert"""
        try:
            smtp_server = self.config.get("smtp_server")
            smtp_port = self.config.get("smtp_port", 587)
            smtp_username = self.config.get("smtp_username")
            smtp_password = self.config.get("smtp_password")
            alert_recipients = self.config.get("alert_recipients", [])
            if not all([smtp_server, smtp_username, smtp_password, alert_recipients]):
                return
            msg = MIMEMultipart()
            msg["From"] = smtp_username
            msg["To"] = ", ".join(alert_recipients)
            msg["Subject"] = f"Security Alert: {threat_event.threat_type.value.upper()}"
            msg.attach(MIMEText(message, "plain"))
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
            server.quit()
        except Exception as e:
            self.logger.error(f"Email alert failed: {str(e)}")

    def _send_slack_alert(self, message: str, threat_event: ThreatEvent) -> Any:
        """Send Slack alert"""
        try:
            slack_token = self.config.get("slack_token")
            slack_channel = self.config.get("slack_channel")
            if not slack_token or not slack_channel:
                return
            client = slack_sdk.WebClient(token=slack_token)
            client.chat_postMessage(
                channel=slack_channel,
                text=f"🚨 Security Alert: {threat_event.threat_type.value.upper()}",
                blocks=[
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"```{message}```"},
                    }
                ],
            )
        except Exception as e:
            self.logger.error(f"Slack alert failed: {str(e)}")

    def _send_sms_alert(self, message: str, threat_event: ThreatEvent) -> Any:
        """Send SMS alert"""
        try:
            twilio_sid = self.config.get("twilio_sid")
            twilio_token = self.config.get("twilio_token")
            twilio_from = self.config.get("twilio_from")
            sms_recipients = self.config.get("sms_recipients", [])
            if not all([twilio_sid, twilio_token, twilio_from, sms_recipients]):
                return
            client = TwilioClient(twilio_sid, twilio_token)
            short_message = f"SECURITY ALERT: {threat_event.threat_type.value.upper()} from {threat_event.source_ip}"
            for recipient in sms_recipients:
                client.messages.create(
                    body=short_message, from_=twilio_from, to=recipient
                )
        except Exception as e:
            self.logger.error(f"SMS alert failed: {str(e)}")


class ThreatDetectionEngine:
    """Main threat detection engine"""

    def __init__(
        self, db_session: Any, redis_client: redis.Redis, config: Dict[str, Any]
    ) -> None:
        self.db_session = db_session
        self.redis_client = redis_client
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.threat_intel = ThreatIntelligenceCollector(db_session, redis_client)
        self.anomaly_detector = AnomalyDetector(db_session, redis_client)
        self.rule_engine = ThreatDetectionRules(db_session, redis_client)
        self.response_system = AutomatedResponseSystem(redis_client, config)
        Base.metadata.create_all(bind=db_session.bind)
        self.threat_counter = Counter(
            "threats_detected_total", "Total threats detected", ["type", "severity"]
        )
        self.response_counter = Counter(
            "responses_executed_total", "Total responses executed", ["action"]
        )
        self.detection_latency = Histogram(
            "threat_detection_latency_seconds", "Threat detection latency"
        )

    def analyze_event(self, event_data: Dict[str, Any]) -> List[ThreatEvent]:
        """Analyze event for threats"""
        start_time = time.time()
        threats: List[Any] = []
        try:
            rule_threats = self.rule_engine.evaluate_rules(event_data)
            threats.extend(rule_threats)
            anomaly_threats = self._detect_anomalies(event_data)
            threats.extend(anomaly_threats)
            intel_threats = self._check_threat_intelligence(event_data)
            threats.extend(intel_threats)
            for threat in threats:
                self._process_threat(threat)
            detection_time = time.time() - start_time
            self.detection_latency.observe(detection_time)
            return threats
        except Exception as e:
            self.logger.error(f"Event analysis failed: {str(e)}")
            return []

    def _detect_anomalies(self, event_data: Dict[str, Any]) -> List[ThreatEvent]:
        """Detect anomalies in event data"""
        threats: List[Any] = []
        try:
            user_features = self._extract_user_features(event_data)
            network_features = self._extract_network_features(event_data)
            self._extract_api_features(event_data)
            if user_features:
                result = self.anomaly_detector.detect_anomaly(
                    "user_behavior", user_features
                )
                if result.is_anomaly:
                    threat = ThreatEvent(
                        event_id=f"anom_user_{int(time.time())}_{hash(str(user_features)) % 10000}",
                        threat_type=ThreatType.ANOMALOUS_BEHAVIOR,
                        severity=Severity.MEDIUM,
                        confidence=abs(result.anomaly_score),
                        source_ip=event_data.get("ip_address", ""),
                        target_resource=event_data.get("resource", ""),
                        user_id=event_data.get("user_id"),
                        session_id=event_data.get("session_id"),
                        timestamp=datetime.utcnow(),
                        description=result.explanation,
                        indicators=result.feature_contributions,
                        raw_data=event_data,
                        response_actions=[
                            ResponseAction.ALERT_ADMIN,
                            ResponseAction.CHALLENGE_USER,
                        ],
                        mitre_tactics=["TA0009"],
                        mitre_techniques=["T1005"],
                    )
                    threats.append(threat)
            if network_features:
                result = self.anomaly_detector.detect_anomaly(
                    "network_traffic", network_features
                )
                if result.is_anomaly:
                    threat = ThreatEvent(
                        event_id=f"anom_net_{int(time.time())}_{hash(str(network_features)) % 10000}",
                        threat_type=ThreatType.ANOMALOUS_BEHAVIOR,
                        severity=Severity.MEDIUM,
                        confidence=abs(result.anomaly_score),
                        source_ip=event_data.get("ip_address", ""),
                        target_resource=event_data.get("resource", ""),
                        user_id=event_data.get("user_id"),
                        session_id=event_data.get("session_id"),
                        timestamp=datetime.utcnow(),
                        description=f"Network anomaly: {result.explanation}",
                        indicators=result.feature_contributions,
                        raw_data=event_data,
                        response_actions=[
                            ResponseAction.ALERT_ADMIN,
                            ResponseAction.RATE_LIMIT,
                        ],
                        mitre_tactics=["TA0011"],
                        mitre_techniques=["T1071"],
                    )
                    threats.append(threat)
            return threats
        except Exception as e:
            self.logger.error(f"Anomaly detection failed: {str(e)}")
            return []

    def _check_threat_intelligence(
        self, event_data: Dict[str, Any]
    ) -> List[ThreatEvent]:
        """Check event against threat intelligence"""
        threats: List[Any] = []
        try:
            ip_address = event_data.get("ip_address")
            if ip_address:
                intel = self.threat_intel.check_indicator("ip", ip_address)
                if intel:
                    threat = ThreatEvent(
                        event_id=f"intel_{int(time.time())}_{hash(ip_address) % 10000}",
                        threat_type=(
                            ThreatType.APT
                            if intel["severity"] == "critical"
                            else ThreatType.MALWARE
                        ),
                        severity=Severity[intel["severity"].upper()],
                        confidence=intel["confidence"],
                        source_ip=ip_address,
                        target_resource=event_data.get("resource", ""),
                        user_id=event_data.get("user_id"),
                        session_id=event_data.get("session_id"),
                        timestamp=datetime.utcnow(),
                        description=f"Known threat source: {intel['source']} ({intel['threat_type']})",
                        indicators=intel,
                        raw_data=event_data,
                        response_actions=[
                            ResponseAction.BLOCK_IP,
                            ResponseAction.ALERT_ADMIN,
                        ],
                        mitre_tactics=["TA0001"],
                        mitre_techniques=["T1190"],
                    )
                    threats.append(threat)
            return threats
        except Exception as e:
            self.logger.error(f"Threat intelligence check failed: {str(e)}")
            return []

    def _extract_user_features(
        self, event_data: Dict[str, Any]
    ) -> Optional[List[float]]:
        """Extract user behavior features"""
        try:
            user_id = event_data.get("user_id")
            if not user_id:
                return None
            features = [
                hash(user_id) % 100 / 100.0,
                len(event_data.get("resource", "")) / 100.0,
                event_data.get("timestamp", time.time()) % 86400 / 86400.0,
                len(event_data.get("user_agent", "")) / 500.0,
                1.0 if event_data.get("success", True) else 0.0,
                len(str(event_data)) / 1000.0,
                hash(event_data.get("action", "")) % 50 / 50.0,
                hash(event_data.get("ip_address", "")) % 256 / 256.0,
                np.random.random(),
                np.random.random(),
            ]
            return features
        except Exception as e:
            self.logger.error(f"User feature extraction failed: {str(e)}")
            return None

    def _extract_network_features(
        self, event_data: Dict[str, Any]
    ) -> Optional[List[float]]:
        """Extract network traffic features"""
        try:
            ip_address = event_data.get("ip_address")
            if not ip_address:
                return None
            features = [
                hash(ip_address) % 256 / 256.0,
                len(event_data.get("user_agent", "")) / 500.0,
                len(str(event_data.get("request_data", {}))) / 1000.0,
                event_data.get("timestamp", time.time()) % 86400 / 86400.0,
                1.0 if "bot" in event_data.get("user_agent", "").lower() else 0.0,
                len(event_data.get("resource", "")) / 200.0,
                hash(event_data.get("method", "GET")) % 10 / 10.0,
                event_data.get("response_code", 200) / 600.0,
                np.random.random(),
                np.random.random(),
                np.random.random(),
                np.random.random(),
                np.random.random(),
                np.random.random(),
                np.random.random(),
            ]
            return features
        except Exception as e:
            self.logger.error(f"Network feature extraction failed: {str(e)}")
            return None

    def _extract_api_features(
        self, event_data: Dict[str, Any]
    ) -> Optional[List[float]]:
        """Extract API usage features"""
        try:
            features = [
                len(event_data.get("resource", "")) / 200.0,
                hash(event_data.get("action", "")) % 20 / 20.0,
                event_data.get("timestamp", time.time()) % 86400 / 86400.0,
                1.0 if event_data.get("success", True) else 0.0,
                len(str(event_data.get("request_data", {}))) / 1000.0,
                len(str(event_data.get("response_data", {}))) / 1000.0,
                event_data.get("response_time", 0) / 10000.0,
                hash(event_data.get("user_id", "")) % 100 / 100.0,
                np.random.random(),
                np.random.random(),
                np.random.random(),
                np.random.random(),
            ]
            return features
        except Exception as e:
            self.logger.error(f"API feature extraction failed: {str(e)}")
            return None

    def _process_threat(self, threat: ThreatEvent) -> Any:
        """Process detected threat"""
        try:
            threat_log = ThreatEventLog(
                event_id=threat.event_id,
                threat_type=threat.threat_type.value,
                severity=threat.severity.name,
                confidence=threat.confidence,
                source_ip=threat.source_ip,
                target_resource=threat.target_resource,
                user_id=threat.user_id,
                session_id=threat.session_id,
                description=threat.description,
                indicators=json.dumps(threat.indicators),
                raw_data=json.dumps(threat.raw_data),
                response_actions=json.dumps(
                    [action.value for action in threat.response_actions]
                ),
                mitre_tactics=json.dumps(threat.mitre_tactics),
                mitre_techniques=json.dumps(threat.mitre_techniques),
            )
            self.db_session.add(threat_log)
            self.db_session.commit()
            self.response_system.execute_response(threat)
            self.threat_counter.labels(
                type=threat.threat_type.value, severity=threat.severity.name
            ).inc()
            for action in threat.response_actions:
                self.response_counter.labels(action=action.value).inc()
            self.logger.info(
                f"Processed threat: {threat.event_id} - {threat.description}"
            )
        except Exception as e:
            self.logger.error(f"Threat processing failed: {str(e)}")

    def get_threat_statistics(self) -> Dict[str, Any]:
        """Get threat detection statistics"""
        try:
            recent_threats = (
                self.db_session.query(ThreatEventLog)
                .filter(
                    ThreatEventLog.timestamp >= datetime.utcnow() - timedelta(hours=24)
                )
                .all()
            )
            total_threats = len(recent_threats)
            threat_types = defaultdict(int)
            severity_counts = defaultdict(int)
            for threat in recent_threats:
                threat_types[threat.threat_type] += 1
                severity_counts[threat.severity] += 1
            return {
                "total_threats_24h": total_threats,
                "threat_types": dict(threat_types),
                "severity_distribution": dict(severity_counts),
                "top_source_ips": self._get_top_source_ips(recent_threats),
                "top_targets": self._get_top_targets(recent_threats),
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            self.logger.error(f"Statistics calculation failed: {str(e)}")
            return {"error": str(e)}

    def _get_top_source_ips(
        self, threats: List[ThreatEventLog]
    ) -> List[Dict[str, Any]]:
        """Get top source IPs from threats"""
        ip_counts = defaultdict(int)
        for threat in threats:
            if threat.source_ip:
                ip_counts[threat.source_ip] += 1
        top_ips = sorted(ip_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        return [{"ip": ip, "count": count} for ip, count in top_ips]

    def _get_top_targets(self, threats: List[ThreatEventLog]) -> List[Dict[str, Any]]:
        """Get top target resources from threats"""
        target_counts = defaultdict(int)
        for threat in threats:
            if threat.target_resource:
                target_counts[threat.target_resource] += 1
        top_targets = sorted(target_counts.items(), key=lambda x: x[1], reverse=True)[
            :10
        ]
        return [
            {"resource": resource, "count": count} for resource, count in top_targets
        ]

    def train_models(self) -> Any:
        """Train anomaly detection models"""
        try:
            self.anomaly_detector.train_models()
            self.logger.info("Threat detection models trained successfully")
        except Exception as e:
            self.logger.error(f"Model training failed: {str(e)}")

    def update_threat_intelligence(self) -> Any:
        """Update threat intelligence data"""
        try:
            self.threat_intel.collect_threat_intelligence()
            self.logger.info("Threat intelligence updated successfully")
        except Exception as e:
            self.logger.error(f"Threat intelligence update failed: {str(e)}")


def create_threat_detection_engine(
    database_url: str, redis_url: str, config: Dict[str, Any]
) -> ThreatDetectionEngine:
    """Factory function to create threat detection engine"""
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    db_session = Session()
    redis_client = redis.from_url(redis_url, decode_responses=True)
    engine = ThreatDetectionEngine(db_session, redis_client, config)
    return engine


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    config = {
        "email_alerts_enabled": True,
        "slack_alerts_enabled": True,
        "sms_alerts_enabled": True,
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_username": "alerts@nexafi.com",
        "smtp_password": "password",
        "alert_recipients": ["admin@nexafi.com"],
        "slack_token": "xoxb-your-token",
        "slack_channel": "#security-alerts",
        "twilio_sid": "your-sid",
        "twilio_token": "your-token",
        "twilio_from": "+1234567890",
        "sms_recipients": ["+1234567890"],
    }
    engine = create_threat_detection_engine(
        database_url="sqlite:///threat_detection.db",
        redis_url="redis://localhost:6379/0",
        config=config,
    )
    engine.train_models()
    engine.update_threat_intelligence()
    event_data = {
        "ip_address": "192.168.1.100",
        "user_id": "user123",
        "session_id": "session456",
        "resource": "/api/financial-data",
        "action": "read",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "timestamp": time.time(),
        "success": True,
        "request_data": {"query_params": "id=1", "post_data": ""},
    }
    threats = engine.analyze_event(event_data)
    logger.info(f"Detected {len(threats)} threats")
    for threat in threats:
        logger.info(f"- {threat.threat_type.value}: {threat.description}")
    stats = engine.get_threat_statistics()
    logger.info(f"Threat Statistics: {json.dumps(stats, indent=2)}")
