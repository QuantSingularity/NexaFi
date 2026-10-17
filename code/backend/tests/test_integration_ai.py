import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import requests

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SHARED = os.path.join(BACKEND, "shared")
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

from database.manager import BaseModel, DatabaseManager


class Thing(BaseModel):
    table_name = "things"


class TestBaseModel(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = DatabaseManager(os.path.join(self.dir, "t.db"))
        self.db.execute_update(
            "CREATE TABLE things (id TEXT PRIMARY KEY, name TEXT, payload TEXT, flag INTEGER DEFAULT 0, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP, extra REAL)"
        )
        self.db.execute_update(
            "CREATE TABLE counters (id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT)"
        )
        BaseModel.set_db_manager(self.db)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_save_with_preassigned_id_inserts(self):
        Thing(id="abc", name="x").save()
        self.assertEqual(Thing.count(), 1)
        self.assertEqual(Thing.find_by_id("abc").name, "x")

    def test_save_twice_updates(self):
        thing = Thing(id="abc", name="x")
        thing.save()
        thing.name = "y"
        thing.save()
        self.assertEqual(Thing.count(), 1)
        self.assertEqual(Thing.find_by_id("abc").name, "y")

    def test_text_primary_key_generated_when_missing(self):
        thing = Thing(name="auto").save()
        self.assertTrue(thing.id)
        self.assertEqual(Thing.find_by_id(thing.id).name, "auto")

    def test_integer_primary_key_uses_lastrowid(self):
        class Counter(BaseModel):
            table_name = "counters"

        first = Counter(label="a").save()
        second = Counter(label="b").save()
        self.assertEqual((first.id, second.id), (1, 2))

    def test_dict_list_bool_values_are_adapted(self):
        thing = Thing(id="d", payload={"a": [1, 2]}, flag=True).save()
        row = self.db.fetch_one("SELECT payload, flag FROM things WHERE id = 'd'")
        self.assertEqual(row["payload"], '{"a": [1, 2]}')
        self.assertEqual(row["flag"], 1)
        self.assertIsInstance(thing.payload, str)

    def test_missing_columns_default_to_none_and_db_defaults_load(self):
        thing = Thing(id="m").save()
        self.assertIsNone(thing.extra)
        self.assertTrue(thing.created_at)

    def test_find_all_ordering_limit_and_injection_guard(self):
        for i in range(5):
            Thing(id=f"i{i}", name=str(i)).save()
        rows = Thing.find_all("", (), order_by="name DESC", limit=2, offset=1)
        self.assertEqual([r.name for r in rows], ["3", "2"])
        with self.assertRaises(ValueError):
            Thing.find_all("", (), order_by="name; DROP TABLE things")

    def test_delete(self):
        thing = Thing(id="z", name="gone").save()
        thing.delete()
        self.assertIsNone(Thing.find_by_id("z"))


def load_service(name, kind="backend"):
    base = os.path.abspath(os.path.join(BACKEND, ".."))
    root = os.path.join(base, kind, name, "src")
    tmp = tempfile.mkdtemp()
    shutil.copytree(root, os.path.join(tmp, "src"))
    for path in (os.path.join(tmp, "src"), SHARED):
        if path not in sys.path:
            sys.path.insert(0, path)
    for key in list(sys.modules):
        if key.split(".")[0] in (
            "routes",
            "models",
            "ai_scoring",
            "fraud_screening",
            "main",
        ):
            sys.modules.pop(key, None)
    spec = importlib.util.spec_from_file_location(
        "main", os.path.join(tmp, "src", "main.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, tmp


class TestCreditServiceAIIntegration(unittest.TestCase):
    def setUp(self):
        self.module, self.tmp = load_service("credit-service")
        self.client = self.module.app.test_client()
        self.headers = {"X-User-ID": "u1"}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _ai(self, score=712):
        response = MagicMock(status_code=200)
        response.json.return_value = {
            "credit_score": score,
            "data_completeness": 0.75,
            "risk_category": "good",
            "decision": "approve",
            "probability_of_default": 0.03,
            "factors": {"payment_history_score": 20.0},
            "recommendations": ["Pay on time"],
            "model": {"version": 1},
            "prediction_id": "p1",
        }
        return response

    def test_uses_ai_scorecard_and_stores_details(self):
        with patch("requests.post", return_value=self._ai()) as post:
            response = self.client.post(
                "/api/v1/credit/scores",
                headers=self.headers,
                json={"input_features": {"annual_income": 90000}},
            )
        self.assertEqual(response.status_code, 201)
        body = response.get_json()
        self.assertEqual(body["score"], 712)
        self.assertEqual(body["calculation_details"]["method"], "ai_scorecard")
        self.assertEqual(body["confidence_score"], 0.75)
        self.assertEqual(post.call_args.kwargs["headers"]["X-User-ID"], "u1")
        self.assertIn("timeout", post.call_args.kwargs)

    def test_falls_back_to_rules_when_ai_is_down(self):
        with patch("requests.post", side_effect=requests.ConnectionError()):
            response = self.client.post(
                "/api/v1/credit/scores",
                headers=self.headers,
                json={"input_features": {"annual_income": 120000, "total_debt": 5000}},
            )
        body = response.get_json()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(body["calculation_details"]["method"], "rule_based_fallback")
        self.assertEqual(body["score"], 720)

    def test_scores_are_persisted_and_latest_is_current(self):
        with patch("requests.post", side_effect=requests.ConnectionError()):
            self.client.post(
                "/api/v1/credit/scores",
                headers=self.headers,
                json={"input_features": {"annual_income": 120000}},
            )
            self.client.post(
                "/api/v1/credit/scores",
                headers=self.headers,
                json={"input_features": {"annual_income": 20000}},
            )
        current = self.client.get("/api/v1/credit/scores/current", headers=self.headers)
        self.assertEqual(current.get_json()["score"], 640)
        rows = BaseModel.db_manager.fetch_all("SELECT is_current FROM credit_scores")
        self.assertEqual(sorted(r["is_current"] for r in rows), [0, 1])

    def test_input_validation(self):
        self.assertEqual(
            self.client.post(
                "/api/v1/credit/scores",
                headers=self.headers,
                json={"input_features": {}},
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/credit/scores", headers=self.headers, data="x"
            ).status_code,
            400,
        )
        with patch("requests.post", side_effect=requests.ConnectionError()):
            bad = self.client.post(
                "/api/v1/credit/scores",
                headers=self.headers,
                json={"input_features": {"annual_income": "lots"}},
            )
        self.assertEqual(bad.status_code, 400)


class TestPaymentFraudScreening(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)
        self.module, self.tmp = load_service("payment-service")
        self.client = self.module.app.test_client()
        self.headers = {"X-User-ID": "u1"}

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _risk(self, action):
        response = MagicMock(status_code=200)
        response.json.return_value = {
            "risk_score": 0.9,
            "risk_level": "high",
            "recommended_action": action,
            "reasons": ["x"],
        }
        return response

    def _post(self, amount=500):
        return self.client.post(
            "/api/v1/transactions",
            headers=self.headers,
            json={"amount": amount, "transaction_type": "payment"},
        )

    def test_monitor_mode_records_risk_without_blocking(self):
        os.environ["FRAUD_SCREENING_MODE"] = "monitor"
        with patch("requests.post", return_value=self._risk("block")):
            response = self._post()
        self.assertEqual(response.status_code, 201)
        stored = BaseModel.db_manager.fetch_one("SELECT metadata FROM transactions")
        self.assertIn('"risk"', stored["metadata"])

    def test_enforce_mode_blocks_high_risk(self):
        os.environ["FRAUD_SCREENING_MODE"] = "enforce"
        with patch("requests.post", return_value=self._risk("block")):
            response = self._post()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            BaseModel.db_manager.fetch_all("SELECT id FROM transactions"), []
        )

    def test_review_action_is_allowed_in_enforce_mode(self):
        os.environ["FRAUD_SCREENING_MODE"] = "enforce"
        with patch("requests.post", return_value=self._risk("review")):
            self.assertEqual(self._post().status_code, 201)

    def test_review_can_be_blocked_when_configured(self):
        os.environ["FRAUD_SCREENING_MODE"] = "enforce"
        os.environ["FRAUD_SCREENING_BLOCK_ON"] = "review"
        with patch("requests.post", return_value=self._risk("review")):
            self.assertEqual(self._post().status_code, 403)

    def test_fail_open_and_fail_closed(self):
        os.environ["FRAUD_SCREENING_MODE"] = "enforce"
        with patch("requests.post", side_effect=requests.ConnectionError()):
            self.assertEqual(self._post().status_code, 201)
            os.environ["FRAUD_SCREENING_FAIL_CLOSED"] = "true"
            self.assertEqual(self._post().status_code, 403)

    def test_off_mode_never_calls_ai(self):
        os.environ["FRAUD_SCREENING_MODE"] = "off"
        with patch("requests.post") as post:
            self.assertEqual(self._post().status_code, 201)
        post.assert_not_called()

    def test_input_errors_are_client_errors(self):
        os.environ["FRAUD_SCREENING_MODE"] = "off"
        self.assertEqual(
            self.client.post(
                "/api/v1/transactions", headers=self.headers, data="x"
            ).status_code,
            400,
        )
        self.assertEqual(self._post("abc").status_code, 400)
        self.assertEqual(self._post(-5).status_code, 400)

    def test_listing_is_paginated(self):
        os.environ["FRAUD_SCREENING_MODE"] = "off"
        for _ in range(3):
            self._post(10)
        body = self.client.get(
            "/api/v1/transactions?per_page=2", headers=self.headers
        ).get_json()
        self.assertEqual(
            (body["total"], len(body["transactions"]), body["per_page"]), (3, 2, 2)
        )


class TestInternalKeyMiddleware(unittest.TestCase):
    def test_requires_key_when_configured(self):
        from flask import Flask, jsonify
        from middleware.internal import install_internal_auth

        with patch.dict(os.environ, {"INTERNAL_SERVICE_KEY": "secret"}):
            app = Flask(__name__)
            self.assertTrue(install_internal_auth(app))

            @app.route("/api/v1/data")
            def data():
                return jsonify({"ok": True})

            @app.route("/api/v1/thing/health")
            def health():
                return jsonify({"ok": True})

            client = app.test_client()
            self.assertEqual(client.get("/api/v1/data").status_code, 403)
            self.assertEqual(
                client.get(
                    "/api/v1/data", headers={"X-Internal-Key": "nope"}
                ).status_code,
                403,
            )
            self.assertEqual(
                client.get(
                    "/api/v1/data", headers={"X-Internal-Key": "secret"}
                ).status_code,
                200,
            )
            self.assertEqual(client.get("/api/v1/thing/health").status_code, 200)

    def test_inactive_without_key(self):
        from flask import Flask
        from middleware.internal import install_internal_auth

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("INTERNAL_SERVICE_KEY", None)
            self.assertFalse(install_internal_auth(Flask(__name__)))


class TestGatewayHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault(
            "SECRET_KEY", "gateway-test-secret-key-with-enough-length"
        )
        cls.module, cls.tmp = load_service("api-gateway")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_longest_prefix_routing(self):
        name, _ = self.module.get_service_for_route("/api/v1/analytics/dashboards")
        self.assertEqual(name, "analytics-service")
        self.assertEqual(
            self.module.get_service_for_route("/api/v1/credit/scores")[0],
            "credit-service",
        )
        self.assertEqual(
            self.module.get_service_for_route("/api/v1/predictions/credit-score")[0],
            "ai-service",
        )
        self.assertEqual(
            self.module.get_service_for_route("/api/v1/anomalies/score")[0],
            "ai-service",
        )
        self.assertIsNone(self.module.get_service_for_route("/api/v1/unknown")[0])
        self.assertIsNone(self.module.get_service_for_route("/api/v1/paymentsx")[0])

    def test_protected_routes_require_authentication(self):
        client = self.module.app.test_client()
        response = client.get("/api/v1/predictions", headers={"X-User-ID": "spoofed"})
        self.assertEqual(response.status_code, 401)

    def test_circuit_breaker_failure_count_resets_on_success(self):
        state = self.module.circuit_breaker_state
        name = "ai-service"
        self.module.record_service_failure(name)
        state[name]["failure_count"] = 0
        self.module.record_service_failure(name)
        self.module.record_service_failure(name)
        self.module.record_service_success(name)
        self.assertEqual(state[name]["failure_count"], 0)
        self.assertEqual(state[name]["state"], "closed")

    def test_forwarded_identity_comes_from_verified_token(self):
        module = self.module
        with module.app.test_request_context(
            "/api/v1/predictions", headers={"X-User-ID": "spoofed"}
        ):
            module.g.current_user = {"user_id": "real", "roles": ["admin"]}
            captured = {}

            def fake_get(url, headers=None, params=None, timeout=None):
                captured.update(headers)
                response = MagicMock(status_code=200, content=b"{}")
                response.json.return_value = {}
                return response

            with patch.object(module.requests, "get", side_effect=fake_get):
                module.forward_request(
                    "ai-service",
                    module.SERVICES["ai-service"],
                    "/api/v1/predictions",
                    "GET",
                    {"X-User-ID": "spoofed", "Authorization": "Bearer x"},
                    None,
                    None,
                )
        self.assertEqual(captured["X-User-ID"], "real")
        self.assertEqual(captured["X-User-Roles"], "admin")

    def test_post_is_not_retried(self):
        module = self.module
        calls = []

        def boom(*args, **kwargs):
            calls.append(1)
            raise requests.Timeout()

        with module.app.test_request_context("/api/v1/payments", method="POST"):
            with patch.object(module.requests, "post", side_effect=boom):
                module.forward_request(
                    "payment-service",
                    module.SERVICES["payment-service"],
                    "/api/v1/payments",
                    "POST",
                    {},
                    {"a": 1},
                    None,
                )
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
