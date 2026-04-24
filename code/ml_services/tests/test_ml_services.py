"""
Tests for NexaFi ML Services
Tests for the AI service, analytics service, and explainable AI engine.
"""

import os
import sys
import unittest

# Add backend shared and ml_services to path
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_ML_SERVICES_DIR = os.path.dirname(_TESTS_DIR)
_BACKEND_SHARED = os.path.join(_ML_SERVICES_DIR, "..", "backend", "shared")
sys.path.insert(0, _ML_SERVICES_DIR)
sys.path.insert(0, _BACKEND_SHARED)


class TestExplainableAIEngine(unittest.TestCase):
    """Tests that the explainable AI engine module is accessible and structured correctly."""

    def test_engine_module_accessible(self):
        """Explainable AI engine module file should exist."""
        engine_path = os.path.join(
            _ML_SERVICES_DIR,
            "ai-explainability",
            "model-interpretation",
            "explainable_ai_engine.py",
        )
        self.assertTrue(
            os.path.exists(engine_path), f"Engine file missing: {engine_path}"
        )

    def test_explanation_type_enum_importable(self):
        """ExplanationType enum should import cleanly when dependencies are available."""
        try:
            from ai_explainability.model_interpretation.explainable_ai_engine import (
                ExplanationType,
            )

            self.assertTrue(hasattr(ExplanationType, "GLOBAL"))
            self.assertTrue(hasattr(ExplanationType, "LOCAL"))
            self.assertTrue(hasattr(ExplanationType, "SHAP_VALUES"))
        except ImportError as e:
            self.skipTest(f"Optional ML dependency not installed: {e}")


class TestAIService(unittest.TestCase):
    """Tests AI service structure and basic imports."""

    def test_ai_service_main_exists(self):
        """AI service main.py should exist."""
        main_path = os.path.join(_ML_SERVICES_DIR, "ai-service", "src", "main.py")
        self.assertTrue(os.path.exists(main_path))

    def test_ai_service_routes_exist(self):
        """AI service routes file should exist."""
        routes_path = os.path.join(
            _ML_SERVICES_DIR, "ai-service", "src", "routes", "user.py"
        )
        self.assertTrue(os.path.exists(routes_path))

    def test_ai_service_models_exist(self):
        """AI service models file should exist."""
        models_path = os.path.join(
            _ML_SERVICES_DIR, "ai-service", "src", "models", "user.py"
        )
        self.assertTrue(os.path.exists(models_path))

    def test_ai_service_migrations_exist(self):
        """AI service migrations file should exist."""
        mig_path = os.path.join(_ML_SERVICES_DIR, "ai-service", "src", "migrations.py")
        self.assertTrue(os.path.exists(mig_path))


class TestAnalyticsService(unittest.TestCase):
    """Tests analytics service structure."""

    def test_analytics_service_main_exists(self):
        """Analytics service main.py should exist."""
        main_path = os.path.join(
            _ML_SERVICES_DIR, "analytics-service", "src", "main.py"
        )
        self.assertTrue(os.path.exists(main_path))

    def test_analytics_service_routes_exist(self):
        """Analytics service routes file should exist."""
        routes_path = os.path.join(
            _ML_SERVICES_DIR, "analytics-service", "src", "routes", "user.py"
        )
        self.assertTrue(os.path.exists(routes_path))

    def test_analytics_service_migrations_exist(self):
        """Analytics service migrations file should exist."""
        mig_path = os.path.join(
            _ML_SERVICES_DIR, "analytics-service", "src", "migrations.py"
        )
        self.assertTrue(os.path.exists(mig_path))


class TestSharedPathResolution(unittest.TestCase):
    """Tests that the shared backend library is reachable from ml_services."""

    def test_backend_shared_reachable(self):
        """backend/shared should be importable from ml_services."""
        shared_path = os.path.normpath(
            os.path.join(_ML_SERVICES_DIR, "..", "backend", "shared")
        )
        self.assertTrue(
            os.path.exists(shared_path),
            f"backend/shared not found at: {shared_path}",
        )

    def test_database_manager_importable(self):
        """shared database manager should be importable."""
        from database.manager import initialize_database

        self.assertTrue(callable(initialize_database))


if __name__ == "__main__":
    unittest.main()
