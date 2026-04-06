"""
Additional tests for security module components:
CircuitBreaker, RobustEncryption, SecurityManager session management
"""

import json
import os
import sys
import threading
import time
import unittest
from datetime import datetime
from unittest.mock import Mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.security import (
    AdvancedEncryption,
    FraudDetectionEngine,
    MultiFactorAuthentication,
    RobustEncryption,
    SecurityEvent,
    SecurityEventType,
    SecurityMonitor,
    ThreatLevel,
)
from shared.utils.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreaker(unittest.TestCase):

    def test_closed_state_passes_calls(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        result = cb.call(lambda: "ok")
        self.assertEqual(result, "ok")
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        for _ in range(3):
            try:
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass
        self.assertEqual(cb.state, CircuitState.OPEN)

    def test_open_state_raises_immediately(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=9999)
        try:
            cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        except Exception:
            pass
        with self.assertRaises(Exception) as ctx:
            cb.call(lambda: "should not run")
        self.assertIn("OPEN", str(ctx.exception))

    def test_resets_after_recovery_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
        try:
            cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        except Exception:
            pass
        self.assertEqual(cb.state, CircuitState.OPEN)
        time.sleep(1.1)
        result = cb.call(lambda: "recovered")
        self.assertEqual(result, "recovered")
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_should_attempt_reset_with_none_last_failure(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        self.assertTrue(cb._should_attempt_reset())

    def test_resets_failure_count_on_success(self):
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        for _ in range(3):
            try:
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass
        cb.call(lambda: "ok")
        self.assertEqual(cb.failure_count, 0)

    def test_thread_safety(self):
        cb = CircuitBreaker(failure_threshold=100, recovery_timeout=60)
        results = []
        errors = []

        def worker():
            try:
                r = cb.call(lambda: "ok")
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(results), 20)
        self.assertEqual(len(errors), 0)


class TestRobustEncryption(unittest.TestCase):

    def setUp(self):
        self.enc = RobustEncryption("test-master-key-abc")

    def test_encrypt_returns_string(self):
        result = self.enc.encrypt_sensitive_data("hello world")
        self.assertIsInstance(result, str)
        self.assertNotEqual(result, "hello world")

    def test_decrypt_round_trip(self):
        original = "my secret data 12345"
        encrypted = self.enc.encrypt_sensitive_data(original)
        decrypted = self.enc.decrypt_sensitive_data(encrypted)
        self.assertEqual(decrypted, original)

    def test_different_keys_cannot_decrypt(self):
        enc2 = RobustEncryption("different-key")
        encrypted = self.enc.encrypt_sensitive_data("secret")
        with self.assertRaises(ValueError):
            enc2.decrypt_sensitive_data(encrypted)

    def test_tampered_data_raises(self):
        encrypted = self.enc.encrypt_sensitive_data("data")
        tampered = encrypted[:-5] + "XXXXX"
        with self.assertRaises(ValueError):
            self.enc.decrypt_sensitive_data(tampered)


class TestAdvancedEncryptionExtras(unittest.TestCase):

    def setUp(self):
        self.enc = AdvancedEncryption("advanced-test-key")

    def test_max_age_none_always_succeeds(self):
        data = self.enc.encrypt_sensitive_data("test")
        result = self.enc.decrypt_sensitive_data(data, max_age_seconds=None)
        self.assertEqual(result, "test")

    def test_max_age_zero_raises_immediately(self):
        data = self.enc.encrypt_sensitive_data("test")
        with self.assertRaises(ValueError):
            self.enc.decrypt_sensitive_data(data, max_age_seconds=0)

    def test_max_age_generous_succeeds(self):
        data = self.enc.encrypt_sensitive_data("test")
        result = self.enc.decrypt_sensitive_data(data, max_age_seconds=3600)
        self.assertEqual(result, "test")

    def test_field_level_encryption_only_encrypts_specified_fields(self):
        record = {"name": "Alice", "ssn": "123-45-6789", "age": 30}
        encrypted = self.enc.encrypt_field_level(record, ["ssn"])
        self.assertEqual(encrypted["name"], "Alice")
        self.assertEqual(encrypted["age"], 30)
        self.assertNotEqual(encrypted["ssn"], "123-45-6789")

    def test_field_level_decryption_restores_original(self):
        record = {"name": "Alice", "ssn": "123-45-6789", "account": "9999"}
        encrypted = self.enc.encrypt_field_level(record, ["ssn", "account"])
        decrypted = self.enc.decrypt_field_level(encrypted, ["ssn", "account"])
        self.assertEqual(decrypted["ssn"], "123-45-6789")
        self.assertEqual(decrypted["account"], "9999")
        self.assertEqual(decrypted["name"], "Alice")

    def test_field_level_ignores_missing_fields(self):
        record = {"name": "Bob"}
        encrypted = self.enc.encrypt_field_level(record, ["ssn"])
        self.assertEqual(encrypted, {"name": "Bob"})


class TestMultiFactorAuthenticationExtras(unittest.TestCase):

    def setUp(self):
        self.mock_db = Mock()
        self.mock_db.execute_query = Mock(return_value=Mock())
        self.mock_db.fetch_one = Mock(return_value=None)
        self.mfa = MultiFactorAuthentication(self.mock_db)

    def test_setup_totp_returns_valid_secret(self):
        secret, uri, codes = self.mfa.setup_totp("u1", "u1@test.com")
        self.assertGreater(len(secret), 15)
        self.assertIn("otpauth://totp/", uri)
        self.assertEqual(len(codes), 10)

    def test_verify_totp_returns_false_when_no_user(self):
        self.mock_db.fetch_one.return_value = None
        result = self.mfa.verify_totp("nonexistent", "123456")
        self.assertFalse(result)

    def test_verify_backup_code_fails_when_already_used(self):
        used = ["ABCD1234"]
        self.mock_db.fetch_one.return_value = {
            "backup_codes": json.dumps(["ABCD1234", "EFGH5678"]),
            "recovery_codes_used": json.dumps(used),
        }
        result = self.mfa.verify_backup_code("u1", "ABCD1234")
        self.assertFalse(result)

    def test_verify_backup_code_fails_when_not_in_list(self):
        self.mock_db.fetch_one.return_value = {
            "backup_codes": json.dumps(["EFGH5678"]),
            "recovery_codes_used": json.dumps([]),
        }
        result = self.mfa.verify_backup_code("u1", "ZZZZ0000")
        self.assertFalse(result)


class TestSecurityMonitorExtras(unittest.TestCase):

    def setUp(self):
        self.mock_db = Mock()
        self.mock_db.execute_query = Mock(return_value=Mock())
        self.mock_db.fetch_all = Mock(return_value=[])
        self.monitor = SecurityMonitor(self.mock_db)

    def test_log_multiple_events(self):
        for i in range(3):
            event = SecurityEvent(
                event_type=SecurityEventType.LOGIN_ATTEMPT,
                user_id=f"user{i}",
                ip_address="10.0.0.1",
                user_agent="test",
                timestamp=datetime.utcnow(),
                details={},
                threat_level=ThreatLevel.LOW,
            )
            self.monitor.log_security_event(event)
        self.assertEqual(len(self.monitor.security_events), 3)

    def test_get_threat_summary_returns_required_keys(self):
        summary = self.monitor.get_threat_summary(12)
        self.assertIn("time_period_hours", summary)
        self.assertIn("total_events", summary)
        self.assertIn("events_by_type", summary)
        self.assertIn("top_threat_indicators", summary)
        self.assertEqual(summary["time_period_hours"], 12)

    def test_get_threat_summary_totals_events(self):
        self.mock_db.fetch_all.side_effect = [
            [
                {"event_type": "login_failure", "threat_level": "high", "count": 3},
                {"event_type": "login_attempt", "threat_level": "low", "count": 7},
            ],
            [],
        ]
        summary = self.monitor.get_threat_summary(24)
        self.assertEqual(summary["total_events"], 10)


class TestFraudDetectionEngineExtras(unittest.TestCase):

    def setUp(self):
        self.mock_db = Mock()
        self.mock_db.execute_query = Mock(return_value=Mock())
        self.mock_db.fetch_all = Mock(return_value=[])
        self.engine = FraudDetectionEngine(self.mock_db)

    def test_analyze_transaction_low_risk(self):
        score, factors = self.engine.analyze_transaction_behavior(
            "u1", 50.0, "USD", "grocery", "1.2.3.4"
        )
        self.assertEqual(score, 0.0)
        self.assertEqual(factors, [])

    def test_analyze_transaction_high_amount_flag(self):
        score, factors = self.engine.analyze_transaction_behavior(
            "u1", 10000.0, "USD", "grocery", "1.2.3.4"
        )
        self.assertGreaterEqual(score, 40.0)
        self.assertIn("high_amount", factors)

    def test_analyze_transaction_high_risk_merchant(self):
        score, factors = self.engine.analyze_transaction_behavior(
            "u1", 100.0, "USD", "gambling", "1.2.3.4"
        )
        self.assertGreaterEqual(score, 30.0)
        self.assertIn("high_risk_merchant", factors)

    def test_analyze_login_new_device_flagged(self):
        self.mock_db.fetch_all.return_value = []
        score, factors = self.engine.analyze_login_behavior(
            "u1", "192.168.1.1", "Mozilla", "device_xyz"
        )
        self.assertGreater(score, 0)
        self.assertIn("new_device", factors)

    def test_create_fraud_alert_returns_id(self):
        mock_result = Mock()
        mock_result.lastrowid = 99
        self.mock_db.execute_query.return_value = mock_result
        alert_id = self.engine.create_fraud_alert(
            "u1", "test_alert", 80.0, {"reason": "test"}
        )
        self.assertEqual(alert_id, 99)


if __name__ == "__main__":
    unittest.main(verbosity=2)
