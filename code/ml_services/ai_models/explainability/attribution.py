from typing import Any, Callable, Dict, List, Sequence

import numpy as np


def permutation_importance(
    predict: Callable[[np.ndarray], np.ndarray],
    X: np.ndarray,
    y: np.ndarray,
    feature_names: Sequence[str],
    loss: Callable[[np.ndarray, np.ndarray], float],
    repeats: int = 5,
    seed: int = 7,
) -> List[Dict[str, Any]]:
    rng = np.random.default_rng(seed)
    baseline = loss(y, predict(X))
    results = []
    for column, name in enumerate(feature_names):
        deltas = []
        for _ in range(repeats):
            shuffled = X.copy()
            shuffled[:, column] = shuffled[rng.permutation(len(X)), column]
            deltas.append(loss(y, predict(shuffled)) - baseline)
        results.append(
            {
                "feature": name,
                "importance": float(np.mean(deltas)),
                "std": float(np.std(deltas)),
            }
        )
    results.sort(key=lambda item: item["importance"], reverse=True)
    return results


def occlusion_contributions(
    predict: Callable[[np.ndarray], float],
    row: np.ndarray,
    baseline: np.ndarray,
    feature_names: Sequence[str],
) -> List[Dict[str, Any]]:
    reference = predict(baseline)
    full = predict(row)
    out = []
    for i, name in enumerate(feature_names):
        probe = row.copy()
        probe[i] = baseline[i]
        out.append(
            {
                "feature": name,
                "contribution": float(full - predict(probe)),
                "value": float(row[i]),
            }
        )
    out.sort(key=lambda item: abs(item["contribution"]), reverse=True)
    return [{"reference_prediction": float(reference), "prediction": float(full)}] + out
