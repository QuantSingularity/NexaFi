"""
Enterprise Model Serving Infrastructure for NexaFi
High-performance, scalable model serving with comprehensive monitoring
"""

import json
import logging
import os
import pickle
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import boto3
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
import psutil
import redis
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from mlflow.tracking import MlflowClient
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from sklearn.base import BaseEstimator

REQUEST_COUNT = Counter(
    "model_requests_total",
    "Total model requests",
    ["model_name", "version", "endpoint"],
)
REQUEST_DURATION = Histogram(
    "model_request_duration_seconds", "Request duration", ["model_name", "version"]
)
PREDICTION_COUNT = Counter(
    "model_predictions_total", "Total predictions made", ["model_name", "version"]
)
ERROR_COUNT = Counter(
    "model_errors_total", "Total errors", ["model_name", "version", "error_type"]
)
MODEL_LOAD_TIME = Gauge(
    "model_load_time_seconds", "Time to load model", ["model_name", "version"]
)
MEMORY_USAGE = Gauge(
    "model_memory_usage_bytes", "Memory usage", ["model_name", "version"]
)
CPU_USAGE = Gauge(
    "model_cpu_usage_percent", "CPU usage percentage", ["model_name", "version"]
)


@dataclass
class PredictionRequest:
    """Structured prediction request"""

    request_id: str
    model_name: str
    model_version: str
    features: Dict[str, Any]
    metadata: Dict[str, Any]
    timestamp: datetime


@dataclass
class PredictionResponse:
    """Structured prediction response"""

    request_id: str
    model_name: str
    model_version: str
    prediction: Any
    confidence: Optional[float]
    explanation: Optional[Dict[str, Any]]
    processing_time_ms: float
    timestamp: datetime
    status: str
    error_message: Optional[str] = None


class ModelCache:
    """Intelligent model caching with LRU eviction"""

    def __init__(self, max_models: int = 5, ttl_hours: int = 24) -> None:
        self.max_models = max_models
        self.ttl_hours = ttl_hours
        self.cache = {}
        self.access_times = {}
        self.load_times = {}
        self.lock = threading.RLock()
        self.logger = logging.getLogger(__name__)

    def get_model(self, model_name: str, version: str) -> Optional[BaseEstimator]:
        """Get model from cache"""
        with self.lock:
            key = f"{model_name}:{version}"
            if key in self.cache:
                load_time = self.load_times.get(key)
                if load_time and datetime.now() - load_time < timedelta(
                    hours=self.ttl_hours
                ):
                    self.access_times[key] = datetime.now()
                    self.logger.debug(f"Model {key} served from cache")
                    return self.cache[key]
                else:
                    self._evict_model(key)
            return None

    def put_model(self, model_name: str, version: str, model: BaseEstimator) -> Any:
        """Put model in cache with LRU eviction"""
        with self.lock:
            key = f"{model_name}:{version}"
            if len(self.cache) >= self.max_models and key not in self.cache:
                self._evict_lru()
            self.cache[key] = model
            self.access_times[key] = datetime.now()
            self.load_times[key] = datetime.now()
            self.logger.info(f"Model {key} cached successfully")

    def _evict_lru(self) -> Any:
        """Evict least recently used model"""
        if not self.access_times:
            return
        lru_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
        self._evict_model(lru_key)

    def _evict_model(self, key: str) -> Any:
        """Evict specific model"""
        if key in self.cache:
            del self.cache[key]
            del self.access_times[key]
            del self.load_times[key]
            self.logger.info(f"Model {key} evicted from cache")

    def clear_cache(self) -> Any:
        """Clear all cached models"""
        with self.lock:
            self.cache.clear()
            self.access_times.clear()
            self.load_times.clear()
            self.logger.info("Model cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            return {
                "cached_models": list(self.cache.keys()),
                "cache_size": len(self.cache),
                "max_size": self.max_models,
                "access_times": {
                    k: v.isoformat() for k, v in self.access_times.items()
                },
                "load_times": {k: v.isoformat() for k, v in self.load_times.items()},
            }


