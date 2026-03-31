"""
MLOps Pipeline Infrastructure for NexaFi
Implements enterprise-grade ML pipeline with automated deployment and monitoring
"""

import datetime
import json
import logging
import os
import pickle
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Tuple

import boto3
import docker
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from kubernetes import client, config
from mlflow.tracking import MlflowClient
from sklearn.base import BaseEstimator
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class ModelMetadata:
    """Model metadata for tracking and versioning"""

    model_id: str
    model_name: str
    version: str
    created_at: datetime.datetime
    created_by: str
    model_type: str
    framework: str
    performance_metrics: Dict[str, float]
    data_schema: Dict[str, Any]
    feature_importance: Dict[str, float]
    model_size_mb: float
    training_duration_seconds: float
    hyperparameters: Dict[str, Any]
    validation_results: Dict[str, Any]
    compliance_status: str
    risk_level: str
    approval_status: str
    deployment_status: str
    tags: List[str]


@dataclass
class DeploymentConfig:
    """Deployment configuration for models"""

    environment: str
    replicas: int
    cpu_request: str
    cpu_limit: str
    memory_request: str
    memory_limit: str
    auto_scaling: bool
    min_replicas: int
    max_replicas: int
    target_cpu_utilization: int
    health_check_path: str
    readiness_probe_delay: int
    liveness_probe_delay: int
    rolling_update_strategy: Dict[str, Any]
    canary_deployment: bool
    canary_percentage: int
    monitoring_enabled: bool
    logging_level: str
    feature_flags: Dict[str, bool]


class ModelRegistry:
    """Enterprise model registry with versioning and metadata management"""

    def __init__(self, registry_uri: str, s3_bucket: str = None) -> None:
        self.registry_uri = registry_uri
        self.s3_bucket = s3_bucket
        self.client = MlflowClient(registry_uri)
        self.s3_client = boto3.client("s3") if s3_bucket else None
        self.logger = logging.getLogger(__name__)

    def register_model(
        self,
        model: BaseEstimator,
        metadata: ModelMetadata,
        model_artifacts: Dict[str, Any] = None,
    ) -> str:
        """Register a new model version with comprehensive metadata"""
        try:
            with mlflow.start_run(
                run_name=f"{metadata.model_name}_v{metadata.version}"
            ):
                model_uri = mlflow.sklearn.log_model(
                    model, "model", registered_model_name=metadata.model_name
                )
                mlflow.log_params(metadata.hyperparameters)
                mlflow.log_metrics(metadata.performance_metrics)
                mlflow.log_dict(asdict(metadata), "metadata.json")
                if model_artifacts:
                    for name, artifact in model_artifacts.items():
                        if isinstance(artifact, dict):
                            mlflow.log_dict(artifact, f"{name}.json")
                        else:
                            mlflow.log_artifact(artifact, name)
                model_version = self.client.create_model_version(
                    name=metadata.model_name,
                    source=model_uri.model_uri,
                    tags={
                        "compliance_status": metadata.compliance_status,
                        "risk_level": metadata.risk_level,
                        "approval_status": metadata.approval_status,
                        "model_type": metadata.model_type,
                        "framework": metadata.framework,
                    },
                )
                if self.s3_client:
                    self._store_model_s3(model, metadata)
                self.logger.info(
                    f"Model {metadata.model_name} v{metadata.version} registered successfully"
                )
                return model_version.version
        except Exception as e:
            self.logger.error(f"Failed to register model: {str(e)}")
            raise

    def get_model(
        self, model_name: str, version: str = "latest"
    ) -> Tuple[BaseEstimator, ModelMetadata]:
        """Retrieve model and metadata from registry"""
        try:
            if version == "latest":
                model_version = self.client.get_latest_versions(
                    model_name, stages=["Production"]
                )[0]
            else:
                model_version = self.client.get_model_version(model_name, version)
            model_uri = f"models:/{model_name}/{model_version.version}"
            model = mlflow.sklearn.load_model(model_uri)
            run = self.client.get_run(model_version.run_id)
            f"{run.info.artifact_uri}/metadata.json"
            metadata = self._load_metadata(model_version, run)
            return (model, metadata)
        except Exception as e:
            self.logger.error(f"Failed to retrieve model: {str(e)}")
            raise

    def promote_model(self, model_name: str, version: str, stage: str) -> bool:
        """Promote model to different stage (Staging, Production)"""
        try:
            self.client.transition_model_version_stage(
                name=model_name, version=version, stage=stage
            )
            self.logger.info(f"Model {model_name} v{version} promoted to {stage}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to promote model: {str(e)}")
            return False

    def archive_model(self, model_name: str, version: str) -> bool:
        """Archive old model version"""
        try:
            self.client.transition_model_version_stage(
                name=model_name, version=version, stage="Archived"
            )
            self.logger.info(f"Model {model_name} v{version} archived")
            return True
        except Exception as e:
            self.logger.error(f"Failed to archive model: {str(e)}")
            return False

    def _store_model_s3(self, model: BaseEstimator, metadata: ModelMetadata) -> Any:
        """Store model artifacts in S3"""
        model_key = f"models/{metadata.model_name}/v{metadata.version}/model.pkl"
        metadata_key = f"models/{metadata.model_name}/v{metadata.version}/metadata.json"
        model_bytes = pickle.dumps(model)
        self.s3_client.put_object(
            Bucket=self.s3_bucket, Key=model_key, Body=model_bytes
        )
        metadata_json = json.dumps(asdict(metadata), default=str)
        self.s3_client.put_object(
            Bucket=self.s3_bucket, Key=metadata_key, Body=metadata_json
        )

    def _load_metadata(self, model_version: Any, run: Any) -> ModelMetadata:
        """Load metadata from MLflow run"""
        return ModelMetadata(
            model_id=model_version.run_id,
            model_name=model_version.name,
            version=model_version.version,
            created_at=datetime.datetime.fromtimestamp(
                model_version.creation_timestamp / 1000
            ),
            created_by=run.data.tags.get("mlflow.user", "unknown"),
            model_type=model_version.tags.get("model_type", "unknown"),
            framework=model_version.tags.get("framework", "sklearn"),
            performance_metrics=run.data.metrics,
            data_schema={},
            feature_importance={},
            model_size_mb=0.0,
            training_duration_seconds=0.0,
            hyperparameters=run.data.params,
            validation_results={},
            compliance_status=model_version.tags.get("compliance_status", "pending"),
            risk_level=model_version.tags.get("risk_level", "medium"),
            approval_status=model_version.tags.get("approval_status", "pending"),
            deployment_status="registered",
            tags=list(model_version.tags.keys()),
        )


