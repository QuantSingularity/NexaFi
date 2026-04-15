"""
Tests for NexaFi Platform Services
Tests for security engines, scalability modules, and enterprise integrations.
"""

import os
import sys
import unittest

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PLATFORM_DIR = os.path.dirname(_TESTS_DIR)
_BACKEND_SHARED = os.path.normpath(
    os.path.join(_PLATFORM_DIR, "..", "backend", "shared")
)
sys.path.insert(0, _PLATFORM_DIR)
sys.path.insert(0, _BACKEND_SHARED)


class TestSecurityModules(unittest.TestCase):
    """Tests that security engine modules are accessible."""

    def test_threat_detection_engine_exists(self):
        """Threat detection engine file should exist."""
        engine_path = os.path.join(
            _PLATFORM_DIR, "security", "threat-detection", "threat_detection_engine.py"
        )
        self.assertTrue(os.path.exists(engine_path), f"Missing: {engine_path}")

    def test_zero_trust_framework_exists(self):
        """Zero trust framework file should exist."""
        zt_path = os.path.join(
            _PLATFORM_DIR, "security", "zero-trust", "zero_trust_framework.py"
        )
        self.assertTrue(os.path.exists(zt_path), f"Missing: {zt_path}")


class TestScalabilityModules(unittest.TestCase):
    """Tests that scalability modules are accessible."""

    def test_cache_system_exists(self):
        """Cache system file should exist."""
        cache_path = os.path.join(
            _PLATFORM_DIR, "scalability", "caching", "cache_system.py"
        )
        self.assertTrue(os.path.exists(cache_path), f"Missing: {cache_path}")

    def test_distributed_processor_exists(self):
        """Distributed transaction processor file should exist."""
        dist_path = os.path.join(
            _PLATFORM_DIR,
            "scalability",
            "distributed-computing",
            "distributed_transaction_processor.py",
        )
        self.assertTrue(os.path.exists(dist_path), f"Missing: {dist_path}")


class TestEnterpriseIntegrations(unittest.TestCase):
    """Tests that enterprise integration modules are accessible."""

    def test_sap_integration_exists(self):
        """SAP integration file should exist."""
        sap_path = os.path.join(
            _PLATFORM_DIR, "enterprise-integrations", "sap", "sap_integration.py"
        )
        self.assertTrue(os.path.exists(sap_path))

    def test_oracle_integration_exists(self):
        """Oracle integration file should exist."""
        oracle_path = os.path.join(
            _PLATFORM_DIR, "enterprise-integrations", "oracle", "oracle_integration.py"
        )
        self.assertTrue(os.path.exists(oracle_path))

    def test_base_integration_exists(self):
        """Base integration framework file should exist."""
        base_path = os.path.join(
            _PLATFORM_DIR, "enterprise-integrations", "shared", "base_integration.py"
        )
        self.assertTrue(os.path.exists(base_path))

    def test_integration_manager_exists(self):
        """Integration manager file should exist."""
        mgr_path = os.path.join(
            _PLATFORM_DIR, "enterprise-integrations", "shared", "integration_manager.py"
        )
        self.assertTrue(os.path.exists(mgr_path))


class TestSharedPathResolution(unittest.TestCase):
    """Tests that the shared backend library is reachable from platform_services."""

    def test_backend_shared_reachable(self):
        shared_path = _BACKEND_SHARED
        self.assertTrue(
            os.path.exists(shared_path), f"backend/shared not found: {shared_path}"
        )

    def test_circuit_breaker_importable(self):
        """CircuitBreaker from shared utils should be importable."""
        from utils.circuit_breaker import CircuitBreaker

        self.assertTrue(callable(CircuitBreaker))


if __name__ == "__main__":
    unittest.main()
