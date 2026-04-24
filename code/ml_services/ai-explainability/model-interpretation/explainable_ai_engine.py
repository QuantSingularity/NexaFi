"""
Explainable AI Engine for NexaFi
Comprehensive AI model interpretation and explanation system for regulatory compliance
"""

import json
import logging
import os
import warnings
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

warnings.filterwarnings("ignore")
import lime
import lime.lime_tabular
import shap
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import partial_dependence, permutation_importance

try:
    DEEP_LEARNING_AVAILABLE = True
except ImportError:
    DEEP_LEARNING_AVAILABLE = False
import uuid

import matplotlib.pyplot as plt
import redis
import structlog
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

Base = declarative_base()


class ExplanationType(Enum):
    """Types of explanations"""

    GLOBAL = "global"
    LOCAL = "local"
    FEATURE_IMPORTANCE = "feature_importance"
    PARTIAL_DEPENDENCE = "partial_dependence"
    SHAP_VALUES = "shap_values"
    LIME_EXPLANATION = "lime_explanation"
    COUNTERFACTUAL = "counterfactual"
    ANCHORS = "anchors"
    DECISION_TREE = "decision_tree"


class ModelType(Enum):
    """Supported model types"""

    SKLEARN = "sklearn"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    CATBOOST = "catboost"
    TENSORFLOW = "tensorflow"
    PYTORCH = "pytorch"
    CUSTOM = "custom"


class ComplianceStandard(Enum):
    """Regulatory compliance standards"""

    GDPR = "gdpr"
    CCPA = "ccpa"
    FCRA = "fcra"
    ECOA = "ecoa"
    SOX = "sox"
    BASEL_III = "basel_iii"
    MiFID_II = "mifid_ii"
    PCI_DSS = "pci_dss"


@dataclass
class ExplanationRequest:
    """Request for model explanation"""

    model_id: str
    explanation_type: ExplanationType
    instance_data: Optional[Dict[str, Any]] = None
    feature_names: Optional[List[str]] = None
    target_class: Optional[Union[int, str]] = None
    compliance_standards: Optional[List[ComplianceStandard]] = None
    explanation_depth: str = "standard"
    include_visualizations: bool = True
    output_format: str = "json"


@dataclass
class ExplanationResult:
    """Result of model explanation"""

    explanation_id: str
    model_id: str
    explanation_type: ExplanationType
    timestamp: datetime
    explanations: Dict[str, Any]
    visualizations: Dict[str, str]
    confidence_score: float
    compliance_status: Dict[ComplianceStandard, bool]
    metadata: Dict[str, Any]


