import jwt
from tests.conftest import FakePayments

FLOWS = [100 + (i % 7) * 15 + i for i in range(60)]


def test_health_reports_model_provenance(client):
    body = client.get("/api/v1/health").get_json()
    assert body["status"] == "healthy"
    assert body["credit_model_training_data"] == "synthetic_bootstrap"


def test_authentication_modes(client, ai_app):
    assert client.get("/api/v1/models").status_code == 401
    assert client.get("/api/v1/models", headers={"X-User-ID": "u1"}).status_code == 401
    assert (
        client.get(
            "/api/v1/models", headers={"X-User-ID": "u1", "X-Internal-Key": "wrong"}
        ).status_code
        == 401
    )
    token = jwt.encode(
        {"user_id": "u9", "type": "access"},
        ai_app.config["SECRET_KEY"],
        algorithm="HS256",
    )
    assert (
        client.get(
            "/api/v1/predictions", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 200
    )
    refresh = jwt.encode(
        {"user_id": "u9", "type": "refresh"},
        ai_app.config["SECRET_KEY"],
        algorithm="HS256",
    )
    assert (
        client.get(
            "/api/v1/predictions", headers={"Authorization": f"Bearer {refresh}"}
        ).status_code
        == 401
    )
    forged = jwt.encode(
        {"user_id": "u9", "type": "access"},
        "other-secret-key-with-enough-length-1234",
        algorithm="HS256",
    )
    assert (
        client.get(
            "/api/v1/predictions", headers={"Authorization": f"Bearer {forged}"}
        ).status_code
        == 401
    )


def test_unknown_api_paths_return_json_404(client, headers):
    response = client.get("/api/v1/nope", headers=headers)
    assert response.status_code == 404 and response.get_json()["code"] == "NOT_FOUND"


def test_models_endpoint_lists_real_metrics(client, headers):
    models = {
        m["name"]: m
        for m in client.get("/api/v1/models", headers=headers).get_json()["models"]
    }
    assert {
        "credit_scorecard",
        "cash_flow_forecaster",
        "transaction_anomaly_detector",
    } <= set(models)
    assert 0.6 < models["credit_scorecard"]["performance_metrics"]["auc"] < 0.95
    assert (
        models["credit_scorecard"]["training_data_info"]["source"]
        == "synthetic_bootstrap"
    )


def test_cash_flow_prediction_is_persisted_and_scoped_to_user(client, headers):
    response = client.post(
        "/api/v1/predictions/cash-flow",
        headers=headers,
        json={"historical_data": {"daily_cash_flows": FLOWS}, "days_ahead": 5},
    )
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert len(body["forecast"]) == 5 and body["metrics"]["cv_mae"] >= 0
    listed = client.get(
        "/api/v1/predictions?type=cash_flow", headers=headers
    ).get_json()
    assert listed["total"] == 1
    other = {**headers, "X-User-ID": "user-2"}
    assert client.get("/api/v1/predictions", headers=other).get_json()["total"] == 0
    assert (
        client.get(
            f"/api/v1/predictions/{body['prediction_id']}", headers=other
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/predictions/{body['prediction_id']}", headers=headers
        ).status_code
        == 200
    )


def test_cash_flow_from_payment_history(ai_app, client, headers):
    transactions = [
        {"date": f"2026-09-{d:02d}", "amount": 100 + d, "type": "credit"}
        for d in range(1, 29)
    ]
    ai_app.extensions["services"].payments = FakePayments(transactions)
    response = client.post(
        "/api/v1/predictions/cash-flow",
        headers=headers,
        json={"source": "payments", "days_ahead": 3},
    )
    assert response.status_code == 200
    assert response.get_json()["summary"]["data_source"] == "transactions"


def test_cash_flow_errors_are_client_errors(client, headers):
    assert (
        client.post(
            "/api/v1/predictions/cash-flow",
            headers=headers,
            json={"historical_data": {}},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/predictions/cash-flow",
            headers=headers,
            json={"historical_data": {"daily_cash_flows": FLOWS}, "days_ahead": 999},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/v1/predictions/cash-flow",
            headers=headers,
            data="x",
            content_type="application/json",
        ).status_code
        == 400
    )


def test_credit_score_endpoint(client, headers):
    response = client.post(
        "/api/v1/predictions/credit-score",
        headers=headers,
        json={
            "business_data": {
                "annual_revenue": 800000,
                "payment_history_score": 85,
                "credit_utilization": 0.2,
            }
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    assert (
        300 <= body["credit_score"] <= 850
        and body["model"]["training_data"] == "synthetic_bootstrap"
    )
    assert body["factor_details"][0]["points"] != 0
    assert (
        client.post(
            "/api/v1/predictions/credit-score",
            headers=headers,
            json={"business_data": {}},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/v1/predictions/credit-score",
            headers=headers,
            json={"business_data": {"payment_history_score": 500}},
        ).status_code
        == 400
    )


def test_anomaly_endpoints_and_persistence_of_flagged_only(client, headers):
    low = client.post(
        "/api/v1/anomalies/score",
        headers=headers,
        json={"transaction": {"amount": 20, "timestamp": "2026-10-01T10:00:00Z"}},
    )
    assert low.get_json()["risk_level"] == "low"
    high = client.post(
        "/api/v1/anomalies/score",
        headers=headers,
        json={"transaction": {"amount": 90000, "timestamp": "2026-10-01T03:00:00Z"}},
    )
    assert high.get_json()["risk_level"] != "low"
    stored = client.get(
        "/api/v1/predictions?type=anomaly_detection", headers=headers
    ).get_json()
    assert stored["total"] == 1
    batch = client.post(
        "/api/v1/anomalies/batch",
        headers=headers,
        json={
            "transactions": [{"amount": 10, "timestamp": "2026-10-01T10:00:00Z"}] * 3
        },
    )
    assert batch.get_json()["reviewed"] == 3
    assert (
        client.post(
            "/api/v1/anomalies/batch", headers=headers, json={"transactions": []}
        ).status_code
        == 400
    )


def test_insights_lifecycle(client, headers):
    payload = {
        "financial_data": {
            "expenses_by_category": {"marketing": [1000, 1100, 900, 1000, 2500]}
        }
    }
    created = client.post("/api/v1/insights/generate", headers=headers, json=payload)
    assert created.status_code == 201 and created.get_json()["count"] == 1
    insight = created.get_json()["insights"][0]
    assert "2,500" in insight["description"]
    assert (
        client.post(
            f"/api/v1/insights/{insight['id']}/read", headers=headers
        ).get_json()["is_read"]
        is True
    )
    assert (
        client.get("/api/v1/insights?unread=true", headers=headers).get_json()["total"]
        == 0
    )
    client.put(
        f"/api/v1/insights/{insight['id']}",
        headers=headers,
        json={"is_dismissed": True},
    )
    assert client.get("/api/v1/insights", headers=headers).get_json()["total"] == 0
    assert (
        client.put("/api/v1/insights/missing", headers=headers, json={}).status_code
        == 404
    )
    assert (
        client.post("/api/v1/insights/generate", headers=headers, json={}).status_code
        == 400
    )


def test_chat_session_with_data_context(ai_app, client, headers):
    transactions = [
        {"date": f"2026-09-{d:02d}", "amount": 100 + d, "type": "credit"}
        for d in range(1, 29)
    ]
    ai_app.extensions["services"].payments = FakePayments(transactions)
    session = client.post(
        "/api/v1/chat/sessions", headers=headers, json={"session_name": "Advisor"}
    ).get_json()
    sent = client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        headers=headers,
        json={"message": "forecast my cash flow", "context": {"source": "payments"}},
    )
    assert sent.status_code == 201
    reply = sent.get_json()["assistant_message"]
    assert (
        "30 days" in reply["content"]
        and reply["metadata"]["intent"] == "cash_flow_forecast"
    )
    messages = client.get(
        f"/api/v1/chat/sessions/{session['id']}/messages", headers=headers
    ).get_json()["messages"]
    assert [m["message_type"] for m in messages] == ["user", "assistant"]
    assert (
        client.get(
            f"/api/v1/chat/sessions/{session['id']}",
            headers={**headers, "X-User-ID": "intruder"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/chat/sessions/{session['id']}/messages",
            headers=headers,
            json={"message": ""},
        ).status_code
        == 400
    )
    assert (
        client.delete(
            f"/api/v1/chat/sessions/{session['id']}", headers=headers
        ).status_code
        == 200
    )
    assert client.get("/api/v1/chat/sessions", headers=headers).get_json()["total"] == 0


def test_retrain_is_internal_only_and_updates_model(client, headers):
    from tests.test_credit import _outcomes

    records = _outcomes(1200, 5)
    jwt_only = {"X-User-ID": "u1"}
    assert (
        client.post(
            "/api/v1/models/credit-scorecard/retrain",
            headers=jwt_only,
            json={"records": records},
        ).status_code
        == 401
    )
    ok = client.post(
        "/api/v1/models/credit-scorecard/retrain",
        headers=headers,
        json={"records": records},
    )
    assert ok.status_code == 201 and ok.get_json()["version"] == 2
    card = client.get("/api/v1/models/credit-scorecard", headers=headers).get_json()
    assert card["version"] == 2 and card["warning"] is None
    assert (
        client.post(
            "/api/v1/models/credit-scorecard/retrain",
            headers=headers,
            json={"records": records[:10]},
        ).status_code
        == 422
    )


def test_drift_endpoint_requires_enough_traffic(client, headers):
    assert (
        client.get("/api/v1/models/credit-scorecard/drift", headers=headers).status_code
        == 422
    )
    for i in range(35):
        client.post(
            "/api/v1/predictions/credit-score",
            headers=headers,
            json={
                "business_data": {
                    "annual_revenue": 200000 + i * 1000,
                    "payment_history_score": 70 + i % 10,
                    "credit_utilization": 0.4,
                    "num_credit_inquiries": 2,
                    "debt_to_equity": 1.0,
                    "cash_flow_stability": 0.6,
                    "business_age_months": 30,
                    "employee_count": 6,
                }
            },
        )
    assert (
        client.get("/api/v1/models/credit-scorecard/drift", headers=headers).status_code
        == 200
    )


def test_concurrent_service_startup_is_safe(tmp_path):
    import threading

    from app_factory import build_services
    from service_config import Config

    config = Config(
        secret_key="unit-test-secret-key-with-sufficient-length",
        internal_key="k",
        allow_user_header=False,
        db_path=str(tmp_path / "shared.db"),
        model_dir=str(tmp_path / "models"),
        payment_service_url="http://payments.invalid",
        request_timeout=1.0,
        cors_origins=("*",),
        port=5004,
    )
    barrier = threading.Barrier(4)
    errors = []

    def start():
        try:
            barrier.wait(timeout=5)
            build_services(config)
        except Exception as exc:
            errors.append(repr(exc))

    threads = [threading.Thread(target=start) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    import sqlite3

    rows = (
        sqlite3.connect(config.db_path).execute("SELECT name FROM ai_models").fetchall()
    )
    assert sorted(r[0] for r in rows) == [
        "cash_flow_forecaster",
        "credit_scorecard",
        "transaction_anomaly_detector",
    ]


def test_entry_point_imports_without_pythonpath(tmp_path):
    import os
    import subprocess
    import sys

    src = os.path.join(os.path.dirname(__file__), "..", "ai-service", "src")
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("PYTHONPATH", "INTERNAL_SERVICE_KEY")
    }
    env.update(AI_DB_PATH=str(tmp_path / "e.db"), AI_MODEL_DIR=str(tmp_path / "m"))
    result = subprocess.run(
        [sys.executable, "-c", "import main; print(main.app.name)"],
        cwd=src,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-400:]
