from flask import Blueprint, jsonify
from routes.helpers import services

bp = Blueprint("health", __name__)


@bp.route("/health", methods=["GET"])
def health():
    svc = services()
    database = svc.repo.healthy()
    card = svc.scorer.model_card()
    body = {
        "status": "healthy" if database else "degraded",
        "service": "ai-service",
        "database": database,
        "credit_model_version": card["version"],
        "credit_model_training_data": card["training_data"],
    }
    return jsonify(body), 200 if database else 503