class ModelExplanation(Base):
    """Model explanation storage"""

    __tablename__ = "model_explanations"
    id = Column(Integer, primary_key=True)
    explanation_id = Column(String(100), unique=True, nullable=False, index=True)
    model_id = Column(String(100), nullable=False, index=True)
    explanation_type = Column(String(50), nullable=False)
    instance_id = Column(String(100))
    explanations = Column(Text)
    visualizations = Column(Text)
    confidence_score = Column(Float)
    compliance_status = Column(Text)
    metadata = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ModelRegistry(Base):
    """Model registry for explainability"""

    __tablename__ = "model_registry"
    id = Column(Integer, primary_key=True)
    model_id = Column(String(100), unique=True, nullable=False, index=True)
    model_name = Column(String(200), nullable=False)
    model_type = Column(String(50), nullable=False)
    model_version = Column(String(50))
    model_path = Column(String(500))
    feature_names = Column(Text)
    target_names = Column(Text)
    model_metadata = Column(Text)
    explainability_config = Column(Text)
    compliance_requirements = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class SHAPExplainer:
    """SHAP-based model explanations"""

    def __init__(
        self, model: object, model_type: ModelType, feature_names: List[str]
    ) -> None:
        self.model = model
        self.model_type = model_type
        self.feature_names = feature_names
        self.logger = structlog.get_logger(__name__)
        self.explainer = None
        self._initialize_explainer()

    def _initialize_explainer(self) -> object:
        """Initialize SHAP explainer based on model type"""
        try:
            if self.model_type in [
                ModelType.SKLEARN,
                ModelType.XGBOOST,
                ModelType.LIGHTGBM,
                ModelType.CATBOOST,
            ]:
                if hasattr(self.model, "predict_proba"):
                    self.explainer = shap.TreeExplainer(self.model)
                else:
                    self.explainer = shap.Explainer(self.model)
            elif self.model_type == ModelType.TENSORFLOW:
                if DEEP_LEARNING_AVAILABLE:
                    self.explainer = shap.DeepExplainer(
                        self.model, self._get_background_data()
                    )
                else:
                    raise ImportError(
                        "TensorFlow not available for deep learning explanations"
                    )
            elif self.model_type == ModelType.PYTORCH:
                if DEEP_LEARNING_AVAILABLE:
                    self.explainer = shap.DeepExplainer(
                        self.model, self._get_background_data()
                    )
                else:
                    raise ImportError(
                        "PyTorch not available for deep learning explanations"
                    )
            else:
                self.explainer = shap.Explainer(self.model)
            self.logger.info(f"Initialized SHAP explainer for {self.model_type.value}")
        except Exception as e:
            self.logger.error(f"Failed to initialize SHAP explainer: {str(e)}")
            raise

    def _get_background_data(self) -> np.ndarray:
        """Get background data for deep learning explainers"""
        return np.zeros((100, len(self.feature_names)))

    def explain_global(self, X: np.ndarray) -> Dict[str, Any]:
        """Generate global explanations"""
        try:
            shap_values = self.explainer.shap_values(X)
            if isinstance(shap_values, list):
                explanations: Dict[str, Any] = {}
                for i, class_shap_values in enumerate(shap_values):
                    explanations[f"class_{i}"] = {
                        "feature_importance": np.abs(class_shap_values)
                        .mean(axis=0)
                        .tolist(),
                        "feature_names": self.feature_names,
                    }
            else:
                explanations = {
                    "feature_importance": np.abs(shap_values).mean(axis=0).tolist(),
                    "feature_names": self.feature_names,
                }
            return explanations
        except Exception as e:
            self.logger.error(f"Global SHAP explanation failed: {str(e)}")
            return {}

    def explain_local(self, X: np.ndarray, instance_idx: int = 0) -> Dict[str, Any]:
        """Generate local explanations for a specific instance"""
        try:
            if instance_idx >= len(X):
                raise ValueError(f"Instance index {instance_idx} out of range")
            instance = X[instance_idx : instance_idx + 1]
            shap_values = self.explainer.shap_values(instance)
            if isinstance(shap_values, list):
                explanations: Dict[str, Any] = {}
                for i, class_shap_values in enumerate(shap_values):
                    explanations[f"class_{i}"] = {
                        "shap_values": class_shap_values[0].tolist(),
                        "feature_names": self.feature_names,
                        "feature_values": instance[0].tolist(),
                    }
            else:
                explanations = {
                    "shap_values": shap_values[0].tolist(),
                    "feature_names": self.feature_names,
                    "feature_values": instance[0].tolist(),
                }
            return explanations
        except Exception as e:
            self.logger.error(f"Local SHAP explanation failed: {str(e)}")
            return {}

    def generate_visualizations(self, X: np.ndarray, output_dir: str) -> Dict[str, str]:
        """Generate SHAP visualizations"""
        visualizations: Dict[str, Any] = {}
        try:
            os.makedirs(output_dir, exist_ok=True)
            shap_values = self.explainer.shap_values(X)
            plt.figure(figsize=(10, 8))
            if isinstance(shap_values, list):
                shap.summary_plot(
                    shap_values[0], X, feature_names=self.feature_names, show=False
                )
            else:
                shap.summary_plot(
                    shap_values, X, feature_names=self.feature_names, show=False
                )
            summary_path = os.path.join(output_dir, "shap_summary.png")
            plt.savefig(summary_path, dpi=300, bbox_inches="tight")
            plt.close()
            visualizations["summary_plot"] = summary_path
            plt.figure(figsize=(10, 6))
            if isinstance(shap_values, list):
                shap.summary_plot(
                    shap_values[0],
                    X,
                    feature_names=self.feature_names,
                    plot_type="bar",
                    show=False,
                )
            else:
                shap.summary_plot(
                    shap_values,
                    X,
                    feature_names=self.feature_names,
                    plot_type="bar",
                    show=False,
                )
            importance_path = os.path.join(output_dir, "shap_importance.png")
            plt.savefig(importance_path, dpi=300, bbox_inches="tight")
            plt.close()
            visualizations["importance_plot"] = importance_path
            if len(X) > 0:
                plt.figure(figsize=(10, 8))
                if isinstance(shap_values, list):
                    shap.waterfall_plot(
                        shap.Explanation(
                            values=shap_values[0][0],
                            base_values=self.explainer.expected_value[0],
                            data=X[0],
                            feature_names=self.feature_names,
                        ),
                        show=False,
                    )
                else:
                    shap.waterfall_plot(
                        shap.Explanation(
                            values=shap_values[0],
                            base_values=self.explainer.expected_value,
                            data=X[0],
                            feature_names=self.feature_names,
                        ),
                        show=False,
                    )
                waterfall_path = os.path.join(output_dir, "shap_waterfall.png")
                plt.savefig(waterfall_path, dpi=300, bbox_inches="tight")
                plt.close()
                visualizations["waterfall_plot"] = waterfall_path
            return visualizations
        except Exception as e:
            self.logger.error(f"SHAP visualization generation failed: {str(e)}")
            return {}