class ModelLoader:
    """Model loading with multiple backends support"""

    def __init__(self, mlflow_uri: str, s3_bucket: str = None) -> None:
        self.mlflow_uri = mlflow_uri
        self.s3_bucket = s3_bucket
        self.mlflow_client = MlflowClient(mlflow_uri)
        self.s3_client = boto3.client("s3") if s3_bucket else None
        self.logger = logging.getLogger(__name__)

    def load_model(self, model_name: str, version: str = "latest") -> BaseEstimator:
        """Load model from registry"""
        start_time = time.time()
        try:
            model = self._load_from_mlflow(model_name, version)
            if model is None and self.s3_client:
                model = self._load_from_s3(model_name, version)
            if model is None:
                raise ValueError(f"Model {model_name}:{version} not found")
            load_time = time.time() - start_time
            MODEL_LOAD_TIME.labels(model_name=model_name, version=version).set(
                load_time
            )
            self.logger.info(f"Model {model_name}:{version} loaded in {load_time:.2f}s")
            return model
        except Exception as e:
            self.logger.error(f"Failed to load model {model_name}:{version}: {str(e)}")
            raise

    def _load_from_mlflow(
        self, model_name: str, version: str
    ) -> Optional[BaseEstimator]:
        """Load model from MLflow"""
        try:
            if version == "latest":
                model_version = self.mlflow_client.get_latest_versions(
                    model_name, stages=["Production"]
                )[0]
                version = model_version.version
            model_uri = f"models:/{model_name}/{version}"
            model = mlflow.sklearn.load_model(model_uri)
            self.logger.debug(f"Model {model_name}:{version} loaded from MLflow")
            return model
        except Exception as e:
            self.logger.warning(f"Failed to load from MLflow: {str(e)}")
            return None

    def _load_from_s3(self, model_name: str, version: str) -> Optional[BaseEstimator]:
        """Load model from S3"""
        try:
            model_key = f"models/{model_name}/v{version}/model.pkl"
            response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=model_key)
            model_bytes = response["Body"].read()
            model = pickle.loads(model_bytes)
            self.logger.debug(f"Model {model_name}:{version} loaded from S3")
            return model
        except Exception as e:
            self.logger.warning(f"Failed to load from S3: {str(e)}")
            return None


