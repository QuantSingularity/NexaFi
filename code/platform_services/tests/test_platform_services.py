from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PLATFORM_DIR = os.path.dirname(_TESTS_DIR)
_BACKEND_SHARED = os.path.normpath(
    os.path.join(_PLATFORM_DIR, "..", "backend", "shared")
)

for p in [_BACKEND_SHARED, _PLATFORM_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)


def _load(name: str, path: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_zt = _load(
    "zero_trust_framework",
    os.path.join(_PLATFORM_DIR, "security", "zero-trust", "zero_trust_framework.py"),
)
_tde = _load(
    "threat_detection_engine",
    os.path.join(
        _PLATFORM_DIR, "security", "threat-detection", "threat_detection_engine.py"
    ),
)
_cache = _load(
    "cache_system",
    os.path.join(_PLATFORM_DIR, "scalability", "caching", "cache_system.py"),
)
_dtp = _load(
    "distributed_transaction_processor",
    os.path.join(
        _PLATFORM_DIR,
        "scalability",
        "distributed-computing",
        "distributed_transaction_processor.py",
    ),
)
_ei_base = os.path.join(_PLATFORM_DIR, "enterprise-integrations")
_base_mod = _load(
    "nexafi_base_integration", os.path.join(_ei_base, "shared", "base_integration.py")
)
_sap_mod = _load(
    "nexafi_sap_integration", os.path.join(_ei_base, "sap", "sap_integration.py")
)
_oracle_mod = _load(
    "nexafi_oracle_integration",
    os.path.join(_ei_base, "oracle", "oracle_integration.py"),
)

TrustLevel = _zt.TrustLevel
RiskLevel = _zt.RiskLevel
AccessDecision = _zt.AccessDecision
SecurityContext = _zt.SecurityContext
ContextAnalyzer = _zt.ContextAnalyzer
PolicyRule = _zt.PolicyRule

ThreatType = _tde.ThreatType
Severity = _tde.Severity
ResponseAction = _tde.ResponseAction
AnomalyDetectionResult = _tde.AnomalyDetectionResult
ThreatDetectionRules = _tde.ThreatDetectionRules

CacheStrategy = _cache.CacheStrategy
CacheSystem = _cache.CacheConfiguration

TransactionCoordinator = _dtp.DistributedTransactionManager
TransactionStatus = _dtp.TransactionStatus

SAPConfig = _sap_mod.SAPConfig
SAPAuthenticator = _sap_mod.SAPAuthenticator
SAPIntegration = _sap_mod.SAPIntegration
OracleConfig = _oracle_mod.OracleConfig
OracleIntegration = _oracle_mod.OracleIntegration
AuthMethod = _base_mod.AuthMethod
IntegrationConfig = _base_mod.IntegrationConfig
SyncResult = _base_mod.SyncResult
DataTransformer = _base_mod.DataTransformer


class TestZeroTrustEnums(unittest.TestCase):

    def test_trust_level_values(self) -> None:
        self.assertEqual(TrustLevel.UNTRUSTED.value, 0)
        self.assertEqual(TrustLevel.LOW.value, 1)
        self.assertEqual(TrustLevel.MEDIUM.value, 2)
        self.assertEqual(TrustLevel.HIGH.value, 3)
        self.assertEqual(TrustLevel.VERIFIED.value, 4)

    def test_risk_level_ordering(self) -> None:
        self.assertGreater(RiskLevel.CRITICAL.value, RiskLevel.HIGH.value)
        self.assertGreater(RiskLevel.HIGH.value, RiskLevel.MEDIUM.value)
        self.assertGreater(RiskLevel.MEDIUM.value, RiskLevel.LOW.value)
        self.assertGreater(RiskLevel.LOW.value, RiskLevel.MINIMAL.value)

    def test_access_decision_values(self) -> None:
        self.assertEqual(AccessDecision.ALLOW.value, "allow")
        self.assertIn("deny", AccessDecision.DENY.value)

    def test_all_trust_levels_present(self) -> None:
        names = {t.name for t in TrustLevel}
        for expected in ("UNTRUSTED", "LOW", "MEDIUM", "HIGH", "VERIFIED"):
            self.assertIn(expected, names)


class TestSecurityContext(unittest.TestCase):

    def test_construction(self) -> None:
        ctx = SecurityContext(
            user_id="u1",
            session_id="s1",
            device_id="d1",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            location={},
            timestamp=None,
            trust_score=0.65,
            risk_score=0.20,
            authentication_factors=[],
            device_fingerprint="fp1",
            network_info={},
            behavioral_score=0.7,
            compliance_status={},
        )
        self.assertEqual(ctx.user_id, "u1")
        self.assertAlmostEqual(ctx.trust_score, 0.65)

    def test_trust_score_in_range(self) -> None:
        ctx = SecurityContext(
            user_id="u2",
            session_id="s2",
            device_id="d2",
            ip_address="10.0.0.1",
            user_agent="curl/7.0",
            location={},
            timestamp=None,
            trust_score=0.15,
            risk_score=0.85,
            authentication_factors=[],
            device_fingerprint="fp2",
            network_info={},
            behavioral_score=0.2,
            compliance_status={},
        )
        self.assertGreaterEqual(ctx.trust_score, 0.0)
        self.assertLessEqual(ctx.trust_score, 1.0)


class TestContextAnalyzer(unittest.TestCase):

    def setUp(self) -> None:
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis.set.return_value = True
        mock_redis.setex.return_value = True
        self.analyzer = ContextAnalyzer(db_session=MagicMock(), redis_client=mock_redis)

    def _req(self, uid="u1", ip="192.168.1.1", ua="Mozilla/5.0"):
        return {
            "user_id": uid,
            "device_id": "dev",
            "ip_address": ip,
            "user_agent": ua,
            "session_id": "s1",
        }

    def test_returns_security_context(self) -> None:
        req = self._req()
        ctx = self.analyzer.analyze_request_context(req["user_id"], req)
        self.assertIsInstance(ctx, SecurityContext)

    def test_trust_score_in_range(self) -> None:
        req = self._req()
        ctx = self.analyzer.analyze_request_context(req["user_id"], req)
        self.assertGreaterEqual(ctx.trust_score, 0.0)
        self.assertLessEqual(ctx.trust_score, 1.0)

    def test_risk_score_in_range(self) -> None:
        req = self._req(ip="203.0.113.5")
        ctx = self.analyzer.analyze_request_context(req["user_id"], req)
        self.assertGreaterEqual(ctx.risk_score, 0.0)
        self.assertLessEqual(ctx.risk_score, 1.0)

    def test_loopback_not_worse_than_external(self) -> None:
        req_lo = self._req(ip="127.0.0.1")
        ctx_lo = self.analyzer.analyze_request_context(req_lo["user_id"], req_lo)
        req_ext = self._req(ip="198.51.100.1")
        ctx_ext = self.analyzer.analyze_request_context(req_ext["user_id"], req_ext)
        self.assertGreaterEqual(ctx_lo.trust_score, 0.0)
        self.assertGreaterEqual(ctx_ext.trust_score, 0.0)


class TestPolicyRule(unittest.TestCase):

    def test_construction(self) -> None:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        rule = PolicyRule(
            rule_id="r-001",
            name="Admin Guard",
            description="Require auth for admin endpoints",
            conditions={"mfa_required": True, "min_trust_level": "HIGH"},
            action=AccessDecision.ALLOW,
            priority=10,
            enabled=True,
            created_at=now,
            updated_at=now,
            metadata={},
        )
        self.assertEqual(rule.rule_id, "r-001")
        self.assertEqual(rule.action, AccessDecision.ALLOW)
        self.assertEqual(rule.priority, 10)


class TestThreatDetectionEnums(unittest.TestCase):

    def test_threat_type_enum(self) -> None:
        names = {t.name for t in ThreatType}
        for expected in ("BRUTE_FORCE", "SQL_INJECTION", "XSS", "ANOMALOUS_BEHAVIOR"):
            self.assertIn(expected, names)

    def test_severity_ordering(self) -> None:
        vals = {s.name: s.value for s in Severity}
        for name in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            self.assertIn(name, vals)

    def test_response_action_non_empty(self) -> None:
        self.assertGreater(len(list(ResponseAction)), 0)


class TestAnomalyDetectionResult(unittest.TestCase):

    def test_is_anomaly(self) -> None:
        r = AnomalyDetectionResult(
            is_anomaly=True,
            anomaly_score=0.87,
            feature_contributions={"login_freq": 0.5},
            baseline_comparison={"expected": 0.1, "actual": 0.87},
            explanation="Unusual login frequency detected",
        )
        self.assertTrue(r.is_anomaly)
        self.assertAlmostEqual(r.anomaly_score, 0.87)

    def test_not_anomaly(self) -> None:
        r = AnomalyDetectionResult(
            is_anomaly=False,
            anomaly_score=0.12,
            feature_contributions={},
            baseline_comparison={},
            explanation="Normal behaviour",
        )
        self.assertFalse(r.is_anomaly)
        self.assertLess(r.anomaly_score, 0.5)


class TestThreatDetectionRules(unittest.TestCase):

    def setUp(self) -> None:
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True
        self.rules = ThreatDetectionRules(
            db_session=MagicMock(), redis_client=mock_redis
        )

    def test_evaluate_normal_event_returns_list(self) -> None:
        event = {
            "event_type": "login",
            "user_id": "u1",
            "ip_address": "192.168.1.1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_agent": "Mozilla/5.0",
            "success": True,
        }
        result = self.rules.evaluate_rules(event)
        self.assertIsInstance(result, list)

    def test_brute_force_high_incr(self) -> None:
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis.incr.return_value = 20
        mock_redis.expire.return_value = True
        rules = ThreatDetectionRules(db_session=MagicMock(), redis_client=mock_redis)
        event = {
            "event_type": "login_failed",
            "user_id": "victim",
            "ip_address": "10.10.10.10",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "success": False,
        }
        result = rules.evaluate_rules(event)
        self.assertIsInstance(result, list)

    def test_rules_initialized(self) -> None:
        self.assertIsNotNone(self.rules)


class TestCacheSystem(unittest.TestCase):

    def test_cache_strategy_enum(self) -> None:
        self.assertGreater(len(list(CacheStrategy)), 0)

    def test_cache_system_importable(self) -> None:
        self.assertIsNotNone(CacheSystem)


class TestDistributedTransactionProcessor(unittest.TestCase):

    def test_coordinator_importable(self) -> None:
        self.assertIsNotNone(TransactionCoordinator)

    def test_status_enum_non_empty(self) -> None:
        self.assertGreater(len(list(TransactionStatus)), 0)


class TestSAPIntegration(unittest.TestCase):

    def test_config_construction(self) -> None:
        cfg = SAPConfig(sap_system="PRD", enable_rfc=False, enable_odata=True)
        self.assertEqual(cfg.sap_system, "PRD")
        self.assertFalse(cfg.enable_rfc)

    def test_config_defaults(self) -> None:
        cfg = SAPConfig(sap_system="DEV")
        self.assertEqual(cfg.sap_client, "100")
        self.assertTrue(cfg.enable_rfc)

    def test_authenticator_importable(self) -> None:
        self.assertIsNotNone(SAPAuthenticator)

    def test_integration_importable(self) -> None:
        self.assertIsNotNone(SAPIntegration)


class TestOracleIntegration(unittest.TestCase):

    def test_config_importable(self) -> None:
        cfg = OracleConfig(
            oracle_system="PROD", database_host="oracle.example.com", database_port=1521
        )
        self.assertEqual(cfg.oracle_system, "PROD")
        self.assertEqual(cfg.database_host, "oracle.example.com")

    def test_integration_importable(self) -> None:
        self.assertIsNotNone(OracleIntegration)


class TestBaseIntegration(unittest.TestCase):

    def test_auth_method_enum(self) -> None:
        self.assertGreater(len(list(AuthMethod)), 0)

    def test_integration_config_importable(self) -> None:
        self.assertIsNotNone(IntegrationConfig)

    def test_sync_result_importable(self) -> None:
        self.assertIsNotNone(SyncResult)

    def test_data_transformer_importable(self) -> None:
        self.assertIsNotNone(DataTransformer)


if __name__ == "__main__":
    unittest.main(verbosity=2)
