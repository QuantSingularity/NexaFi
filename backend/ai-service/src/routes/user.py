import random
from datetime import datetime, timedelta
from decimal import Decimal
from functools import wraps
from typing import Any, List

import numpy as np
from flask import Blueprint, jsonify, request
from src.models.user import (
    AIModel,
    AIPrediction,
    ConversationMessage,
    ConversationSession,
    FinancialInsight,
    db,
)

user_bp = Blueprint("ai", __name__)


def require_user_id(f: Any) -> Any:
    """Decorator to extract user_id from request headers"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            return (jsonify({"error": "User ID is required in headers"}), 401)
        request.user_id = user_id
        return f(*args, **kwargs)

    return decorated_function


def generate_cash_flow_forecast(
    user_id: Any, historical_data: Any, days_ahead: Any = 30
) -> Any:
    """Generate cash flow forecast using simulated ML model"""
    base_amount = historical_data.get("average_monthly_cash_flow", 10000)
    seasonal_factor = 1 + 0.1 * np.sin(2 * np.pi * datetime.now().month / 12)
    trend_factor = 1.02
    forecasts: List[Any] = []
    current_date = datetime.now().date()
    for i in range(days_ahead):
        date = current_date + timedelta(days=i)
        random_factor = 1 + random.uniform(-0.15, 0.15)
        daily_amount = base_amount / 30 * seasonal_factor * trend_factor * random_factor
        forecasts.append(
            {
                "date": date.isoformat(),
                "predicted_cash_flow": round(daily_amount, 2),
                "confidence_interval": {
                    "lower": round(daily_amount * 0.85, 2),
                    "upper": round(daily_amount * 1.15, 2),
                },
            }
        )
    return forecasts


def calculate_credit_score(user_id: Any, business_data: Any) -> Any:
    """Calculate credit score using simulated ML model"""
    base_score = 650
    revenue_factor = min(business_data.get("annual_revenue", 0) / 1000000 * 50, 100)
    age_factor = min(business_data.get("business_age_months", 0) / 12 * 10, 50)
    employee_factor = min(business_data.get("employee_count", 0) * 5, 30)
    payment_history_factor = random.uniform(0, 80)
    credit_score = int(
        base_score
        + revenue_factor
        + age_factor
        + employee_factor
        + payment_history_factor
    )
    credit_score = min(max(credit_score, 300), 850)
    if credit_score >= 750:
        risk_category = "excellent"
    elif credit_score >= 700:
        risk_category = "good"
    elif credit_score >= 650:
        risk_category = "fair"
    elif credit_score >= 600:
        risk_category = "poor"
    else:
        risk_category = "very_poor"
    return {
        "credit_score": credit_score,
        "risk_category": risk_category,
        "probability_of_default": round(max(0, (750 - credit_score) / 450), 4),
        "factors": {
            "revenue_impact": round(revenue_factor, 2),
            "business_age_impact": round(age_factor, 2),
            "employee_count_impact": round(employee_factor, 2),
            "payment_history_impact": round(payment_history_factor, 2),
        },
    }


@user_bp.route("/predictions/cash-flow", methods=["POST"])
@require_user_id
def predict_cash_flow() -> Any:
    """Generate cash flow forecast"""
    try:
        data = request.get_json()
        historical_data = data.get("historical_data", {})
        days_ahead = data.get("days_ahead", 30)
        forecast = generate_cash_flow_forecast(
            request.user_id, historical_data, days_ahead
        )
        model = AIModel.query.filter_by(
            name="cash_flow_forecast_v1", is_active=True
        ).first()
        if not model:
            model = AIModel(
                name="cash_flow_forecast_v1",
                model_type="cash_flow_forecast",
                version="1.0",
                description="LSTM-based cash flow forecasting model",
                model_config={"architecture": "LSTM", "layers": 3, "units": 50},
                performance_metrics={"mae": 0.12, "rmse": 0.18, "accuracy": 0.87},
                is_active=True,
                is_production=True,
            )
            db.session.add(model)
            db.session.flush()
        prediction = AIPrediction(
            user_id=request.user_id,
            model_id=model.id,
            prediction_type="cash_flow_forecast",
            input_data=historical_data,
            prediction_result={"forecast": forecast, "days_ahead": days_ahead},
            confidence_score=Decimal("0.87"),
            explanation={
                "key_factors": [
                    "historical_trends",
                    "seasonal_patterns",
                    "business_growth",
                ],
                "methodology": "LSTM neural network with 30-day lookback window",
            },
            execution_time_ms=245,
        )
        db.session.add(prediction)
        db.session.commit()
        return (
            jsonify(
                {
                    "prediction_id": prediction.id,
                    "forecast": forecast,
                    "summary": {
                        "total_predicted_cash_flow": sum(
                            (f["predicted_cash_flow"] for f in forecast)
                        ),
                        "average_daily_cash_flow": sum(
                            (f["predicted_cash_flow"] for f in forecast)
                        )
                        / len(forecast),
                        "confidence_score": float(prediction.confidence_score),
                    },
                    "model_info": {
                        "model_name": model.name,
                        "model_version": model.version,
                        "accuracy": model.performance_metrics.get("accuracy"),
                    },
                }
            ),
            200,
        )
    except Exception as e:
        db.session.rollback()
        return (
            jsonify(
                {"error": "Failed to generate cash flow forecast", "details": str(e)}
            ),
            500,
        )


@user_bp.route("/predictions/credit-score", methods=["POST"])
@require_user_id
def predict_credit_score() -> Any:
    """Calculate credit score"""
    try:
        data = request.get_json()
        business_data = data.get("business_data", {})
        credit_result = calculate_credit_score(request.user_id, business_data)
        model = AIModel.query.filter_by(
            name="credit_scoring_v1", is_active=True
        ).first()
        if not model:
            model = AIModel(
                name="credit_scoring_v1",
                model_type="credit_scoring",
                version="1.0",
                description="XGBoost-based credit scoring model",
                model_config={"algorithm": "XGBoost", "features": 47, "trees": 100},
                performance_metrics={"auc": 0.89, "precision": 0.84, "recall": 0.81},
                is_active=True,
                is_production=True,
            )
            db.session.add(model)
            db.session.flush()
        prediction = AIPrediction(
            user_id=request.user_id,
            model_id=model.id,
            prediction_type="credit_scoring",
            input_data=business_data,
            prediction_result=credit_result,
            confidence_score=Decimal("0.89"),
            explanation={
                "key_factors": list(credit_result["factors"].keys()),
                "methodology": "Gradient boosting with alternative data sources",
            },
            execution_time_ms=156,
        )
        db.session.add(prediction)
        db.session.commit()
        return (
            jsonify(
                {
                    "prediction_id": prediction.id,
                    "credit_score": credit_result["credit_score"],
                    "risk_category": credit_result["risk_category"],
                    "probability_of_default": credit_result["probability_of_default"],
                    "factors": credit_result["factors"],
                    "recommendations": [
                        "Maintain consistent payment history to improve score",
                        "Consider increasing business revenue to boost creditworthiness",
                        "Build longer business operating history",
                    ],
                    "model_info": {
                        "model_name": model.name,
                        "model_version": model.version,
                        "auc_score": model.performance_metrics.get("auc"),
                    },
                }
            ),
            200,
        )
    except Exception as e:
        db.session.rollback()
        return (
            jsonify({"error": "Failed to calculate credit score", "details": str(e)}),
            500,
        )


@user_bp.route("/insights", methods=["GET"])
@require_user_id
def get_financial_insights() -> Any:
    """Get financial insights for user"""
    try:
        category = request.args.get("category")
        severity = request.args.get("severity")
        is_read = request.args.get("is_read")
        query = FinancialInsight.query.filter_by(
            user_id=request.user_id, is_dismissed=False
        )
        if category:
            query = query.filter_by(category=category)
        if severity:
            query = query.filter_by(severity=severity)
        if is_read is not None:
            query = query.filter_by(is_read=is_read.lower() == "true")
        insights = query.order_by(FinancialInsight.created_at.desc()).all()
        return (
            jsonify(
                {
                    "insights": [insight.to_dict() for insight in insights],
                    "total": len(insights),
                    "summary": {
                        "unread_count": len([i for i in insights if not i.is_read]),
                        "critical_count": len(
                            [i for i in insights if i.severity == "critical"]
                        ),
                        "warning_count": len(
                            [i for i in insights if i.severity == "warning"]
                        ),
                    },
                }
            ),
            200,
        )
    except Exception as e:
        return (jsonify({"error": "Failed to get insights", "details": str(e)}), 500)


@user_bp.route("/insights/generate", methods=["POST"])
@require_user_id
def generate_insights() -> Any:
    """Generate new financial insights"""
    try:
        data = request.get_json()
        financial_data = data.get("financial_data", {})
        insights_to_create: List[Any] = []
        if financial_data.get("cash_flow_trend") == "declining":
            insights_to_create.append(
                {
                    "insight_type": "cash_flow_alert",
                    "title": "Declining Cash Flow Detected",
                    "description": "Your cash flow has decreased by 15% over the last 30 days. This trend may impact your ability to meet upcoming obligations.",
                    "severity": "warning",
                    "category": "cash_flow",
                    "data_points": {
                        "current_cash_flow": financial_data.get("current_cash_flow", 0),
                        "previous_cash_flow": financial_data.get(
                            "previous_cash_flow", 0
                        ),
                        "decline_percentage": 15,
                    },
                    "recommendations": [
                        "Review accounts receivable for overdue payments",
                        "Consider accelerating collection efforts",
                        "Evaluate expense reduction opportunities",
                    ],
                }
            )
        if financial_data.get("unusual_expenses"):
            insights_to_create.append(
                {
                    "insight_type": "expense_anomaly",
                    "title": "Unusual Expense Pattern Detected",
                    "description": "Your marketing expenses are 40% higher than usual this month. Review these expenses to ensure they align with your budget.",
                    "severity": "info",
                    "category": "expenses",
                    "data_points": {
                        "category": "marketing",
                        "current_amount": financial_data.get("marketing_expenses", 0),
                        "average_amount": financial_data.get(
                            "avg_marketing_expenses", 0
                        ),
                        "variance_percentage": 40,
                    },
                    "recommendations": [
                        "Review marketing campaign ROI",
                        "Verify all marketing expenses are legitimate",
                        "Consider adjusting budget allocation",
                    ],
                }
            )
        insights_to_create.append(
            {
                "insight_type": "revenue_opportunity",
                "title": "Revenue Growth Opportunity Identified",
                "description": "Based on your customer data, there's potential to increase revenue by 12% through targeted upselling to existing customers.",
                "severity": "info",
                "category": "opportunity",
                "data_points": {
                    "potential_increase": 12,
                    "target_customers": financial_data.get("target_customers", 25),
                    "estimated_additional_revenue": financial_data.get(
                        "potential_revenue", 5000
                    ),
                },
                "recommendations": [
                    "Identify high-value customers for upselling",
                    "Develop targeted marketing campaigns",
                    "Track conversion rates and adjust strategy",
                ],
            }
        )
        created_insights: List[Any] = []
        for insight_data in insights_to_create:
            insight = FinancialInsight(
                user_id=request.user_id,
                insight_type=insight_data["insight_type"],
                title=insight_data["title"],
                description=insight_data["description"],
                severity=insight_data["severity"],
                category=insight_data["category"],
                data_points=insight_data["data_points"],
                recommendations=insight_data["recommendations"],
                expires_at=datetime.utcnow() + timedelta(days=30),
            )
            db.session.add(insight)
            created_insights.append(insight)
        db.session.commit()
        return (
            jsonify(
                {
                    "message": f"Generated {len(created_insights)} new insights",
                    "insights": [insight.to_dict() for insight in created_insights],
                }
            ),
            201,
        )
    except Exception as e:
        db.session.rollback()
        return (
            jsonify({"error": "Failed to generate insights", "details": str(e)}),
            500,
        )


@user_bp.route("/insights/<insight_id>/read", methods=["POST"])
@require_user_id
def mark_insight_read(insight_id: Any) -> Any:
    """Mark insight as read"""
    try:
        insight = FinancialInsight.query.filter_by(
            id=insight_id, user_id=request.user_id
        ).first()
        if not insight:
            return (jsonify({"error": "Insight not found"}), 404)
        insight.is_read = True
        insight.updated_at = datetime.utcnow()
        db.session.commit()
        return (jsonify({"message": "Insight marked as read"}), 200)
    except Exception as e:
        db.session.rollback()
        return (
            jsonify({"error": "Failed to mark insight as read", "details": str(e)}),
            500,
        )


@user_bp.route("/chat/sessions", methods=["GET"])
@require_user_id
def get_chat_sessions() -> Any:
    """Get chat sessions for user"""
    try:
        sessions = (
            ConversationSession.query.filter_by(user_id=request.user_id)
            .order_by(ConversationSession.last_activity_at.desc())
            .all()
        )
        return (
            jsonify(
                {
                    "sessions": [session.to_dict() for session in sessions],
                    "total": len(sessions),
                }
            ),
            200,
        )
    except Exception as e:
        return (
            jsonify({"error": "Failed to get chat sessions", "details": str(e)}),
            500,
        )


@user_bp.route("/chat/sessions", methods=["POST"])
@require_user_id
def create_chat_session() -> Any:
    """Create new chat session"""
    try:
        data = request.get_json()
        session = ConversationSession(
            user_id=request.user_id,
            session_name=data.get(
                "session_name",
                f"Chat Session {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            ),
            context=data.get("context", {}),
        )
        db.session.add(session)
        db.session.commit()
        return (
            jsonify(
                {
                    "message": "Chat session created successfully",
                    "session": session.to_dict(),
                }
            ),
            201,
        )
    except Exception as e:
        db.session.rollback()
        return (
            jsonify({"error": "Failed to create chat session", "details": str(e)}),
            500,
        )


@user_bp.route("/chat/sessions/<session_id>/messages", methods=["GET"])
@require_user_id
def get_chat_messages(session_id: Any) -> Any:
    """Get messages for chat session"""
    try:
        session = ConversationSession.query.filter_by(
            id=session_id, user_id=request.user_id
        ).first()
        if not session:
            return (jsonify({"error": "Chat session not found"}), 404)
        messages = (
            ConversationMessage.query.filter_by(session_id=session_id)
            .order_by(ConversationMessage.created_at)
            .all()
        )
        return (
            jsonify(
                {
                    "session": session.to_dict(),
                    "messages": [message.to_dict() for message in messages],
                    "total_messages": len(messages),
                }
            ),
            200,
        )
    except Exception as e:
        return (
            jsonify({"error": "Failed to get chat messages", "details": str(e)}),
            500,
        )


@user_bp.route("/chat/sessions/<session_id>/messages", methods=["POST"])
@require_user_id
def send_chat_message(session_id: Any) -> Any:
    """Send message to chat session"""
    try:
        session = ConversationSession.query.filter_by(
            id=session_id, user_id=request.user_id
        ).first()
        if not session:
            return (jsonify({"error": "Chat session not found"}), 404)
        data = request.get_json()
        user_message_content = data.get("message", "").strip()
        if not user_message_content:
            return (jsonify({"error": "Message content is required"}), 400)
        user_message = ConversationMessage(
            session_id=session_id,
            message_type="user",
            content=user_message_content,
            metadata=data.get("metadata", {}),
        )
        db.session.add(user_message)
        ai_response = generate_ai_response(user_message_content, session.context)
        ai_message = ConversationMessage(
            session_id=session_id,
            message_type="assistant",
            content=ai_response["content"],
            metadata=ai_response["metadata"],
            tokens_used=ai_response["tokens_used"],
            processing_time_ms=ai_response["processing_time_ms"],
        )
        db.session.add(ai_message)
        session.last_activity_at = datetime.utcnow()
        session.updated_at = datetime.utcnow()
        db.session.commit()
        return (
            jsonify(
                {
                    "user_message": user_message.to_dict(),
                    "ai_response": ai_message.to_dict(),
                }
            ),
            201,
        )
    except Exception as e:
        db.session.rollback()
        return (jsonify({"error": "Failed to send message", "details": str(e)}), 500)


def generate_ai_response(user_message: Any, context: Any) -> Any:
    """Generate AI response (simplified simulation)"""
    processing_time = random.randint(500, 2000)
    tokens_used = random.randint(50, 200)
    user_message_lower = user_message.lower()
    if any((word in user_message_lower for word in ["cash flow", "cash", "flow"])):
        response = "I can help you analyze your cash flow. Based on your recent transactions, I notice some patterns that might be worth discussing. Would you like me to generate a detailed cash flow forecast for the next 30 days?"
    elif any((word in user_message_lower for word in ["credit", "score", "loan"])):
        response = "I can assist with credit-related questions. Your current credit profile shows several positive factors. Would you like me to run a credit assessment or help you understand what factors most impact your business credit score?"
    elif any(
        (word in user_message_lower for word in ["expense", "expenses", "spending"])
    ):
        response = "I can analyze your expense patterns. I've noticed some interesting trends in your spending that could help optimize your budget. Would you like me to identify potential cost-saving opportunities?"
    elif any((word in user_message_lower for word in ["revenue", "income", "sales"])):
        response = "Let me help you with revenue analysis. Your revenue trends show some promising patterns. I can provide insights on growth opportunities and revenue optimization strategies. What specific aspect would you like to explore?"
    else:
        response = "I'm here to help with your financial questions and provide insights about your business. I can assist with cash flow analysis, expense optimization, revenue forecasting, credit assessment, and general financial planning. What would you like to know more about?"
    return {
        "content": response,
        "metadata": {
            "response_type": "financial_advisory",
            "confidence": random.uniform(0.8, 0.95),
            "suggested_actions": [
                "view_dashboard",
                "generate_report",
                "schedule_review",
            ],
        },
        "tokens_used": tokens_used,
        "processing_time_ms": processing_time,
    }


@user_bp.route("/models", methods=["GET"])
def get_models() -> Any:
    """Get available AI models"""
    try:
        models = AIModel.query.filter_by(is_active=True).all()
        return (
            jsonify(
                {"models": [model.to_dict() for model in models], "total": len(models)}
            ),
            200,
        )
    except Exception as e:
        return (jsonify({"error": "Failed to get models", "details": str(e)}), 500)


@user_bp.route("/predictions", methods=["GET"])
@require_user_id
def get_predictions() -> Any:
    """Get user's prediction history"""
    try:
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        prediction_type = request.args.get("type")
        query = AIPrediction.query.filter_by(user_id=request.user_id)
        if prediction_type:
            query = query.filter_by(prediction_type=prediction_type)
        predictions = query.order_by(AIPrediction.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        return (
            jsonify(
                {
                    "predictions": [
                        prediction.to_dict() for prediction in predictions.items
                    ],
                    "pagination": {
                        "page": page,
                        "per_page": per_page,
                        "total": predictions.total,
                        "pages": predictions.pages,
                        "has_next": predictions.has_next,
                        "has_prev": predictions.has_prev,
                    },
                }
            ),
            200,
        )
    except Exception as e:
        return (jsonify({"error": "Failed to get predictions", "details": str(e)}), 500)


@user_bp.route("/health", methods=["GET"])
def health_check() -> Any:
    """Health check endpoint"""
    return (
        jsonify(
            {
                "status": "healthy",
                "service": "ai-service",
                "timestamp": datetime.utcnow().isoformat(),
                "models_available": AIModel.query.filter_by(is_active=True).count(),
            }
        ),
        200,
    )