class PredictionLogger:
    """Comprehensive prediction logging for audit and monitoring"""

    def __init__(self, redis_client: redis.Redis = None) -> None:
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
        self.log_buffer = []
        self.buffer_size = 100
        self.lock = threading.Lock()

    def log_prediction(
        self, request: PredictionRequest, response: PredictionResponse
    ) -> Any:
        """Log prediction request and response"""
        log_entry = {
            "request_id": request.request_id,
            "timestamp": response.timestamp.isoformat(),
            "model_name": request.model_name,
            "model_version": request.model_version,
            "features": request.features,
            "prediction": response.prediction,
            "confidence": response.confidence,
            "processing_time_ms": response.processing_time_ms,
            "status": response.status,
            "error_message": response.error_message,
            "metadata": request.metadata,
        }
        self.logger.info(f"PREDICTION_LOG: {json.dumps(log_entry)}")
        with self.lock:
            self.log_buffer.append(log_entry)
            if len(self.log_buffer) >= self.buffer_size:
                self._flush_buffer()
        if self.redis_client:
            try:
                key = f"predictions:{request.model_name}:{datetime.now().strftime('%Y%m%d')}"
                self.redis_client.lpush(key, json.dumps(log_entry))
                self.redis_client.expire(key, 86400 * 7)
            except Exception as e:
                self.logger.warning(f"Failed to log to Redis: {str(e)}")

    def _flush_buffer(self) -> Any:
        """Flush log buffer to persistent storage"""
        if not self.log_buffer:
            return
        try:
            self.logger.info(f"Flushing {len(self.log_buffer)} prediction logs")
            self.log_buffer.clear()
        except Exception as e:
            self.logger.error(f"Failed to flush log buffer: {str(e)}")

    def get_prediction_stats(self, model_name: str, hours: int = 24) -> Dict[str, Any]:
        """Get prediction statistics for monitoring"""
        if not self.redis_client:
            return {}
        try:
            key = f"predictions:{model_name}:{datetime.now().strftime('%Y%m%d')}"
            predictions = self.redis_client.lrange(key, 0, -1)
            if not predictions:
                return {"total_predictions": 0}
            parsed_predictions = [json.loads(p) for p in predictions]
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_predictions = [
                p
                for p in parsed_predictions
                if datetime.fromisoformat(p["timestamp"]) > cutoff_time
            ]
            if not recent_predictions:
                return {"total_predictions": 0}
            processing_times = [p["processing_time_ms"] for p in recent_predictions]
            confidences = [
                p["confidence"]
                for p in recent_predictions
                if p["confidence"] is not None
            ]
            stats = {
                "total_predictions": len(recent_predictions),
                "avg_processing_time_ms": np.mean(processing_times),
                "p95_processing_time_ms": np.percentile(processing_times, 95),
                "avg_confidence": np.mean(confidences) if confidences else None,
                "error_rate": len(
                    [p for p in recent_predictions if p["status"] == "error"]
                )
                / len(recent_predictions),
                "predictions_per_hour": len(recent_predictions) / hours,
            }
            return stats
        except Exception as e:
            self.logger.error(f"Failed to get prediction stats: {str(e)}")
            return {}


