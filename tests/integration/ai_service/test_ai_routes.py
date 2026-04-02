from datetime import datetime, timedelta
from typing import Any

import pytest

from backend.ai_service.src.main import app
from backend.ai_service.src.models.user import (
    AIModel,
    AIPrediction,
    ConversationMessage,
    ConversationSession,
    FinancialInsight,
    db,
)


@pytest.fixture(scope="module")
def client() -> Any:
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        with app.app_context():
            db.drop_all()


@pytest.fixture(autouse=True)
def run_around_tests(client: Any) -> Any:
    with app.app_context():
        AIModel.query.delete()
        AIPrediction.query.delete()
        FinancialInsight.query.delete()
        ConversationSession.query.delete()
        ConversationMessage.query.delete()
        db.session.commit()
    yield


def create_test_model(
    name: Any, model_type: Any, version: Any, description: Any, performance_metrics: Any
) -> Any:
    model = AIModel(
        name=name,
        model_type=model_type,
        version=version,
        description=description,
        model_config={},
        performance_metrics=performance_metrics,
        is_active=True,
        is_production=True,
    )
    db.session.add(model)
    db.session.commit()
    return model


class TestAIPredictionRoutes:

    def test_predict_cash_flow_success(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_123"}
        data = {
            "historical_data": {"average_monthly_cash_flow": 10000},
            "days_ahead": 5,
        }
        response = client.post(
            "/api/v1/predictions/cash-flow", headers=headers, json=data
        )
        assert response.status_code == 200
        json_data = response.get_json()
        assert "prediction_id" in json_data
        assert "forecast" in json_data
        assert len(json_data["forecast"]) == 5
        assert "summary" in json_data
        assert "model_info" in json_data
        with app.app_context():
            prediction = AIPrediction.query.filter_by(user_id="test_user_123").first()
            assert prediction is not None
            assert prediction.prediction_type == "cash_flow_forecast"
            assert prediction.confidence_score == 0.87

    def test_predict_cash_flow_missing_user_id(self, client: Any) -> Any:
        data = {
            "historical_data": {"average_monthly_cash_flow": 10000},
            "days_ahead": 5,
        }
        response = client.post("/api/v1/predictions/cash-flow", json=data)
        assert response.status_code == 401
        assert response.get_json()["error"] == "User ID is required in headers"

    def test_predict_credit_score_success(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_123"}
        data = {
            "business_data": {
                "annual_revenue": 1500000,
                "business_age_months": 60,
                "employee_count": 10,
            }
        }
        response = client.post(
            "/api/v1/predictions/credit-score", headers=headers, json=data
        )
        assert response.status_code == 200
        json_data = response.get_json()
        assert "prediction_id" in json_data
        assert "credit_score" in json_data
        assert "risk_category" in json_data
        assert "probability_of_default" in json_data
        assert "factors" in json_data
        assert "recommendations" in json_data
        assert "model_info" in json_data
        with app.app_context():
            prediction = AIPrediction.query.filter_by(user_id="test_user_123").first()
            assert prediction is not None
            assert prediction.prediction_type == "credit_scoring"
            assert prediction.confidence_score == 0.89

    def test_predict_credit_score_missing_user_id(self, client: Any) -> Any:
        data = {
            "business_data": {
                "annual_revenue": 1500000,
                "business_age_months": 60,
                "employee_count": 10,
            }
        }
        response = client.post("/api/v1/predictions/credit-score", json=data)
        assert response.status_code == 401
        assert response.get_json()["error"] == "User ID is required in headers"


class TestFinancialInsightsRoutes:

    def test_get_financial_insights_no_insights(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_456"}
        response = client.get("/api/v1/insights", headers=headers)
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["insights"] == []
        assert json_data["total"] == 0
        assert json_data["summary"]["unread_count"] == 0

    def test_generate_insights_success(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_456"}
        data = {
            "financial_data": {
                "cash_flow_trend": "declining",
                "current_cash_flow": 5000,
                "previous_cash_flow": 6000,
                "unusual_expenses": True,
                "marketing_expenses": 1000,
                "avg_marketing_expenses": 700,
                "target_customers": 50,
                "potential_revenue": 10000,
            }
        }
        response = client.post("/api/v1/insights/generate", headers=headers, json=data)
        assert response.status_code == 201
        json_data = response.get_json()
        assert "message" in json_data
        assert len(json_data["insights"]) == 3
        with app.app_context():
            insights = FinancialInsight.query.filter_by(user_id="test_user_456").all()
            assert len(insights) == 3
            assert any((i.insight_type == "cash_flow_alert" for i in insights))
            assert any((i.insight_type == "expense_anomaly" for i in insights))
            assert any((i.insight_type == "revenue_opportunity" for i in insights))

    def test_mark_insight_read_success(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_789"}
        with app.app_context():
            insight = FinancialInsight(
                user_id="test_user_789",
                insight_type="test_type",
                title="Test Insight",
                description="This is a test insight",
                severity="info",
                category="general",
                data_points={},
                recommendations=[],
                expires_at=datetime.utcnow() + timedelta(days=1),
            )
            db.session.add(insight)
            db.session.commit()
            insight_id = insight.id
        response = client.post(f"/api/v1/insights/{insight_id}/read", headers=headers)
        assert response.status_code == 200
        assert response.get_json()["message"] == "Insight marked as read"
        with app.app_context():
            updated_insight = FinancialInsight.query.get(insight_id)
            assert updated_insight.is_read == True

    def test_mark_insight_read_not_found(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_789"}
        response = client.post("/api/v1/insights/99999/read", headers=headers)
        assert response.status_code == 404
        assert response.get_json()["error"] == "Insight not found"


class TestConversationalAIRoutes:

    def test_get_chat_sessions_no_sessions(self, client: Any) -> Any:
        headers = {"X-User-ID": "chat_user_1"}
        response = client.get("/api/v1/chat/sessions", headers=headers)
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["sessions"] == []
        assert json_data["total"] == 0

    def test_create_chat_session_success(self, client: Any) -> Any:
        headers = {"X-User-ID": "chat_user_1"}
        response = client.post("/api/v1/chat/sessions", headers=headers)
        assert response.status_code == 201
        json_data = response.get_json()
        assert "session_id" in json_data
        assert "start_time" in json_data
        with app.app_context():
            session = ConversationSession.query.filter_by(user_id="chat_user_1").first()
            assert session is not None

    def test_send_chat_message_success(self, client: Any) -> Any:
        headers = {"X-User-ID": "chat_user_2"}
        with app.app_context():
            session = ConversationSession(
                user_id="chat_user_2",
                start_time=datetime.utcnow(),
                last_activity_at=datetime.utcnow(),
            )
            db.session.add(session)
            db.session.commit()
            session_id = session.id
        data = {"message": "Hello AI!"}
        response = client.post(
            f"/api/v1/chat/sessions/{session_id}/messages", headers=headers, json=data
        )
        assert response.status_code == 201
        json_data = response.get_json()
        assert "message_id" in json_data
        assert "response" in json_data
        with app.app_context():
            message = ConversationMessage.query.filter_by(session_id=session_id).first()
            assert message is not None
            assert message.sender == "user"
            assert message.content == "Hello AI!"

    def test_send_chat_message_session_not_found(self, client: Any) -> Any:
        headers = {"X-User-ID": "chat_user_3"}
        data = {"message": "Hello AI!"}
        response = client.post(
            "/api/v1/chat/sessions/99999/messages", headers=headers, json=data
        )
        assert response.status_code == 404
        assert response.get_json()["error"] == "Chat session not found"

    def test_get_chat_messages_success(self, client: Any) -> Any:
        headers = {"X-User-ID": "chat_user_4"}
        with app.app_context():
            session = ConversationSession(
                user_id="chat_user_4",
                start_time=datetime.utcnow(),
                last_activity_at=datetime.utcnow(),
            )
            db.session.add(session)
            db.session.commit()
            session_id = session.id
            msg1 = ConversationMessage(
                session_id=session_id, sender="user", content="Hi"
            )
            msg2 = ConversationMessage(
                session_id=session_id, sender="ai", content="Hello"
            )
            db.session.add_all([msg1, msg2])
            db.session.commit()
        response = client.get(
            f"/api/v1/chat/sessions/{session_id}/messages", headers=headers
        )
        assert response.status_code == 200
        json_data = response.get_json()
        assert len(json_data["messages"]) == 2
        assert json_data["messages"][0]["content"] == "Hi"
        assert json_data["messages"][1]["content"] == "Hello"

    def test_get_chat_messages_session_not_found(self, client: Any) -> Any:
        headers = {"X-User-ID": "chat_user_5"}
        response = client.get("/api/v1/chat/sessions/99999/messages", headers=headers)
        assert response.status_code == 404
        assert response.get_json()["error"] == "Chat session not found"

    def test_delete_chat_session_success(self, client: Any) -> Any:
        headers = {"X-User-ID": "chat_user_6"}
        with app.app_context():
            session = ConversationSession(
                user_id="chat_user_6",
                start_time=datetime.utcnow(),
                last_activity_at=datetime.utcnow(),
            )
            db.session.add(session)
            db.session.commit()
            session_id = session.id
        response = client.delete(f"/api/v1/chat/sessions/{session_id}")
        assert response.status_code == 200
        assert response.get_json()["message"] == "Chat session deleted"
        with app.app_context():
            session = ConversationSession.query.get(session_id)
            assert session is None

    def test_delete_chat_session_not_found(self, client: Any) -> Any:
        response = client.delete("/api/v1/chat/sessions/99999")
        assert response.status_code == 404
        assert response.get_json()["error"] == "Chat session not found"
