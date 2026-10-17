from typing import Any, Dict

from ai_models.core.errors import ValidationError
from flask import Blueprint, jsonify, request
from routes.helpers import Timer, body, identity, page_args, services

bp = Blueprint("predictions", __name__)


@bp.route("/predictions/cash-flow", methods=["POST"])
def predict_cash_flow():
    user = identity()
    data = body()
    svc = services()
    historical: Dict[str, Any] = data.get("historical_data") or {}
    if data.get("source") == "payments":
        historical = {"transactions": svc.payments.transactions(user["user_id"])}
    with Timer() as timer:
        result = svc.forecaster.forecast(historical, data.get("days_ahead", 30))
    prediction_id = svc.repo.record_prediction(
        user["user_id"],
        "cash_flow_forecaster",
        "cash_flow",
        {
            "days_ahead": data.get("days_ahead", 30),
            "source": result["summary"]["data_source"],
            "history_days": result["summary"]["history_days"],
        },
        {"summary": result["summary"], "forecast": result["forecast"]},
        None,
        {"metrics": result["metrics"], "warnings": result["warnings"]},
        timer.ms,
    )
    return (
        jsonify(
            {"prediction_id": prediction_id, **result, "execution_time_ms": timer.ms}
        ),
        200,
    )


@bp.route("/predictions/credit-score", methods=["POST"])
def predict_credit_score():
    user = identity()
    data = body()
    svc = services()
    business = data.get("business_data")
    if not isinstance(business, dict) or not business:
        raise ValidationError("business_data is required")
    with Timer() as timer:
        result = svc.scorer.score(business)
    prediction_id = svc.repo.record_prediction(
        user["user_id"],
        "credit_scorecard",
        "credit_scoring",
        business,
        {
            k: result[k]
            for k in (
                "credit_score",
                "risk_category",
                "probability_of_default",
                "decision",
            )
        },
        result["data_completeness"],
        {"factors": result["factors"], "recommendations": result["recommendations"]},
        timer.ms,
    )
    return (
        jsonify(
            {"prediction_id": prediction_id, **result, "execution_time_ms": timer.ms}
        ),
        200,
    )


@bp.route("/predictions", methods=["GET"])
def list_predictions():
    user = identity()
    page, per_page = page_args()
    return jsonify(
        services().repo.list_predictions(
            user["user_id"], request.args.get("type"), page, per_page
        )
    )


@bp.route("/predictions/<prediction_id>", methods=["GET"])
def get_prediction(prediction_id: str):
    user = identity()
    return jsonify(services().repo.get_prediction(user["user_id"], prediction_id))