class LIMEExplainer:
    """LIME-based model explanations"""

    def __init__(
        self,
        model: object,
        model_type: ModelType,
        feature_names: List[str],
        training_data: np.ndarray,
        mode: str = "classification",
    ) -> None:
        self.model = model
        self.model_type = model_type
        self.feature_names = feature_names
        self.training_data = training_data
        self.mode = mode
        self.logger = structlog.get_logger(__name__)
        self.explainer = None
        self._initialize_explainer()

    def _initialize_explainer(self) -> object:
        """Initialize LIME explainer"""
        try:
            self.explainer = lime.lime_tabular.LimeTabularExplainer(
                self.training_data,
                feature_names=self.feature_names,
                mode=self.mode,
                discretize_continuous=True,
            )
            self.logger.info("Initialized LIME explainer")
        except Exception as e:
            self.logger.error(f"Failed to initialize LIME explainer: {str(e)}")
            raise

    def explain_local(
        self, instance: np.ndarray, num_features: int = 10
    ) -> Dict[str, Any]:
        """Generate local LIME explanation"""
        try:
            if hasattr(self.model, "predict_proba"):
                predict_fn = self.model.predict_proba
            else:
                predict_fn = self.model.predict
            explanation = self.explainer.explain_instance(
                instance, predict_fn, num_features=num_features
            )
            feature_importance = explanation.as_list()
            explanations = {
                "feature_importance": feature_importance,
                "score": explanation.score,
                "intercept": (
                    explanation.intercept[0] if hasattr(explanation, "intercept") else 0
                ),
                "prediction_local": (
                    explanation.local_pred[0]
                    if hasattr(explanation, "local_pred")
                    else None
                ),
                "right": explanation.right if hasattr(explanation, "right") else None,
            }
            return explanations
        except Exception as e:
            self.logger.error(f"Local LIME explanation failed: {str(e)}")
            return {}

    def generate_visualizations(
        self, instance: np.ndarray, output_dir: str, num_features: int = 10
    ) -> Dict[str, str]:
        """Generate LIME visualizations"""
        visualizations: Dict[str, Any] = {}
        try:
            os.makedirs(output_dir, exist_ok=True)
            if hasattr(self.model, "predict_proba"):
                predict_fn = self.model.predict_proba
            else:
                predict_fn = self.model.predict
            explanation = self.explainer.explain_instance(
                instance, predict_fn, num_features=num_features
            )
            html_path = os.path.join(output_dir, "lime_explanation.html")
            explanation.save_to_file(html_path)
            visualizations["html_explanation"] = html_path
            fig, ax = plt.subplots(figsize=(10, 6))
            feature_importance = explanation.as_list()
            features = [item[0] for item in feature_importance]
            values = [item[1] for item in feature_importance]
            colors = ["red" if v < 0 else "blue" for v in values]
            ax.barh(features, values, color=colors)
            ax.set_xlabel("Feature Importance")
            ax.set_title("LIME Local Explanation")
            ax.grid(True, alpha=0.3)
            plot_path = os.path.join(output_dir, "lime_plot.png")
            plt.savefig(plot_path, dpi=300, bbox_inches="tight")
            plt.close()
            visualizations["importance_plot"] = plot_path
            return visualizations
        except Exception as e:
            self.logger.error(f"LIME visualization generation failed: {str(e)}")
            return {}


