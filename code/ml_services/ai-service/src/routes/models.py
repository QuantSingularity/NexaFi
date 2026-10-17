import json

from ai_models.core.errors import ValidationError
from ai_models.monitoring.drift import credit_input_drift
from auth import require_internal
from flask import Blueprint, jsonify
from routes.helpers import body, identity, services

bp = Blueprint("models", __name__)


@bp.route("/models", methods=["GET"])
def list_models():
    identity()
    svc = services()
    rows = svc.repo._rows("SELECT * FROM ai_models ORDER BY name")
    models = []
    for row in rows:
        row["is_active"] = bool(row.get("is_active"))
        row["is_production"] = bool(row.get("is_production"))
        for key in ("model_config", "training_data_info", "performance_metrics"):
            raw = row.get(key)
            if isinstance(raw, str) and raw:
                row[key] = json.loads(raw)
        models.append(row)
    return jsonify({"models": models})


@bp.route("/models/credit-scorecard", methods=["GET"])
def credit_card():
    identity()
    return jsonify(services().scorer.model_card())


@bp.route("/models/credit-scorecard/drift", methods=["GET"])
def credit_drift():
    identity()
    svc = services()
    inputs = svc.repo.recent_inputs("credit_scoring")
    return jsonify(credit_input_drift(svc.scorer.model, inputs))


@bp.route("/models/credit-scorecard/retrain", methods=["POST"])
def retrain_credit():
    require_internal()
    records = body().get("records")
    if not isinstance(records, list):
        raise ValidationError("records must be a list of labelled outcomes")
    svc = services()
    model = svc.scorer.store.retrain(records)
    from app_factory import register_models

    register_models(svc)
    return (
        jsonify(
            {
                "version": model.version,
                "training_data": model.training_data,
                "metrics": model.metrics,
            }
        ),
        201,
    )
