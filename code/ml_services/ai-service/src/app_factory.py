import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

from ai_models.advisor.assistant import FinancialAssistant
from ai_models.anomaly.detector import TransactionAnomalyDetector
from ai_models.clients.services import PaymentHistoryClient, ServiceClient
from ai_models.core.errors import MLError
from ai_models.credit.model import CreditModelStore
from ai_models.credit.scorer import CreditScorer
from ai_models.forecasting.cashflow import CashFlowForecaster
from ai_models.insights.engine import InsightEngine
from database.manager import BaseModel, initialize_database
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from migrations import AI_MIGRATIONS
from repository import Repository
from service_config import Config

logger = logging.getLogger("ai-service")


@dataclass
class Services:
    config: Config
    repo: Repository
    scorer: CreditScorer
    forecaster: CashFlowForecaster
    detector: TransactionAnomalyDetector
    insights: InsightEngine
    assistant: FinancialAssistant
    payments: PaymentHistoryClient


def register_models(services: Services) -> None:
    card = services.scorer.model_card()
    services.repo.upsert_model(
        "credit_scorecard",
        "credit_scoring",
        str(card["version"]),
        "Logistic regression scorecard with exact per feature point contributions",
        {"features": card["features"], "scaling": card["scaling"]},
        card["metrics"],
        {
            "source": card["training_data"],
            "samples": card["samples"],
            "warning": card["warning"],
        },
    )
    services.repo.upsert_model(
        "cash_flow_forecaster",
        "forecasting",
        "2.0.0",
        "Per request model selection between seasonal naive, damped trend, ridge and gradient boosting using walk forward validation",
        {"horizon_max_days": 180, "confidence_level": 0.9},
        None,
        {"source": "request supplied history, validated per request"},
    )
    services.repo.upsert_model(
        "transaction_anomaly_detector",
        "anomaly_detection",
        "2.0.0",
        "Per account robust statistical profile with velocity, novelty and structuring signals",
        {"velocity_window_minutes": 60},
        None,
        {"source": "account transaction history supplied with each request"},
    )


def build_services(config: Config, overrides: Optional[dict] = None) -> Services:
    os.makedirs(os.path.dirname(config.db_path), exist_ok=True)
    db_manager, migration_manager = initialize_database(config.db_path)
    BaseModel.set_db_manager(db_manager)
    for version, migration in AI_MIGRATIONS.items():
        migration_manager.apply_migration(
            version, migration["description"], migration["sql"]
        )
    scorer = CreditScorer(CreditModelStore(config.model_dir))
    forecaster = CashFlowForecaster()
    detector = TransactionAnomalyDetector()
    insights = InsightEngine()
    services = Services(
        config=config,
        repo=Repository(db_manager),
        scorer=scorer,
        forecaster=forecaster,
        detector=detector,
        insights=insights,
        assistant=FinancialAssistant(forecaster, scorer, detector, insights),
        payments=PaymentHistoryClient(
            ServiceClient(
                config.payment_service_url, config.request_timeout, config.internal_key
            )
        ),
    )
    for key, value in (overrides or {}).items():
        setattr(services, key, value)
    register_models(services)
    return services


def create_app(
    config: Optional[Config] = None, services: Optional[Services] = None
) -> Flask:
    config = config or Config.from_env()
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app = Flask(__name__, static_folder=static_dir)
    app.config["SECRET_KEY"] = config.secret_key
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
    app.json.sort_keys = False
    CORS(
        app,
        origins=list(config.cors_origins),
        allow_headers=["Content-Type", "Authorization", "X-User-ID", "X-Request-ID"],
    )
    app.extensions["config"] = config
    app.extensions["services"] = services or build_services(config)

    from routes import anomalies, chat, health, insights, models, predictions

    for module in (health, predictions, anomalies, insights, chat, models):
        app.register_blueprint(module.bp, url_prefix="/api/v1")

    @app.errorhandler(MLError)
    def handle_ml_error(error: MLError) -> Any:
        if error.status_code >= 500:
            logger.error("%s %s: %s", request.method, request.path, error.message)
        return jsonify(error.to_dict()), error.status_code

    @app.errorhandler(404)
    def not_found(error: Exception) -> Any:
        return jsonify({"error": "Endpoint not found", "code": "NOT_FOUND"}), 404

    @app.errorhandler(405)
    def method_not_allowed(error: Exception) -> Any:
        return (
            jsonify({"error": "Method not allowed", "code": "METHOD_NOT_ALLOWED"}),
            405,
        )

    @app.errorhandler(Exception)
    def unexpected(error: Exception) -> Any:
        logger.exception("Unhandled error on %s %s", request.method, request.path)
        return (
            jsonify({"error": "Internal server error", "code": "INTERNAL_ERROR"}),
            500,
        )

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve(path: str) -> Any:
        if path.startswith("api/"):
            return jsonify({"error": "Endpoint not found", "code": "NOT_FOUND"}), 404
        if path and os.path.exists(os.path.join(static_dir, path)):
            return send_from_directory(static_dir, path)
        if os.path.exists(os.path.join(static_dir, "index.html")):
            return send_from_directory(static_dir, "index.html")
        return jsonify({"service": "NexaFi AI Service"}), 200

    return app
