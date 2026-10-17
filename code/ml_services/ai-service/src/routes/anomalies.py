from ai_models.core.errors import ValidationError
from flask import Blueprint, jsonify
from routes.helpers import Timer, body, identity, services

bp = Blueprint("anomalies", __name__)


@bp.route("/anomalies/score", methods=["POST"])
def score_transaction():
    user = identity()
    data = body()
    svc = services()
    transaction = data.get("transaction")
    if not isinstance(transaction, dict):
        raise ValidationError("transaction is required")
    history = data.get("history")
    if history is None and data.get("use_history"):
        history = svc.payments.transactions(user["user_id"])
    with Timer() as timer:
        result = svc.detector.score_transaction(transaction, history or [])
    if result["risk_level"] != "low":
        svc.repo.record_prediction(
            user["user_id"],
            "transaction_anomaly_detector",
            "anomaly_detection",
            transaction,
            result,
            result["risk_score"],
            {"reasons": result["reasons"]},
            timer.ms,
        )
    return jsonify({**result, "execution_time_ms": timer.ms})


@bp.route("/anomalies/batch", methods=["POST"])
def score_batch():
    identity()
    transactions = body().get("transactions")
    if not isinstance(transactions, list) or not transactions:
        raise ValidationError("transactions must be a non empty list")
    results = services().detector.score_batch(transactions)
    flagged = [i for i, r in enumerate(results) if r["risk_level"] != "low"]
    return jsonify(
        {"results": results, "flagged_indexes": flagged, "reviewed": len(results)}
    )