class ModelServer:
    """High-performance model serving with enterprise features"""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.app = Flask(__name__)
        CORS(self.app)
        self.model_cache = ModelCache(
            max_models=config.get("max_cached_models", 5),
            ttl_hours=config.get("model_ttl_hours", 24),
        )
        self.model_loader = ModelLoader(
            mlflow_uri=config["mlflow_uri"], s3_bucket=config.get("s3_bucket")
        )
        redis_config = config.get("redis", {})
        self.redis_client = None
        if redis_config:
            self.redis_client = redis.Redis(
                host=redis_config.get("host", "localhost"),
                port=redis_config.get("port", 6379),
                db=redis_config.get("db", 0),
                decode_responses=True,
            )
        self.prediction_logger = PredictionLogger(self.redis_client)
        logging.basicConfig(
            level=getattr(logging, config.get("log_level", "INFO")),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger(__name__)
        self._setup_routes()
        self._start_monitoring()

    def _setup_routes(self) -> Any:
        """Setup Flask routes"""

        @self.app.route("/health", methods=["GET"])
        def health_check():
            """Health check endpoint"""
            try:
                memory_percent = psutil.virtual_memory().percent
                cpu_percent = psutil.cpu_percent(interval=1)
                redis_status = "healthy"
                if self.redis_client:
                    try:
                        self.redis_client.ping()
                    except:
                        redis_status = "unhealthy"
                status = {
                    "status": "healthy",
                    "timestamp": datetime.now().isoformat(),
                    "memory_usage_percent": memory_percent,
                    "cpu_usage_percent": cpu_percent,
                    "redis_status": redis_status,
                    "cached_models": len(self.model_cache.cache),
                    "version": self.config.get("version", "1.0.0"),
                }
                if (
                    memory_percent > 90
                    or cpu_percent > 90
                    or redis_status == "unhealthy"
                ):
                    status["status"] = "degraded"
                    return (jsonify(status), 503)
                return (jsonify(status), 200)
            except Exception as e:
                return (
                    jsonify(
                        {
                            "status": "unhealthy",
                            "error": str(e),
                            "timestamp": datetime.now().isoformat(),
                        }
                    ),
                    503,
                )

        @self.app.route("/ready", methods=["GET"])
        def readiness_check():
            """Readiness check endpoint"""
            try:
                test_model = self.config.get("default_model")
                if test_model:
                    model_name = test_model["name"]
                    model_version = test_model["version"]
                    model = self._get_model(model_name, model_version)
                    if model is None:
                        return (
                            jsonify(
                                {
                                    "status": "not_ready",
                                    "reason": "Cannot load default model",
                                    "timestamp": datetime.now().isoformat(),
                                }
                            ),
                            503,
                        )
                return (
                    jsonify(
                        {"status": "ready", "timestamp": datetime.now().isoformat()}
                    ),
                    200,
                )
            except Exception as e:
                return (
                    jsonify(
                        {
                            "status": "not_ready",
                            "error": str(e),
                            "timestamp": datetime.now().isoformat(),
                        }
                    ),
                    503,
                )

        @self.app.route("/predict", methods=["POST"])
        def predict():
            """Main prediction endpoint"""
            request_id = str(uuid.uuid4())
            start_time = time.time()
            try:
                data = request.get_json()
                if not data:
                    raise ValueError("No JSON data provided")
                model_name = data.get("model_name")
                model_version = data.get("model_version", "latest")
                features = data.get("features")
                metadata = data.get("metadata", {})
                if not model_name or not features:
                    raise ValueError("model_name and features are required")
                pred_request = PredictionRequest(
                    request_id=request_id,
                    model_name=model_name,
                    model_version=model_version,
                    features=features,
                    metadata=metadata,
                    timestamp=datetime.now(),
                )
                model = self._get_model(model_name, model_version)
                if model is None:
                    raise ValueError(f"Model {model_name}:{model_version} not found")
                feature_array = self._prepare_features(features, model)
                prediction = model.predict(feature_array)
                confidence = None
                if hasattr(model, "predict_proba"):
                    proba = model.predict_proba(feature_array)
                    confidence = float(np.max(proba))
                explanation = None
                if metadata.get("explain", False):
                    explanation = self._explain_prediction(
                        model, feature_array, features
                    )
                processing_time = (time.time() - start_time) * 1000
                response = PredictionResponse(
                    request_id=request_id,
                    model_name=model_name,
                    model_version=model_version,
                    prediction=(
                        prediction.tolist()
                        if isinstance(prediction, np.ndarray)
                        else prediction
                    ),
                    confidence=confidence,
                    explanation=explanation,
                    processing_time_ms=processing_time,
                    timestamp=datetime.now(),
                    status="success",
                )
                self.prediction_logger.log_prediction(pred_request, response)
                REQUEST_COUNT.labels(
                    model_name=model_name, version=model_version, endpoint="predict"
                ).inc()
                REQUEST_DURATION.labels(
                    model_name=model_name, version=model_version
                ).observe(processing_time / 1000)
                PREDICTION_COUNT.labels(
                    model_name=model_name, version=model_version
                ).inc()
                return (jsonify(asdict(response)), 200)
            except Exception as e:
                processing_time = (time.time() - start_time) * 1000
                error_response = PredictionResponse(
                    request_id=request_id,
                    model_name=(
                        data.get("model_name", "unknown")
                        if "data" in locals()
                        else "unknown"
                    ),
                    model_version=(
                        data.get("model_version", "unknown")
                        if "data" in locals()
                        else "unknown"
                    ),
                    prediction=None,
                    confidence=None,
                    explanation=None,
                    processing_time_ms=processing_time,
                    timestamp=datetime.now(),
                    status="error",
                    error_message=str(e),
                )
                if "pred_request" in locals():
                    self.prediction_logger.log_prediction(pred_request, error_response)
                ERROR_COUNT.labels(
                    model_name=error_response.model_name,
                    version=error_response.model_version,
                    error_type=type(e).__name__,
                ).inc()
                self.logger.error(f"Prediction error: {str(e)}")
                return (jsonify(asdict(error_response)), 400)

        @self.app.route("/batch_predict", methods=["POST"])
        def batch_predict():
            """Batch prediction endpoint"""
            request_id = str(uuid.uuid4())
            start_time = time.time()
            try:
                data = request.get_json()
                if not data:
                    raise ValueError("No JSON data provided")
                model_name = data.get("model_name")
                model_version = data.get("model_version", "latest")
                batch_features = data.get("batch_features")
                data.get("metadata", {})
                if not model_name or not batch_features:
                    raise ValueError("model_name and batch_features are required")
                model = self._get_model(model_name, model_version)
                if model is None:
                    raise ValueError(f"Model {model_name}:{model_version} not found")
                predictions = []
                for i, features in enumerate(batch_features):
                    try:
                        feature_array = self._prepare_features(features, model)
                        prediction = model.predict(feature_array)
                        confidence = None
                        if hasattr(model, "predict_proba"):
                            proba = model.predict_proba(feature_array)
                            confidence = float(np.max(proba))
                        predictions.append(
                            {
                                "index": i,
                                "prediction": (
                                    prediction.tolist()
                                    if isinstance(prediction, np.ndarray)
                                    else prediction
                                ),
                                "confidence": confidence,
                                "status": "success",
                            }
                        )
                    except Exception as e:
                        predictions.append(
                            {
                                "index": i,
                                "prediction": None,
                                "confidence": None,
                                "status": "error",
                                "error_message": str(e),
                            }
                        )
                processing_time = (time.time() - start_time) * 1000
                response = {
                    "request_id": request_id,
                    "model_name": model_name,
                    "model_version": model_version,
                    "predictions": predictions,
                    "processing_time_ms": processing_time,
                    "timestamp": datetime.now().isoformat(),
                    "total_samples": len(batch_features),
                    "successful_predictions": len(
                        [p for p in predictions if p["status"] == "success"]
                    ),
                }
                REQUEST_COUNT.labels(
                    model_name=model_name,
                    version=model_version,
                    endpoint="batch_predict",
                ).inc()
                REQUEST_DURATION.labels(
                    model_name=model_name, version=model_version
                ).observe(processing_time / 1000)
                PREDICTION_COUNT.labels(
                    model_name=model_name, version=model_version
                ).inc(len(batch_features))
                return (jsonify(response), 200)
            except Exception as e:
                self.logger.error(f"Batch prediction error: {str(e)}")
                return (
                    jsonify(
                        {
                            "request_id": request_id,
                            "error": str(e),
                            "timestamp": datetime.now().isoformat(),
                        }
                    ),
                    400,
                )

        @self.app.route("/models", methods=["GET"])
        def list_models():
            """List available models"""
            try:
                cached_models = self.model_cache.get_cache_stats()
                return (
                    jsonify(
                        {
                            "cached_models": cached_models["cached_models"],
                            "cache_stats": cached_models,
                            "timestamp": datetime.now().isoformat(),
                        }
                    ),
                    200,
                )
            except Exception as e:
                return (jsonify({"error": str(e)}), 500)

        @self.app.route("/models/<model_name>/stats", methods=["GET"])
        def model_stats(model_name):
            """Get model statistics"""
            try:
                hours = request.args.get("hours", 24, type=int)
                stats = self.prediction_logger.get_prediction_stats(model_name, hours)
                return (
                    jsonify(
                        {
                            "model_name": model_name,
                            "stats": stats,
                            "time_window_hours": hours,
                            "timestamp": datetime.now().isoformat(),
                        }
                    ),
                    200,
                )
            except Exception as e:
                return (jsonify({"error": str(e)}), 500)

        @self.app.route("/metrics", methods=["GET"])
        def metrics():
            """Prometheus metrics endpoint"""
            return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

        @self.app.route("/cache/clear", methods=["POST"])
        def clear_cache():
            """Clear model cache"""
            try:
                self.model_cache.clear_cache()
                return (
                    jsonify(
                        {
                            "message": "Cache cleared successfully",
                            "timestamp": datetime.now().isoformat(),
                        }
                    ),
                    200,
                )
            except Exception as e:
                return (jsonify({"error": str(e)}), 500)

    def _get_model(self, model_name: str, version: str) -> Optional[BaseEstimator]:
        """Get model from cache or load from registry"""
        model = self.model_cache.get_model(model_name, version)
        if model is None:
            try:
                model = self.model_loader.load_model(model_name, version)
                self.model_cache.put_model(model_name, version, model)
            except Exception as e:
                self.logger.error(
                    f"Failed to load model {model_name}:{version}: {str(e)}"
                )
                return None
        return model

    def _prepare_features(
        self, features: Dict[str, Any], model: BaseEstimator
    ) -> np.ndarray:
        """Prepare features for prediction"""
        df = pd.DataFrame([features])
        return df.values

    def _explain_prediction(
        self,
        model: BaseEstimator,
        features: np.ndarray,
        original_features: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate prediction explanation"""
        explanation = {}
        if hasattr(model, "feature_importances_"):
            feature_names = list(original_features.keys())
            importances = model.feature_importances_
            explanation["feature_importance"] = dict(
                zip(feature_names, importances.tolist())
            )
        if hasattr(model, "coef_"):
            feature_names = list(original_features.keys())
            coefficients = model.coef_
            if coefficients.ndim > 1:
                coefficients = coefficients[0]
            explanation["coefficients"] = dict(
                zip(feature_names, coefficients.tolist())
            )
        return explanation

    def _start_monitoring(self) -> Any:
        """Start background monitoring thread"""

        def monitor():
            while True:
                try:
                    memory_usage = psutil.virtual_memory().used
                    cpu_usage = psutil.cpu_percent(interval=1)
                    for model_key in self.model_cache.cache.keys():
                        model_name, version = model_key.split(":")
                        MEMORY_USAGE.labels(model_name=model_name, version=version).set(
                            memory_usage
                        )
                        CPU_USAGE.labels(model_name=model_name, version=version).set(
                            cpu_usage
                        )
                    time.sleep(30)
                except Exception as e:
                    self.logger.error(f"Monitoring error: {str(e)}")
                    time.sleep(60)

        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()

    def run(self, host: str = "0.0.0.0", port: int = 8080, debug: bool = False) -> Any:
        """Run the model server"""
        self.logger.info(f"Starting model server on {host}:{port}")
        self.app.run(host=host, port=port, debug=debug, threaded=True)


def create_server_config() -> Dict[str, Any]:
    """Create default server configuration"""
    return {
        "mlflow_uri": os.getenv("MLFLOW_URI", "http://mlflow-server:5000"),
        "s3_bucket": os.getenv("S3_BUCKET"),
        "redis": {
            "host": os.getenv("REDIS_HOST", "localhost"),
            "port": int(os.getenv("REDIS_PORT", "6379")),
            "db": int(os.getenv("REDIS_DB", "0")),
        },
        "max_cached_models": int(os.getenv("MAX_CACHED_MODELS", "5")),
        "model_ttl_hours": int(os.getenv("MODEL_TTL_HOURS", "24")),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "version": os.getenv("MODEL_SERVER_VERSION", "1.0.0"),
        "default_model": (
            {
                "name": os.getenv("DEFAULT_MODEL_NAME"),
                "version": os.getenv("DEFAULT_MODEL_VERSION", "latest"),
            }
            if os.getenv("DEFAULT_MODEL_NAME")
            else None
        ),
    }


if __name__ == "__main__":
    config = create_server_config()
    server = ModelServer(config)
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    server.run(host=host, port=port, debug=debug)
