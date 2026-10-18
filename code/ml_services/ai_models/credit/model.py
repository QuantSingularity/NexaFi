import json
import math
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from ai_models.core.errors import InsufficientDataError, NotFoundError, ValidationError
from ai_models.credit.features import (
    FEATURE_NAMES,
    FEATURES,
    normalize_inputs,
    transform_vector,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split

BASE_SCORE = 650.0
BASE_ODDS = 10.0
POINTS_TO_DOUBLE_ODDS = 50.0
MIN_RECORDS = 200
MIN_CLASS = 20

_TRUE_COEFFICIENTS = np.array([-0.18, -0.16, -0.05, -0.60, 0.38, 0.20, 0.28, -0.30])
_TRUE_INTERCEPT = -2.2


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(min(value, 40.0), -40.0)))


def synthetic_population(n: int = 6000, seed: int = 7) -> tuple:
    rng = np.random.default_rng(seed)
    raw = {
        "annual_revenue": rng.lognormal(12.3, 1.1, n),
        "business_age_months": rng.gamma(2.2, 18.0, n),
        "employee_count": rng.lognormal(1.6, 1.0, n),
        "payment_history_score": np.clip(rng.normal(72, 16, n), 0, 100),
        "credit_utilization": np.clip(rng.beta(2.0, 3.2, n), 0, 1.5),
        "num_credit_inquiries": rng.poisson(2.2, n).astype(float),
        "debt_to_equity": rng.lognormal(0.1, 0.8, n),
        "cash_flow_stability": np.clip(rng.beta(4.0, 2.6, n), 0, 1),
    }
    X = np.array(
        [
            transform_vector({k: float(raw[k][i]) for k in FEATURE_NAMES})
            for i in range(n)
        ]
    )
    z = (X - X.mean(axis=0)) / X.std(axis=0)
    logit_default = _TRUE_INTERCEPT + z @ _TRUE_COEFFICIENTS
    probability = 1.0 / (1.0 + np.exp(-logit_default))
    y = (rng.random(n) < probability).astype(int)
    return X, y


@dataclass
class CreditModel:
    version: int
    trained_at: str
    training_data: str
    samples: int
    mean: List[float]
    scale: List[float]
    coefficients: List[float]
    intercept: float
    metrics: Dict[str, float]
    reference_quantiles: Dict[str, List[float]] = field(default_factory=dict)

    @property
    def factor(self) -> float:
        return POINTS_TO_DOUBLE_ODDS / math.log(2.0)

    @property
    def offset(self) -> float:
        return BASE_SCORE - self.factor * math.log(BASE_ODDS)

    def standardize(self, vector: Sequence[float]) -> np.ndarray:
        return (np.asarray(vector, dtype=float) - np.asarray(self.mean)) / np.asarray(
            self.scale
        )

    def logit_default(self, z: np.ndarray) -> float:
        return float(self.intercept + np.dot(self.coefficients, z))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CreditModel":
        return cls(**payload)


def _ks(y_true: np.ndarray, p: np.ndarray) -> float:
    order = np.argsort(p)
    y = y_true[order]
    bad = np.cumsum(y) / max(1, y.sum())
    good = np.cumsum(1 - y) / max(1, (1 - y).sum())
    return float(np.max(np.abs(bad - good)))