class PermutationImportanceExplainer:
    """Permutation importance-based explanations"""

    def __init__(self, model: object, feature_names: List[str]) -> None:
        self.model = model
        self.feature_names = feature_names
        self.logger = structlog.get_logger(__name__)

    def explain_global(
        self,
        X: np.ndarray,
        y: np.ndarray,
        scoring: str = "accuracy",
        n_repeats: int = 10,
    ) -> Dict[str, Any]:
        """Generate global permutation importance"""
        try:
            perm_importance = permutation_importance(
                self.model, X, y, scoring=scoring, n_repeats=n_repeats, random_state=42
            )
            explanations = {
                "feature_importance": perm_importance.importances_mean.tolist(),
                "feature_importance_std": perm_importance.importances_std.tolist(),
                "feature_names": self.feature_names,
                "scoring_metric": scoring,
            }
            return explanations
        except Exception as e:
            self.logger.error(f"Permutation importance explanation failed: {str(e)}")
            return {}

    def generate_visualizations(
        self, X: np.ndarray, y: np.ndarray, output_dir: str, scoring: str = "accuracy"
    ) -> Dict[str, str]:
        """Generate permutation importance visualizations"""
        visualizations: Dict[str, Any] = {}
        try:
            os.makedirs(output_dir, exist_ok=True)
            perm_importance = permutation_importance(
                self.model, X, y, scoring=scoring, n_repeats=10, random_state=42
            )
            fig, ax = plt.subplots(figsize=(10, 8))
            indices = np.argsort(perm_importance.importances_mean)[::-1]
            ax.bar(
                range(len(indices)),
                perm_importance.importances_mean[indices],
                yerr=perm_importance.importances_std[indices],
            )
            ax.set_xlabel("Features")
            ax.set_ylabel(f"Permutation Importance ({scoring})")
            ax.set_title("Feature Importance via Permutation")
            ax.set_xticks(range(len(indices)))
            ax.set_xticklabels(
                [self.feature_names[i] for i in indices], rotation=45, ha="right"
            )
            ax.grid(True, alpha=0.3)
            plot_path = os.path.join(output_dir, "permutation_importance.png")
            plt.savefig(plot_path, dpi=300, bbox_inches="tight")
            plt.close()
            visualizations["importance_plot"] = plot_path
            return visualizations
        except Exception as e:
            self.logger.error(f"Permutation importance visualization failed: {str(e)}")
            return {}


class PartialDependenceExplainer:
    """Partial dependence plot explanations"""

    def __init__(self, model: object, feature_names: List[str]) -> None:
        self.model = model
        self.feature_names = feature_names
        self.logger = structlog.get_logger(__name__)

    def explain_feature_effects(
        self, X: np.ndarray, features: List[Union[int, str]]
    ) -> Dict[str, Any]:
        """Generate partial dependence explanations"""
        try:
            explanations: Dict[str, Any] = {}
            for feature in features:
                if isinstance(feature, str):
                    feature_idx = self.feature_names.index(feature)
                else:
                    feature_idx = feature
                pdp_result = partial_dependence(
                    self.model, X, [feature_idx], kind="average"
                )
                explanations[self.feature_names[feature_idx]] = {
                    "values": pdp_result["values"][0].tolist(),
                    "average": pdp_result["average"][0].tolist(),
                    "feature_name": self.feature_names[feature_idx],
                }
            return explanations
        except Exception as e:
            self.logger.error(f"Partial dependence explanation failed: {str(e)}")
            return {}

    def generate_visualizations(
        self, X: np.ndarray, features: List[Union[int, str]], output_dir: str
    ) -> Dict[str, str]:
        """Generate partial dependence visualizations"""
        visualizations: Dict[str, Any] = {}
        try:
            os.makedirs(output_dir, exist_ok=True)
            for feature in features:
                if isinstance(feature, str):
                    feature_idx = self.feature_names.index(feature)
                    feature_name = feature
                else:
                    feature_idx = feature
                    feature_name = self.feature_names[feature_idx]
                pdp_result = partial_dependence(
                    self.model, X, [feature_idx], kind="average"
                )
                fig, ax = plt.subplots(figsize=(10, 6))
                ax.plot(pdp_result["values"][0], pdp_result["average"][0], linewidth=2)
                ax.set_xlabel(feature_name)
                ax.set_ylabel("Partial Dependence")
                ax.set_title(f"Partial Dependence Plot - {feature_name}")
                ax.grid(True, alpha=0.3)
                plot_path = os.path.join(output_dir, f"pdp_{feature_name}.png")
                plt.savefig(plot_path, dpi=300, bbox_inches="tight")
                plt.close()
                visualizations[f"pdp_{feature_name}"] = plot_path
            return visualizations
        except Exception as e:
            self.logger.error(f"Partial dependence visualization failed: {str(e)}")
            return {}


