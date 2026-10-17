from typing import Any, Dict, List, Sequence

import numpy as np
from ai_models.core.errors import InsufficientDataError
from ai_models.credit.features import FEATURES, normalize_inputs, transform_vector
from ai_models.credit.model import CreditModel

MODERATE = 0.25
SIGNIFICANT = 0.5
MIN_RECORDS = 30


def psi(reference_quantiles: Sequence[float], values: np.ndarray) -> float:
    edges = np.unique(np.asarray(reference_quantiles, dtype=float))
    if len(edges) < 3 or len(values) == 0:
        return 0.0
    bins = np.searchsorted(edges[1:-1], values, side="right")
    counts = np.bincount(bins, minlength=len(edges) - 1).astype(float)
    total = counts.sum()
    actual = np.clip(counts / total, 1e-4, None)
    expected = np.full(len(actual), 1.0 / len(actual))
    raw = float(np.sum((actual - expected) * np.log(actual / expected)))
    return float(max(0.0, raw - (len(actual) - 1) / total))


def credit_input_drift(
    model: CreditModel, recent_inputs: Sequence[Dict[str, Any]]
) -> Dict[str, Any]:
    rows = []
    for item in recent_inputs:
        try:
            values, imputed = normalize_inputs(item)
        except Exception:
            continue
        if len(imputed) <= len(FEATURES) // 2:
            rows.append(transform_vector(values))
    if len(rows) < MIN_RECORDS:
        raise InsufficientDataError(
            f"At least {MIN_RECORDS} recent scoring requests are required to assess drift",
            {"available": len(rows)},
        )
    z = (np.array(rows) - np.array(model.mean)) / np.array(model.scale)
    features: List[Dict[str, Any]] = []
    for i, spec in enumerate(FEATURES):
        value = psi(model.reference_quantiles[spec.name], z[:, i])
        status = (
            "significant"
            if value >= SIGNIFICANT
            else "moderate" if value >= MODERATE else "stable"
        )
        features.append(
            {"feature": spec.name, "psi": round(value, 4), "status": status}
        )
    features.sort(key=lambda f: f["psi"], reverse=True)
    worst = features[0]["psi"]
    mean = float(np.mean([f["psi"] for f in features]))
    status = (
        "significant"
        if worst >= SIGNIFICANT
        else "moderate" if worst >= MODERATE else "stable"
    )
    return {
        "status": status,
        "max_psi": worst,
        "mean_psi": round(mean, 4),
        "records": len(rows),
        "features": features,
    }