def train(
    X: np.ndarray, y: np.ndarray, version: int, training_data: str, seed: int = 11
) -> CreditModel:
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=int)
    if len(X) < MIN_RECORDS:
        raise InsufficientDataError(
            f"At least {MIN_RECORDS} labelled records are required",
            {"records": int(len(X))},
        )
    if min(int(y.sum()), int((1 - y).sum())) < MIN_CLASS:
        raise InsufficientDataError(
            f"At least {MIN_CLASS} defaults and {MIN_CLASS} repayments are required",
            {"defaults": int(y.sum()), "repaid": int((1 - y).sum())},
        )
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=seed, stratify=y
    )
    mean = X_train.mean(axis=0)
    scale = np.where(X_train.std(axis=0) < 1e-9, 1.0, X_train.std(axis=0))
    classifier = LogisticRegression(C=1.0, max_iter=500)
    classifier.fit((X_train - mean) / scale, y_train)
    probability = classifier.predict_proba((X_test - mean) / scale)[:, 1]
    metrics = {
        "auc": float(roc_auc_score(y_test, probability)),
        "ks": _ks(y_test, probability),
        "brier": float(brier_score_loss(y_test, probability)),
        "holdout_default_rate": float(y_test.mean()),
        "holdout_samples": int(len(y_test)),
    }
    z_all = (X - mean) / scale
    quantiles = {
        name: np.quantile(z_all[:, i], np.linspace(0, 1, 11)).tolist()
        for i, name in enumerate(FEATURE_NAMES)
    }
    return CreditModel(
        version=version,
        trained_at=datetime.now(timezone.utc).isoformat(),
        training_data=training_data,
        samples=int(len(X)),
        mean=mean.tolist(),
        scale=scale.tolist(),
        coefficients=classifier.coef_[0].tolist(),
        intercept=float(classifier.intercept_[0]),
        metrics=metrics,
        reference_quantiles=quantiles,
    )


def bootstrap_model() -> CreditModel:
    X, y = synthetic_population()
    return train(X, y, 1, "synthetic_bootstrap")


def records_to_arrays(records: Sequence[Dict[str, Any]]) -> tuple:
    if not isinstance(records, (list, tuple)):
        raise ValidationError("records must be a list")
    X, y = [], []
    for i, record in enumerate(records):
        if not isinstance(record, dict) or "defaulted" not in record:
            raise ValidationError(f"records[{i}] requires a defaulted flag")
        values, imputed = normalize_inputs(record)
        if len(imputed) > len(FEATURES) // 2:
            continue
        X.append(transform_vector(values))
        y.append(1 if record["defaulted"] in (True, 1, "1", "true", "True") else 0)
    return np.array(X), np.array(y)


class CreditModelStore:
    def __init__(self, directory: Optional[str] = None) -> None:
        self.directory = directory
        self._current: Optional[CreditModel] = None
        if directory:
            os.makedirs(directory, exist_ok=True)

    def _path(self, version: int) -> str:
        return os.path.join(self.directory or "", f"credit_model_v{version}.json")

    def versions(self) -> List[int]:
        if not self.directory:
            return [self._current.version] if self._current else []
        found = []
        for name in os.listdir(self.directory):
            if name.startswith("credit_model_v") and name.endswith(".json"):
                try:
                    found.append(int(name[len("credit_model_v") : -len(".json")]))
                except ValueError:
                    continue
        return sorted(found)

    def save(self, model: CreditModel) -> None:
        self._current = model
        if self.directory:
            temp = f"{self._path(model.version)}.{uuid.uuid4().hex}.tmp"
            with open(temp, "w") as handle:
                json.dump(model.to_dict(), handle)
            os.replace(temp, self._path(model.version))

    def load(self, version: int) -> CreditModel:
        if not self.directory or not os.path.exists(self._path(version)):
            raise NotFoundError(f"Credit model version not found: {version}")
        with open(self._path(version)) as handle:
            return CreditModel.from_dict(json.load(handle))

    def current(self) -> CreditModel:
        if self._current is not None:
            return self._current
        versions = self.versions()
        if versions:
            self._current = self.load(versions[-1])
        else:
            self._current = bootstrap_model()
            self.save(self._current)
        return self._current

    def retrain(self, records: Sequence[Dict[str, Any]]) -> CreditModel:
        X, y = records_to_arrays(records)
        version = max(self.versions() or [0]) + 1
        model = train(X, y, version, f"observed_outcomes (n={len(X)})")
        self.save(model)
        return model
