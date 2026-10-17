from typing import Any, Dict, List, Optional

import numpy as np
from ai_models.credit.features import FEATURES, normalize_inputs, transform_vector
from ai_models.credit.model import (
    BASE_ODDS,
    BASE_SCORE,
    POINTS_TO_DOUBLE_ODDS,
    CreditModel,
    CreditModelStore,
    _sigmoid,
)

MIN_SCORE = 300
MAX_SCORE = 850
ADVICE_THRESHOLD = 6.0


def risk_category(score: float) -> str:
    if score >= 760:
        return "excellent"
    if score >= 700:
        return "good"
    if score >= 640:
        return "fair"
    if score >= 580:
        return "poor"
    return "very_poor"


def risk_level(score: float) -> str:
    if score >= 700:
        return "low"
    if score >= 640:
        return "medium"
    return "high"


def decision_for(score: float, default_probability: float) -> str:
    if score >= 680 and default_probability < 0.08:
        return "approve"
    if score >= 600:
        return "manual_review"
    return "decline"


class CreditScorer:
    def __init__(self, store: Optional[CreditModelStore] = None) -> None:
        self.store = store or CreditModelStore()

    @property
    def model(self) -> CreditModel:
        return self.store.current()

    def score(self, business_data: Any) -> Dict[str, Any]:
        model = self.model
        values, imputed = normalize_inputs(business_data)
        z = model.standardize(transform_vector(values))
        default_probability = _sigmoid(model.logit_default(z))
        raw_score = model.offset + model.factor * (-model.logit_default(z))
        score = float(np.clip(raw_score, MIN_SCORE, MAX_SCORE))
        baseline = model.offset + model.factor * (-model.intercept)
        details: List[Dict[str, Any]] = []
        for spec, coefficient, z_value in zip(FEATURES, model.coefficients, z):
            points = -model.factor * coefficient * float(z_value)
            details.append(
                {
                    "feature": spec.name,
                    "label": spec.label,
                    "value": values[spec.name],
                    "points": round(points, 1),
                    "direction": (
                        "increases_score"
                        if points > 0
                        else "decreases_score" if points < 0 else "neutral"
                    ),
                    "imputed": spec.name in imputed,
                }
            )
        details.sort(key=lambda item: abs(item["points"]), reverse=True)
        advice = [
            spec.advice
            for spec in FEATURES
            for item in details
            if item["feature"] == spec.name
            and item["points"] <= -ADVICE_THRESHOLD
            and not item["imputed"]
        ]
        completeness = 1.0 - len(imputed) / len(FEATURES)
        return {
            "credit_score": int(round(score)),
            "risk_category": risk_category(score),
            "risk_level": risk_level(score),
            "probability_of_default": round(default_probability, 4),
            "probability_of_repayment": round(1.0 - default_probability, 4),
            "approval_probability": round(1.0 - default_probability, 4),
            "decision": decision_for(score, default_probability),
            "factors": {item["feature"]: item["points"] for item in details},
            "factor_details": details,
            "baseline_score": round(baseline, 1),
            "recommendations": advice,
            "imputed_features": imputed,
            "data_completeness": round(completeness, 2),
            "model_version": str(model.version),
            "model": {
                "version": model.version,
                "training_data": model.training_data,
                "auc": round(model.metrics["auc"], 4),
            },
        }

    def model_card(self) -> Dict[str, Any]:
        model = self.model
        return {
            "name": "credit_scorecard",
            "type": "logistic_regression_scorecard",
            "version": model.version,
            "trained_at": model.trained_at,
            "training_data": model.training_data,
            "samples": model.samples,
            "metrics": model.metrics,
            "features": [spec.name for spec in FEATURES],
            "score_range": [MIN_SCORE, MAX_SCORE],
            "scaling": {
                "base_score": BASE_SCORE,
                "base_odds": BASE_ODDS,
                "points_to_double_odds": POINTS_TO_DOUBLE_ODDS,
            },
            "warning": (
                "Trained on a synthetic bootstrap population. Retrain on observed loan outcomes before relying on scores for lending decisions."
                if model.training_data == "synthetic_bootstrap"
                else None
            ),
        }