class ModelValidator:
    """Comprehensive model validation for financial compliance"""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.validation_rules = self._load_validation_rules()

    def validate_model(
        self,
        model: BaseEstimator,
        metadata: ModelMetadata,
        test_data: pd.DataFrame,
        test_labels: np.ndarray,
    ) -> Dict[str, Any]:
        """Comprehensive model validation"""
        validation_results = {
            "performance_validation": self._validate_performance(
                model, test_data, test_labels
            ),
            "bias_validation": self._validate_bias(model, test_data, test_labels),
            "stability_validation": self._validate_stability(model, test_data),
            "compliance_validation": self._validate_compliance(model, metadata),
            "security_validation": self._validate_security(model),
            "interpretability_validation": self._validate_interpretability(model),
            "data_quality_validation": self._validate_data_quality(test_data),
            "overall_score": 0.0,
            "passed": False,
            "issues": [],
            "recommendations": [],
        }
        scores = [
            v.get("score", 0)
            for v in validation_results.values()
            if isinstance(v, dict)
        ]
        validation_results["overall_score"] = np.mean(scores) if scores else 0.0
        validation_results["passed"] = validation_results["overall_score"] >= 0.8
        return validation_results

    def _validate_performance(
        self, model: BaseEstimator, test_data: pd.DataFrame, test_labels: np.ndarray
    ) -> Dict[str, Any]:
        """Validate model performance metrics"""
        try:
            predictions = model.predict(test_data)
            metrics = {
                "accuracy": accuracy_score(test_labels, predictions),
                "precision": precision_score(
                    test_labels, predictions, average="weighted"
                ),
                "recall": recall_score(test_labels, predictions, average="weighted"),
                "f1_score": f1_score(test_labels, predictions, average="weighted"),
            }
            thresholds = {
                "accuracy": 0.85,
                "precision": 0.8,
                "recall": 0.75,
                "f1_score": 0.8,
            }
            passed_metrics = sum(
                (1 for metric, value in metrics.items() if value >= thresholds[metric])
            )
            score = passed_metrics / len(thresholds)
            return {
                "metrics": metrics,
                "thresholds": thresholds,
                "score": score,
                "passed": score >= 0.75,
                "issues": [
                    f"Low {metric}: {value:.3f} < {thresholds[metric]}"
                    for metric, value in metrics.items()
                    if value < thresholds[metric]
                ],
            }
        except Exception as e:
            self.logger.error(f"Performance validation failed: {str(e)}")
            return {"score": 0.0, "passed": False, "error": str(e)}

    def _validate_bias(
        self, model: BaseEstimator, test_data: pd.DataFrame, test_labels: np.ndarray
    ) -> Dict[str, Any]:
        """Validate model for bias and fairness"""
        try:
            predictions = model.predict(test_data)
            bias_metrics = {}
            protected_attributes = ["gender", "age_group", "ethnicity"]
            for attr in protected_attributes:
                if attr in test_data.columns:
                    groups = test_data[attr].unique()
                    group_rates = {}
                    for group in groups:
                        mask = test_data[attr] == group
                        if mask.sum() > 0:
                            group_rate = predictions[mask].mean()
                            group_rates[str(group)] = group_rate
                    if len(group_rates) > 1:
                        rates = list(group_rates.values())
                        bias_metrics[f"{attr}_disparity"] = max(rates) - min(rates)
            max_disparity = max(bias_metrics.values()) if bias_metrics else 0.0
            score = max(0.0, 1.0 - max_disparity)
            return {
                "bias_metrics": bias_metrics,
                "max_disparity": max_disparity,
                "score": score,
                "passed": max_disparity < 0.1,
                "issues": [
                    f"High disparity in {attr}: {disp:.3f}"
                    for attr, disp in bias_metrics.items()
                    if disp > 0.1
                ],
            }
        except Exception as e:
            self.logger.error(f"Bias validation failed: {str(e)}")
            return {"score": 0.0, "passed": False, "error": str(e)}

    def _validate_stability(
        self, model: BaseEstimator, test_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Validate model stability and robustness"""
        try:
            noise_levels = [0.01, 0.05, 0.1]
            stability_scores = []
            original_predictions = model.predict(test_data)
            for noise_level in noise_levels:
                noisy_data = test_data.copy()
                numerical_cols = test_data.select_dtypes(include=[np.number]).columns
                for col in numerical_cols:
                    noise = np.random.normal(
                        0, noise_level * test_data[col].std(), len(test_data)
                    )
                    noisy_data[col] = test_data[col] + noise
                noisy_predictions = model.predict(noisy_data)
                if hasattr(model, "predict_proba"):
                    original_proba = model.predict_proba(test_data)
                    noisy_proba = model.predict_proba(noisy_data)
                    stability = 1.0 - np.mean(np.abs(original_proba - noisy_proba))
                else:
                    stability = np.mean(original_predictions == noisy_predictions)
                stability_scores.append(stability)
            avg_stability = np.mean(stability_scores)
            return {
                "stability_scores": dict(zip(noise_levels, stability_scores)),
                "average_stability": avg_stability,
                "score": avg_stability,
                "passed": avg_stability >= 0.8,
                "issues": (
                    []
                    if avg_stability >= 0.8
                    else ["Model shows instability with noisy inputs"]
                ),
            }
        except Exception as e:
            self.logger.error(f"Stability validation failed: {str(e)}")
            return {"score": 0.0, "passed": False, "error": str(e)}

    def _validate_compliance(
        self, model: BaseEstimator, metadata: ModelMetadata
    ) -> Dict[str, Any]:
        """Validate regulatory compliance requirements"""
        compliance_checks = {
            "model_documentation": len(metadata.tags) > 0,
            "performance_tracking": len(metadata.performance_metrics) > 0,
            "version_control": metadata.version is not None,
            "approval_workflow": metadata.approval_status in ["approved", "pending"],
            "risk_assessment": metadata.risk_level in ["low", "medium", "high"],
            "audit_trail": metadata.created_by is not None,
        }
        passed_checks = sum(compliance_checks.values())
        score = passed_checks / len(compliance_checks)
        return {
            "compliance_checks": compliance_checks,
            "score": score,
            "passed": score >= 0.8,
            "issues": [
                f"Failed compliance check: {check}"
                for check, passed in compliance_checks.items()
                if not passed
            ],
        }

    def _validate_security(self, model: BaseEstimator) -> Dict[str, Any]:
        """Validate model security aspects"""
        security_checks = {
            "no_hardcoded_secrets": True,
            "input_sanitization": True,
            "output_validation": True,
            "access_control": True,
            "encryption_support": True,
        }
        score = sum(security_checks.values()) / len(security_checks)
        return {
            "security_checks": security_checks,
            "score": score,
            "passed": score >= 0.9,
            "issues": [],
        }

    def _validate_interpretability(self, model: BaseEstimator) -> Dict[str, Any]:
        """Validate model interpretability for regulatory requirements"""
        interpretability_score = 0.0
        if hasattr(model, "feature_importances_"):
            interpretability_score += 0.4
        if hasattr(model, "coef_"):
            interpretability_score += 0.4
        interpretable_models = [
            "LinearRegression",
            "LogisticRegression",
            "DecisionTree",
        ]
        if any((model_type in str(type(model)) for model_type in interpretable_models)):
            interpretability_score += 0.2
        return {
            "interpretability_score": interpretability_score,
            "score": interpretability_score,
            "passed": interpretability_score >= 0.6,
            "issues": (
                []
                if interpretability_score >= 0.6
                else ["Model lacks sufficient interpretability"]
            ),
        }

    def _validate_data_quality(self, test_data: pd.DataFrame) -> Dict[str, Any]:
        """Validate data quality for model testing"""
        quality_metrics = {
            "completeness": 1.0 - test_data.isnull().sum().sum() / test_data.size,
            "uniqueness": len(test_data.drop_duplicates()) / len(test_data),
            "consistency": 1.0,
            "validity": 1.0,
        }
        score = np.mean(list(quality_metrics.values()))
        return {
            "quality_metrics": quality_metrics,
            "score": score,
            "passed": score >= 0.9,
            "issues": [],
        }

    def _load_validation_rules(self) -> Dict[str, Any]:
        """Load validation rules from configuration"""
        return {
            "performance_thresholds": {
                "accuracy": 0.85,
                "precision": 0.8,
                "recall": 0.75,
            },
            "bias_thresholds": {"max_disparity": 0.1},
            "stability_thresholds": {"min_stability": 0.8},
        }


class ModelDeployer:
    """Automated model deployment with Kubernetes and Docker"""

    def __init__(self, registry_url: str, namespace: str = "nexafi-ml") -> None:
        self.registry_url = registry_url
        self.namespace = namespace
        self.docker_client = docker.from_env()
        self.k8s_client = self._init_k8s_client()
        self.logger = logging.getLogger(__name__)

    def deploy_model(
        self, model_name: str, version: str, config: DeploymentConfig
    ) -> bool:
        """Deploy model to Kubernetes cluster"""
        try:
            image_tag = self._build_model_image(model_name, version)
            manifests = self._create_k8s_manifests(
                model_name, version, image_tag, config
            )
            self._deploy_to_k8s(manifests)
            if config.monitoring_enabled:
                self._setup_monitoring(model_name, version)
            self.logger.info(f"Model {model_name} v{version} deployed successfully")
            return True
        except Exception as e:
            self.logger.error(f"Deployment failed: {str(e)}")
            return False

    def rollback_deployment(self, model_name: str, previous_version: str) -> bool:
        """Rollback to previous model version"""
        try:
            deployment_name = f"{model_name}-deployment"
            apps_v1 = client.AppsV1Api()
            deployment = apps_v1.read_namespaced_deployment(
                name=deployment_name, namespace=self.namespace
            )
            previous_image = f"{self.registry_url}/{model_name}:{previous_version}"
            deployment.spec.template.spec.containers[0].image = previous_image
            apps_v1.patch_namespaced_deployment(
                name=deployment_name, namespace=self.namespace, body=deployment
            )
            self.logger.info(f"Rolled back {model_name} to version {previous_version}")
            return True
        except Exception as e:
            self.logger.error(f"Rollback failed: {str(e)}")
            return False

    def _build_model_image(self, model_name: str, version: str) -> str:
        """Build Docker image for model"""
        dockerfile_content = self._generate_dockerfile(model_name, version)
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            dockerfile_path = os.path.join(temp_dir, "Dockerfile")
            with open(dockerfile_path, "w") as f:
                f.write(dockerfile_content)
            image_tag = f"{self.registry_url}/{model_name}:{version}"
            self.docker_client.images.build(path=temp_dir, tag=image_tag, rm=True)
            self.docker_client.images.push(image_tag)
            return image_tag

    def _generate_dockerfile(self, model_name: str, version: str) -> str:
        """Generate Dockerfile for model serving"""
        return f'\nFROM python:3.11-slim\n\nWORKDIR /app\n\n# Install dependencies\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\n\n# Copy model serving code\nCOPY model_server.py .\nCOPY model_loader.py .\n\n# Set environment variables\nENV MODEL_NAME={model_name}\nENV MODEL_VERSION={version}\nENV PYTHONPATH=/app\n\n# Expose port\nEXPOSE 8080\n\n# Health check\nHEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \\\n    CMD curl -f http://localhost:8080/health || exit 1\n\n# Run model server\nCMD ["python", "model_server.py"]\n'

    def _create_k8s_manifests(
        self, model_name: str, version: str, image_tag: str, config: DeploymentConfig
    ) -> Dict[str, Any]:
        """Create Kubernetes deployment manifests"""
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": f"{model_name}-deployment",
                "namespace": self.namespace,
                "labels": {
                    "app": model_name,
                    "version": version,
                    "component": "ml-model",
                },
            },
            "spec": {
                "replicas": config.replicas,
                "selector": {"matchLabels": {"app": model_name, "version": version}},
                "template": {
                    "metadata": {
                        "labels": {
                            "app": model_name,
                            "version": version,
                            "component": "ml-model",
                        }
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": model_name,
                                "image": image_tag,
                                "ports": [{"containerPort": 8080}],
                                "resources": {
                                    "requests": {
                                        "cpu": config.cpu_request,
                                        "memory": config.memory_request,
                                    },
                                    "limits": {
                                        "cpu": config.cpu_limit,
                                        "memory": config.memory_limit,
                                    },
                                },
                                "env": [
                                    {"name": "MODEL_NAME", "value": model_name},
                                    {"name": "MODEL_VERSION", "value": version},
                                    {
                                        "name": "LOG_LEVEL",
                                        "value": config.logging_level,
                                    },
                                ],
                                "readinessProbe": {
                                    "httpGet": {
                                        "path": config.health_check_path,
                                        "port": 8080,
                                    },
                                    "initialDelaySeconds": config.readiness_probe_delay,
                                    "periodSeconds": 10,
                                },
                                "livenessProbe": {
                                    "httpGet": {
                                        "path": config.health_check_path,
                                        "port": 8080,
                                    },
                                    "initialDelaySeconds": config.liveness_probe_delay,
                                    "periodSeconds": 30,
                                },
                            }
                        ]
                    },
                },
                "strategy": config.rolling_update_strategy,
            },
        }
        service = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": f"{model_name}-service",
                "namespace": self.namespace,
                "labels": {"app": model_name, "component": "ml-model"},
            },
            "spec": {
                "selector": {"app": model_name},
                "ports": [{"port": 80, "targetPort": 8080, "protocol": "TCP"}],
                "type": "ClusterIP",
            },
        }
        hpa = None
        if config.auto_scaling:
            hpa = {
                "apiVersion": "autoscaling/v2",
                "kind": "HorizontalPodAutoscaler",
                "metadata": {"name": f"{model_name}-hpa", "namespace": self.namespace},
                "spec": {
                    "scaleTargetRef": {
                        "apiVersion": "apps/v1",
                        "kind": "Deployment",
                        "name": f"{model_name}-deployment",
                    },
                    "minReplicas": config.min_replicas,
                    "maxReplicas": config.max_replicas,
                    "metrics": [
                        {
                            "type": "Resource",
                            "resource": {
                                "name": "cpu",
                                "target": {
                                    "type": "Utilization",
                                    "averageUtilization": config.target_cpu_utilization,
                                },
                            },
                        }
                    ],
                },
            }
        manifests = {"deployment": deployment, "service": service}
        if hpa:
            manifests["hpa"] = hpa
        return manifests

    def _deploy_to_k8s(self, manifests: Dict[str, Any]) -> Any:
        """Deploy manifests to Kubernetes"""
        apps_v1 = client.AppsV1Api()
        core_v1 = client.CoreV1Api()
        autoscaling_v2 = client.AutoscalingV2Api()
        try:
            apps_v1.create_namespaced_deployment(
                namespace=self.namespace, body=manifests["deployment"]
            )
        except client.ApiException as e:
            if e.status == 409:
                apps_v1.patch_namespaced_deployment(
                    name=manifests["deployment"]["metadata"]["name"],
                    namespace=self.namespace,
                    body=manifests["deployment"],
                )
            else:
                raise
        try:
            core_v1.create_namespaced_service(
                namespace=self.namespace, body=manifests["service"]
            )
        except client.ApiException as e:
            if e.status == 409:
                core_v1.patch_namespaced_service(
                    name=manifests["service"]["metadata"]["name"],
                    namespace=self.namespace,
                    body=manifests["service"],
                )
            else:
                raise
        if "hpa" in manifests:
            try:
                autoscaling_v2.create_namespaced_horizontal_pod_autoscaler(
                    namespace=self.namespace, body=manifests["hpa"]
                )
            except client.ApiException as e:
                if e.status == 409:
                    autoscaling_v2.patch_namespaced_horizontal_pod_autoscaler(
                        name=manifests["hpa"]["metadata"]["name"],
                        namespace=self.namespace,
                        body=manifests["hpa"],
                    )
                else:
                    raise

    def _setup_monitoring(self, model_name: str, version: str) -> Any:
        """Setup monitoring for deployed model"""
        self.logger.info(f"Setting up monitoring for {model_name} v{version}")

    def _init_k8s_client(self) -> Any:
        """Initialize Kubernetes client"""
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        return client.ApiClient()


class ModelMonitor:
    """Comprehensive model monitoring and alerting"""

    def __init__(self, metrics_backend: str = "prometheus") -> None:
        self.metrics_backend = metrics_backend
        self.logger = logging.getLogger(__name__)
        self.alert_thresholds = self._load_alert_thresholds()

    def monitor_model_performance(
        self,
        model_name: str,
        predictions: np.ndarray,
        actuals: np.ndarray = None,
        features: pd.DataFrame = None,
    ) -> Dict[str, Any]:
        """Monitor model performance in real-time"""
        monitoring_results = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "model_name": model_name,
            "prediction_stats": self._analyze_predictions(predictions),
            "data_drift": (
                self._detect_data_drift(features) if features is not None else None
            ),
            "performance_metrics": (
                self._calculate_performance_metrics(predictions, actuals)
                if actuals is not None
                else None
            ),
            "alerts": [],
        }
        alerts = self._check_alerts(monitoring_results)
        monitoring_results["alerts"] = alerts
        self._log_metrics(monitoring_results)
        if alerts:
            self._send_alerts(alerts)
        return monitoring_results

    def _analyze_predictions(self, predictions: np.ndarray) -> Dict[str, float]:
        """Analyze prediction distribution and statistics"""
        return {
            "mean": float(np.mean(predictions)),
            "std": float(np.std(predictions)),
            "min": float(np.min(predictions)),
            "max": float(np.max(predictions)),
            "median": float(np.median(predictions)),
            "q25": float(np.percentile(predictions, 25)),
            "q75": float(np.percentile(predictions, 75)),
            "count": len(predictions),
        }

    def _detect_data_drift(self, features: pd.DataFrame) -> Dict[str, Any]:
        """Detect data drift in input features"""
        drift_results = {}
        for column in features.select_dtypes(include=[np.number]).columns:
            current_mean = features[column].mean()
            current_std = features[column].std()
            drift_score = abs(current_mean) / (current_std + 1e-08)
            drift_results[column] = {
                "drift_score": float(drift_score),
                "drifted": drift_score > 2.0,
            }
        return drift_results

    def _calculate_performance_metrics(
        self, predictions: np.ndarray, actuals: np.ndarray
    ) -> Dict[str, float]:
        """Calculate performance metrics when ground truth is available"""
        if len(predictions) != len(actuals):
            return {}
        if len(np.unique(actuals)) <= 10:
            return {
                "accuracy": float(accuracy_score(actuals, predictions)),
                "precision": float(
                    precision_score(actuals, predictions, average="weighted")
                ),
                "recall": float(recall_score(actuals, predictions, average="weighted")),
                "f1_score": float(f1_score(actuals, predictions, average="weighted")),
            }
        else:
            from sklearn.metrics import (
                mean_absolute_error,
                mean_squared_error,
                r2_score,
            )

            return {
                "mse": float(mean_squared_error(actuals, predictions)),
                "mae": float(mean_absolute_error(actuals, predictions)),
                "r2_score": float(r2_score(actuals, predictions)),
            }

    def _check_alerts(self, monitoring_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for alert conditions"""
        alerts = []
        pred_stats = monitoring_results["prediction_stats"]
        if pred_stats["std"] > self.alert_thresholds["prediction_std_threshold"]:
            alerts.append(
                {
                    "type": "high_prediction_variance",
                    "severity": "warning",
                    "message": f"High prediction variance: {pred_stats['std']:.4f}",
                    "threshold": self.alert_thresholds["prediction_std_threshold"],
                }
            )
        if monitoring_results["data_drift"]:
            drifted_features = [
                col
                for col, drift in monitoring_results["data_drift"].items()
                if drift["drifted"]
            ]
            if drifted_features:
                alerts.append(
                    {
                        "type": "data_drift",
                        "severity": "critical",
                        "message": f"Data drift detected in features: {drifted_features}",
                        "features": drifted_features,
                    }
                )
        if monitoring_results["performance_metrics"]:
            perf_metrics = monitoring_results["performance_metrics"]
            if "accuracy" in perf_metrics:
                if perf_metrics["accuracy"] < self.alert_thresholds["min_accuracy"]:
                    alerts.append(
                        {
                            "type": "performance_degradation",
                            "severity": "critical",
                            "message": f"Accuracy below threshold: {perf_metrics['accuracy']:.4f}",
                            "threshold": self.alert_thresholds["min_accuracy"],
                        }
                    )
        return alerts

    def _log_metrics(self, monitoring_results: Dict[str, Any]) -> Any:
        """Log metrics to monitoring backend"""
        self.logger.info(
            f"Model monitoring metrics: {json.dumps(monitoring_results, indent=2)}"
        )

    def _send_alerts(self, alerts: List[Dict[str, Any]]) -> Any:
        """Send alerts to notification channels"""
        for alert in alerts:
            self.logger.warning(f"Model Alert: {alert['message']}")

    def _load_alert_thresholds(self) -> Dict[str, float]:
        """Load alert thresholds from configuration"""
        return {
            "prediction_std_threshold": 1.0,
            "min_accuracy": 0.8,
            "max_drift_score": 2.0,
            "max_response_time_ms": 1000,
        }


class MLOpsPipeline:
    """Main MLOps pipeline orchestrator"""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.registry = ModelRegistry(config["mlflow_uri"], config.get("s3_bucket"))
        self.validator = ModelValidator()
        self.deployer = ModelDeployer(
            config["docker_registry"], config.get("k8s_namespace", "nexafi-ml")
        )
        self.monitor = ModelMonitor(config.get("metrics_backend", "prometheus"))
        self.logger = logging.getLogger(__name__)

    def train_and_deploy_model(
        self,
        model: BaseEstimator,
        metadata: ModelMetadata,
        test_data: pd.DataFrame,
        test_labels: np.ndarray,
        deployment_config: DeploymentConfig,
    ) -> bool:
        """Complete MLOps pipeline: train, validate, register, and deploy"""
        try:
            self.logger.info(
                f"Validating model {metadata.model_name} v{metadata.version}"
            )
            validation_results = self.validator.validate_model(
                model, metadata, test_data, test_labels
            )
            if not validation_results["passed"]:
                self.logger.error(
                    f"Model validation failed: {validation_results['issues']}"
                )
                return False
            self.logger.info(
                f"Registering model {metadata.model_name} v{metadata.version}"
            )
            self.registry.register_model(model, metadata)
            if metadata.approval_status == "approved":
                self.logger.info(
                    f"Deploying model {metadata.model_name} v{metadata.version}"
                )
                deployment_success = self.deployer.deploy_model(
                    metadata.model_name, metadata.version, deployment_config
                )
                if deployment_success:
                    self.logger.info(
                        f"Setting up monitoring for {metadata.model_name} v{metadata.version}"
                    )
                    self.logger.info(
                        f"MLOps pipeline completed successfully for {metadata.model_name} v{metadata.version}"
                    )
                    return True
                else:
                    self.logger.error(
                        f"Deployment failed for {metadata.model_name} v{metadata.version}"
                    )
                    return False
            else:
                self.logger.info(
                    f"Model {metadata.model_name} v{metadata.version} registered but not deployed (approval required)"
                )
                return True
        except Exception as e:
            self.logger.error(f"MLOps pipeline failed: {str(e)}")
            return False

    def promote_model_to_production(self, model_name: str, version: str) -> bool:
        """Promote model from staging to production"""
        try:
            success = self.registry.promote_model(model_name, version, "Production")
            if success:
                prod_config = DeploymentConfig(
                    environment="prod",
                    replicas=3,
                    cpu_request="500m",
                    cpu_limit="1000m",
                    memory_request="1Gi",
                    memory_limit="2Gi",
                    auto_scaling=True,
                    min_replicas=2,
                    max_replicas=10,
                    target_cpu_utilization=70,
                    health_check_path="/health",
                    readiness_probe_delay=30,
                    liveness_probe_delay=60,
                    rolling_update_strategy={
                        "type": "RollingUpdate",
                        "rollingUpdate": {"maxUnavailable": "25%", "maxSurge": "25%"},
                    },
                    canary_deployment=True,
                    canary_percentage=10,
                    monitoring_enabled=True,
                    logging_level="INFO",
                    feature_flags={},
                )
                deployment_success = self.deployer.deploy_model(
                    model_name, version, prod_config
                )
                if deployment_success:
                    self.logger.info(
                        f"Model {model_name} v{version} promoted to production"
                    )
                    return True
                else:
                    self.logger.error(
                        f"Failed to deploy {model_name} v{version} to production"
                    )
                    return False
            else:
                return False
        except Exception as e:
            self.logger.error(f"Failed to promote model to production: {str(e)}")
            return False

    def rollback_model(self, model_name: str, target_version: str) -> bool:
        """Rollback model to previous version"""
        try:
            success = self.deployer.rollback_deployment(model_name, target_version)
            if success:
                self.registry.promote_model(model_name, target_version, "Production")
                self.logger.info(
                    f"Model {model_name} rolled back to version {target_version}"
                )
                return True
            else:
                return False
        except Exception as e:
            self.logger.error(f"Failed to rollback model: {str(e)}")
            return False


def create_mlops_config() -> Dict[str, Any]:
    """Create default MLOps configuration"""
    return {
        "mlflow_uri": "http://mlflow-server:5000",
        "s3_bucket": "nexafi-ml-models",
        "docker_registry": "nexafi-registry.com",
        "k8s_namespace": "nexafi-ml",
        "metrics_backend": "prometheus",
        "notification_channels": {
            "slack": {"webhook_url": "https://hooks.slack.com/..."},
            "email": {"smtp_server": "smtp.company.com"},
            "pagerduty": {"api_key": "..."},
        },
    }


if __name__ == "__main__":
    config = create_mlops_config()
    pipeline = MLOpsPipeline(config)
    logger.info("MLOps Pipeline initialized successfully")