class ComplianceChecker:
    """Regulatory compliance checker for AI explanations"""

    def __init__(self) -> None:
        self.logger = structlog.get_logger(__name__)
        self.compliance_rules = self._load_compliance_rules()

    def _load_compliance_rules(self) -> Dict[ComplianceStandard, Dict[str, Any]]:
        """Load compliance rules for different standards"""
        return {
            ComplianceStandard.GDPR: {
                "requires_explanation": True,
                "explanation_depth": "detailed",
                "right_to_explanation": True,
                "automated_decision_making": True,
                "data_subject_rights": True,
            },
            ComplianceStandard.FCRA: {
                "requires_explanation": True,
                "adverse_action_notice": True,
                "explanation_depth": "standard",
                "credit_decision_factors": True,
            },
            ComplianceStandard.ECOA: {
                "requires_explanation": True,
                "prohibited_factors": [
                    "race",
                    "color",
                    "religion",
                    "national_origin",
                    "sex",
                    "marital_status",
                    "age",
                ],
                "adverse_action_notice": True,
                "explanation_depth": "standard",
            },
            ComplianceStandard.SOX: {
                "requires_audit_trail": True,
                "model_documentation": True,
                "explanation_depth": "detailed",
                "financial_reporting": True,
            },
            ComplianceStandard.BASEL_III: {
                "requires_explanation": True,
                "risk_model_validation": True,
                "explanation_depth": "detailed",
                "stress_testing": True,
            },
            ComplianceStandard.MiFID_II: {
                "requires_explanation": True,
                "best_execution": True,
                "explanation_depth": "standard",
                "client_categorization": True,
            },
        }

    def check_compliance(
        self, explanation_result: ExplanationResult, standards: List[ComplianceStandard]
    ) -> Dict[ComplianceStandard, bool]:
        """Check compliance against specified standards"""
        compliance_status: Dict[str, Any] = {}
        for standard in standards:
            try:
                compliance_status[standard] = self._check_standard_compliance(
                    explanation_result, standard
                )
            except Exception as e:
                self.logger.error(
                    f"Compliance check failed for {standard.value}: {str(e)}"
                )
                compliance_status[standard] = False
        return compliance_status

    def _check_standard_compliance(
        self, explanation_result: ExplanationResult, standard: ComplianceStandard
    ) -> bool:
        """Check compliance for a specific standard"""
        rules = self.compliance_rules.get(standard, {})
        if rules.get("requires_explanation", False):
            if not explanation_result.explanations:
                return False
        required_depth = rules.get("explanation_depth", "standard")
        if required_depth == "detailed":
            required_components = [
                "feature_importance",
                "local_explanations",
                "global_explanations",
            ]
            if not all(
                (
                    comp in explanation_result.explanations
                    for comp in required_components
                )
            ):
                return False
        if standard == ComplianceStandard.ECOA:
            prohibited_factors = rules.get("prohibited_factors", [])
            feature_importance = explanation_result.explanations.get(
                "feature_importance", {}
            )
            for factor in prohibited_factors:
                if factor in feature_importance:
                    importance = feature_importance.get(factor, 0)
                    if abs(importance) > 0.1:
                        return False
        if standard == ComplianceStandard.SOX:
            if not explanation_result.metadata.get("audit_trail"):
                return False
        return True

    def generate_compliance_report(
        self, explanation_result: ExplanationResult, standards: List[ComplianceStandard]
    ) -> Dict[str, Any]:
        """Generate compliance report"""
        compliance_status = self.check_compliance(explanation_result, standards)
        report = {
            "explanation_id": explanation_result.explanation_id,
            "model_id": explanation_result.model_id,
            "timestamp": explanation_result.timestamp.isoformat(),
            "compliance_standards": [s.value for s in standards],
            "compliance_status": {
                s.value: status for s, status in compliance_status.items()
            },
            "overall_compliant": all(compliance_status.values()),
            "recommendations": self._generate_recommendations(compliance_status),
            "audit_information": {
                "explanation_type": explanation_result.explanation_type.value,
                "confidence_score": explanation_result.confidence_score,
                "metadata": explanation_result.metadata,
            },
        }
        return report

    def _generate_recommendations(
        self, compliance_status: Dict[ComplianceStandard, bool]
    ) -> List[str]:
        """Generate recommendations for improving compliance"""
        recommendations: List[Any] = []
        for standard, is_compliant in compliance_status.items():
            if not is_compliant:
                if standard == ComplianceStandard.GDPR:
                    recommendations.append(
                        "Provide more detailed explanations to meet GDPR requirements"
                    )
                    recommendations.append("Ensure right to explanation is implemented")
                elif standard == ComplianceStandard.FCRA:
                    recommendations.append("Include adverse action notice requirements")
                    recommendations.append("Provide specific credit decision factors")
                elif standard == ComplianceStandard.ECOA:
                    recommendations.append(
                        "Remove or reduce influence of prohibited factors"
                    )
                    recommendations.append("Ensure fair lending practices")
                elif standard == ComplianceStandard.SOX:
                    recommendations.append("Implement comprehensive audit trail")
                    recommendations.append("Model documentation")
        return recommendations


