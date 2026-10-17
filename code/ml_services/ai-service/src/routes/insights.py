from ai_models.core.errors import ValidationError
from flask import Blueprint, jsonify, request
from routes.helpers import body, identity, page_args, services

bp = Blueprint("insights", __name__)


@bp.route("/insights", methods=["GET"])
def list_insights():
    user = identity()
    page, per_page = page_args()
    unread = request.args.get("unread", "").lower() in ("1", "true", "yes")
    return jsonify(
        services().repo.list_insights(
            user["user_id"], request.args.get("severity"), unread, page, per_page
        )
    )


@bp.route("/insights/generate", methods=["POST"])
def generate_insights():
    user = identity()
    data = body()
    svc = services()
    financial = data.get("financial_data")
    if financial is None and data.get("source") == "payments":
        financial = {"transactions": svc.payments.transactions(user["user_id"])}
    if not isinstance(financial, dict) or not financial:
        raise ValidationError("financial_data is required")
    result = svc.insights.generate(financial)
    saved = svc.repo.save_insights(user["user_id"], result["insights"])
    return (
        jsonify({"insights": saved, "count": len(saved), "notes": result["notes"]}),
        201,
    )


@bp.route("/insights/<insight_id>", methods=["PUT"])
def update_insight(insight_id: str):
    user = identity()
    return jsonify(services().repo.update_insight(user["user_id"], insight_id, body()))


@bp.route("/insights/<insight_id>/read", methods=["POST"])
def mark_insight_read(insight_id: str):
    user = identity()
    return jsonify(
        services().repo.update_insight(user["user_id"], insight_id, {"is_read": True})
    )