class ExplainableAIEngine:
    """Main explainable AI engine"""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.logger = structlog.get_logger(__name__)
        db_url = config.get("database_url", "sqlite:///explainable_ai.db")
        self.db_engine = create_engine(db_url)
        Session = sessionmaker(bind=self.db_engine)
        self.db_session = Session()
        Base.metadata.create_all(bind=self.db_engine)
        redis_url = config.get("redis_url", "redis://localhost:6379/0")
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.compliance_checker = ComplianceChecker()
        self.model_registry = {}
        self.output_dir = config.get("output_dir", "/tmp/explainable_ai")
        os.makedirs(self.output_dir, exist_ok=True)

    def register_model(
        self,
        model_id: str,
        model: object,
        model_type: ModelType,
        feature_names: List[str],
        target_names: Optional[List[str]] = None,
        training_data: np.ndarray = None,
        compliance_requirements: Optional[List[ComplianceStandard]] = None,
    ) -> bool:
        """Register a model for explainability"""
        try:
            model_info = {
                "model": model,
                "model_type": model_type,
                "feature_names": feature_names,
                "target_names": target_names or [],
                "training_data": training_data,
                "compliance_requirements": compliance_requirements or [],
            }
            self.model_registry[model_id] = model_info
            model_record = ModelRegistry(
                model_id=model_id,
                model_name=f"Model_{model_id}",
                model_type=model_type.value,
                feature_names=json.dumps(feature_names),
                target_names=json.dumps(target_names or []),
                compliance_requirements=json.dumps(
                    [req.value for req in compliance_requirements or []]
                ),
            )
            self.db_session.add(model_record)
            self.db_session.commit()
            self.logger.info(f"Registered model: {model_id}")
            return True
        except Exception as e:
            self.logger.error(f"Model registration failed: {str(e)}")
            self.db_session.rollback()
            return False

    def explain_model(self, request: ExplanationRequest) -> ExplanationResult:
        """Generate model explanation"""
        try:
            explanation_id = str(uuid.uuid4())
            if request.model_id not in self.model_registry:
                raise ValueError(f"Model {request.model_id} not registered")
            model_info = self.model_registry[request.model_id]
            model = model_info["model"]
            model_type = model_info["model_type"]
            feature_names = model_info["feature_names"]
            training_data = model_info["training_data"]
            explanations: Dict[str, Any] = {}
            visualizations: Dict[str, Any] = {}
            if request.explanation_type == ExplanationType.SHAP_VALUES:
                explanations, visualizations = self._generate_shap_explanations(
                    model, model_type, feature_names, request, explanation_id
                )
            elif request.explanation_type == ExplanationType.LIME_EXPLANATION:
                explanations, visualizations = self._generate_lime_explanations(
                    model,
                    model_type,
                    feature_names,
                    training_data,
                    request,
                    explanation_id,
                )
            elif request.explanation_type == ExplanationType.FEATURE_IMPORTANCE:
                explanations, visualizations = (
                    self._generate_feature_importance_explanations(
                        model, feature_names, request, explanation_id
                    )
                )
            elif request.explanation_type == ExplanationType.PARTIAL_DEPENDENCE:
                explanations, visualizations = (
                    self._generate_partial_dependence_explanations(
                        model, feature_names, request, explanation_id
                    )
                )
            else:
                explanations, visualizations = (
                    self._generate_comprehensive_explanations(
                        model,
                        model_type,
                        feature_names,
                        training_data,
                        request,
                        explanation_id,
                    )
                )
            confidence_score = self._calculate_confidence_score(explanations)
            compliance_standards = (
                request.compliance_standards or model_info["compliance_requirements"]
            )
            result = ExplanationResult(
                explanation_id=explanation_id,
                model_id=request.model_id,
                explanation_type=request.explanation_type,
                timestamp=datetime.utcnow(),
                explanations=explanations,
                visualizations=visualizations,
                confidence_score=confidence_score,
                compliance_status={},
                metadata={
                    "explanation_depth": request.explanation_depth,
                    "feature_names": feature_names,
                    "model_type": model_type.value,
                },
            )
            if compliance_standards:
                result.compliance_status = self.compliance_checker.check_compliance(
                    result, compliance_standards
                )
            self._store_explanation(result)
            return result
        except Exception as e:
            self.logger.error(f"Model explanation failed: {str(e)}")
            raise

    def _generate_shap_explanations(
        self,
        model: object,
        model_type: ModelType,
        feature_names: List[str],
        request: ExplanationRequest,
        explanation_id: str,
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """Generate SHAP explanations"""
        explainer = SHAPExplainer(model, model_type, feature_names)
        explanations: Dict[str, Any] = {}
        visualizations: Dict[str, Any] = {}
        if request.instance_data:
            X = np.array([list(request.instance_data.values())])
            explanations = explainer.explain_local(X, 0)
            viz_dir = os.path.join(self.output_dir, explanation_id, "shap")
            visualizations = explainer.generate_visualizations(X, viz_dir)
        return (explanations, visualizations)

    def _generate_lime_explanations(
        self,
        model: object,
        model_type: ModelType,
        feature_names: List[str],
        training_data: np.ndarray,
        request: ExplanationRequest,
        explanation_id: str,
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """Generate LIME explanations"""
        if training_data is None:
            raise ValueError("Training data required for LIME explanations")
        explainer = LIMEExplainer(model, model_type, feature_names, training_data)
        explanations: Dict[str, Any] = {}
        visualizations: Dict[str, Any] = {}
        if request.instance_data:
            instance = np.array(list(request.instance_data.values()))
            explanations = explainer.explain_local(instance)
            viz_dir = os.path.join(self.output_dir, explanation_id, "lime")
            visualizations = explainer.generate_visualizations(instance, viz_dir)
        return (explanations, visualizations)

    def _generate_feature_importance_explanations(
        self,
        model: object,
        feature_names: List[str],
        request: ExplanationRequest,
        explanation_id: str,
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """Generate feature importance explanations"""
        explanations: Dict[str, Any] = {}
        visualizations: Dict[str, Any] = {}
        if hasattr(model, "feature_importances_"):
            explanations["feature_importance"] = {
                "importances": model.feature_importances_.tolist(),
                "feature_names": feature_names,
            }
        if explanations:
            viz_dir = os.path.join(
                self.output_dir, explanation_id, "feature_importance"
            )
            os.makedirs(viz_dir, exist_ok=True)
            fig, ax = plt.subplots(figsize=(10, 8))
            importances = explanations["feature_importance"]["importances"]
            indices = np.argsort(importances)[::-1]
            ax.bar(range(len(indices)), [importances[i] for i in indices])
            ax.set_xlabel("Features")
            ax.set_ylabel("Importance")
            ax.set_title("Feature Importance")
            ax.set_xticks(range(len(indices)))
            ax.set_xticklabels(
                [feature_names[i] for i in indices], rotation=45, ha="right"
            )
            ax.grid(True, alpha=0.3)
            plot_path = os.path.join(viz_dir, "feature_importance.png")
            plt.savefig(plot_path, dpi=300, bbox_inches="tight")
            plt.close()
            visualizations["feature_importance_plot"] = plot_path
        return (explanations, visualizations)

    def _generate_partial_dependence_explanations(
        self,
        model: object,
        feature_names: List[str],
        request: ExplanationRequest,
        explanation_id: str,
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """Generate partial dependence explanations"""
        explanations: Dict[str, Any] = {}
        visualizations: Dict[str, Any] = {}
        if request.instance_data:
            X = np.array([list(request.instance_data.values())])
            explainer = PartialDependenceExplainer(model, feature_names)
            top_features = feature_names[:5]
            explanations = explainer.explain_feature_effects(X, top_features)
            viz_dir = os.path.join(
                self.output_dir, explanation_id, "partial_dependence"
            )
            visualizations = explainer.generate_visualizations(X, top_features, viz_dir)
        return (explanations, visualizations)

    def _generate_comprehensive_explanations(
        self,
        model: object,
        model_type: ModelType,
        feature_names: List[str],
        training_data: np.ndarray,
        request: ExplanationRequest,
        explanation_id: str,
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """Generate comprehensive explanations using multiple methods"""
        explanations: Dict[str, Any] = {}
        visualizations: Dict[str, Any] = {}
        try:
            shap_explainer = SHAPExplainer(model, model_type, feature_names)
            if request.instance_data:
                X = np.array([list(request.instance_data.values())])
                shap_local = shap_explainer.explain_local(X, 0)
                explanations["shap_local"] = shap_local
                shap_global = shap_explainer.explain_global(X)
                explanations["shap_global"] = shap_global
                viz_dir = os.path.join(
                    self.output_dir, explanation_id, "comprehensive", "shap"
                )
                shap_viz = shap_explainer.generate_visualizations(X, viz_dir)
                visualizations.update(shap_viz)
            if hasattr(model, "feature_importances_"):
                explanations["feature_importance"] = {
                    "importances": model.feature_importances_.tolist(),
                    "feature_names": feature_names,
                }
            if training_data is not None and request.instance_data:
                lime_explainer = LIMEExplainer(
                    model, model_type, feature_names, training_data
                )
                instance = np.array(list(request.instance_data.values()))
                lime_local = lime_explainer.explain_local(instance)
                explanations["lime_local"] = lime_local
                viz_dir = os.path.join(
                    self.output_dir, explanation_id, "comprehensive", "lime"
                )
                lime_viz = lime_explainer.generate_visualizations(instance, viz_dir)
                visualizations.update(lime_viz)
        except Exception as e:
            self.logger.error(f"Comprehensive explanation generation failed: {str(e)}")
        return (explanations, visualizations)

    def _calculate_confidence_score(self, explanations: Dict[str, Any]) -> float:
        """Calculate confidence score for explanations"""
        try:
            score = 0.0
            if "shap_local" in explanations:
                score += 0.3
            if "shap_global" in explanations:
                score += 0.3
            if "lime_local" in explanations:
                score += 0.2
            if "feature_importance" in explanations:
                score += 0.2
            return min(score, 1.0)
        except Exception:
            return 0.5

    def _store_explanation(self, result: ExplanationResult) -> object:
        """Store explanation result in database"""
        try:
            explanation_record = ModelExplanation(
                explanation_id=result.explanation_id,
                model_id=result.model_id,
                explanation_type=result.explanation_type.value,
                explanations=json.dumps(result.explanations),
                visualizations=json.dumps(result.visualizations),
                confidence_score=result.confidence_score,
                compliance_status=json.dumps(
                    {k.value: v for k, v in result.compliance_status.items()}
                ),
                metadata=json.dumps(result.metadata),
            )
            self.db_session.add(explanation_record)
            self.db_session.commit()
        except Exception as e:
            self.logger.error(f"Explanation storage failed: {str(e)}")
            self.db_session.rollback()

    def get_explanation(self, explanation_id: str) -> Optional[ExplanationResult]:
        """Retrieve stored explanation"""
        try:
            record = (
                self.db_session.query(ModelExplanation)
                .filter_by(explanation_id=explanation_id)
                .first()
            )
            if record:
                return ExplanationResult(
                    explanation_id=record.explanation_id,
                    model_id=record.model_id,
                    explanation_type=ExplanationType(record.explanation_type),
                    timestamp=record.created_at,
                    explanations=json.loads(record.explanations),
                    visualizations=json.loads(record.visualizations),
                    confidence_score=record.confidence_score,
                    compliance_status={
                        ComplianceStandard(k): v
                        for k, v in json.loads(record.compliance_status).items()
                    },
                    metadata=json.loads(record.metadata),
                )
            return None
        except Exception as e:
            self.logger.error(f"Explanation retrieval failed: {str(e)}")
            return None

    def generate_compliance_report(
        self, explanation_id: str
    ) -> Optional[Dict[str, Any]]:
        """Generate compliance report for explanation"""
        try:
            explanation = self.get_explanation(explanation_id)
            if explanation:
                standards = list(explanation.compliance_status.keys())
                return self.compliance_checker.generate_compliance_report(
                    explanation, standards
                )
            return None
        except Exception as e:
            self.logger.error(f"Compliance report generation failed: {str(e)}")
            return None


def create_explainable_ai_engine(config: Dict[str, Any]) -> ExplainableAIEngine:
    """Factory function to create explainable AI engine"""
    return ExplainableAIEngine(config)


if __name__ == "__main__":
    import structlog
    from sklearn.datasets import make_classification
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    config = {
        "database_url": "sqlite:///explainable_ai.db",
        "redis_url": "redis://localhost:6379/0",
        "output_dir": "/tmp/explainable_ai",
    }
    engine = create_explainable_ai_engine(config)
    X, y = make_classification(
        n_samples=1000, n_features=10, n_informative=5, random_state=42
    )
    feature_names = [f"feature_{i}" for i in range(X.shape[1])]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    engine.register_model(
        model_id="credit_risk_model",
        model=model,
        model_type=ModelType.SKLEARN,
        feature_names=feature_names,
        target_names=["low_risk", "high_risk"],
        training_data=X_train,
        compliance_requirements=[ComplianceStandard.FCRA, ComplianceStandard.ECOA],
    )
    instance_data = {f"feature_{i}": X_test[0][i] for i in range(len(feature_names))}
    request = ExplanationRequest(
        model_id="credit_risk_model",
        explanation_type=ExplanationType.GLOBAL,
        instance_data=instance_data,
        compliance_standards=[ComplianceStandard.FCRA, ComplianceStandard.ECOA],
        explanation_depth="detailed",
        include_visualizations=True,
    )
    result = engine.explain_model(request)
    logger.info(f"Explanation ID: {result.explanation_id}")
    logger.info(f"Confidence Score: {result.confidence_score}")
    logger.info(f"Compliance Status: {result.compliance_status}")
    logger.info(f"Explanations: {json.dumps(result.explanations, indent=2)}")
    compliance_report = engine.generate_compliance_report(result.explanation_id)
    logger.info(f"Compliance Report: {json.dumps(compliance_report, indent=2)}")
