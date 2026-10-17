import math
from collections import Counter
from datetime import timedelta
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from ai_models.core.errors import ValidationError
from ai_models.core.validation import (
    as_float,
    parse_timestamp,
    require_dict,
    try_parse_timestamp,
    utcnow,
)

STRUCTURING_THRESHOLDS = (3000.0, 5000.0, 10000.0)
MIN_PROFILE = 5


def _signal(weight: float, active: bool, score: float, reason: str) -> Dict[str, Any]:
    return {
        "weight": weight,
        "score": score if active else 0.0,
        "reason": reason if active else None,
    }


class TransactionAnomalyDetector:
    def __init__(
        self, velocity_window_minutes: int = 60, velocity_limit: int = 10
    ) -> None:
        self.velocity_window = timedelta(minutes=velocity_window_minutes)
        self.velocity_limit = velocity_limit

    @staticmethod
    def _prepare(transaction: Any) -> Dict[str, Any]:
        transaction = require_dict(transaction, "transaction")
        amount = as_float(transaction.get("amount"), "amount")
        if amount is None:
            raise ValidationError("amount is required")
        stamp = parse_timestamp(
            transaction.get("timestamp") or transaction.get("created_at") or utcnow(),
            "timestamp",
        )
        return {
            "amount": abs(amount),
            "timestamp": stamp,
            "merchant": str(
                transaction.get("merchant") or transaction.get("counterparty") or ""
            ).lower()
            or None,
            "category": str(
                transaction.get("category")
                or transaction.get("merchant_category")
                or ""
            ).lower()
            or None,
            "currency": str(transaction.get("currency") or "").upper() or None,
            "country": str(transaction.get("country") or "").upper() or None,
            "id": transaction.get("id") or transaction.get("transaction_id"),
        }

    def _history(self, history: Sequence[Any], reference: Any) -> List[Dict[str, Any]]:
        prepared = []
        for item in history or []:
            try:
                row = self._prepare(item)
            except ValidationError:
                continue
            if row["timestamp"] <= reference:
                prepared.append(row)
        return prepared

    def score_transaction(
        self, transaction: Any, history: Optional[Sequence[Any]] = None
    ) -> Dict[str, Any]:
        current = self._prepare(transaction)
        past = self._history(history or [], current["timestamp"])
        past = [h for h in past if not (current["id"] and h["id"] == current["id"])]
        amounts = np.array([h["amount"] for h in past], dtype=float)
        signals: Dict[str, Dict[str, Any]] = {}

        if len(amounts) >= MIN_PROFILE:
            logs = np.log1p(amounts)
            median = float(np.median(logs))
            mad = float(np.median(np.abs(logs - median))) * 1.4826
            mad = max(mad, 0.15)
            z = (math.log1p(current["amount"]) - median) / mad
            signals["amount_outlier"] = _signal(
                0.40,
                z > 3.0,
                min(1.0, (z - 3.0) / 4.0 + 0.6),
                f"Amount is {z:.1f} robust deviations above this account's norm",
            )
            largest = float(amounts.max())
            signals["new_maximum"] = _signal(
                0.15,
                current["amount"] > largest * 1.5,
                0.7,
                "Amount exceeds 1.5x the largest prior transaction",
            )
            hours = Counter(h["timestamp"].hour for h in past)
            share = hours.get(current["timestamp"].hour, 0) / len(past)
            signals["unusual_hour"] = _signal(
                0.15,
                share < 0.03 and len(past) >= 20,
                0.6,
                "Transaction occurs at an hour this account rarely transacts",
            )
        else:
            signals["amount_outlier"] = _signal(
                0.40,
                current["amount"] > 50000,
                0.9,
                "Very large amount with no account history",
            )

        window_start = current["timestamp"] - self.velocity_window
        recent = [h for h in past if h["timestamp"] >= window_start]
        count = len(recent) + 1
        signals["velocity"] = _signal(
            0.25,
            count > self.velocity_limit,
            min(1.0, count / (2.0 * self.velocity_limit)),
            f"{count} transactions within {int(self.velocity_window.total_seconds() // 60)} minutes",
        )
        for key, label in (
            ("merchant", "merchant"),
            ("country", "country"),
            ("currency", "currency"),
        ):
            known = {h[key] for h in past if h[key]}
            value = current[key]
            signals[f"new_{key}"] = _signal(
                0.10 if key != "country" else 0.20,
                bool(value) and len(past) >= MIN_PROFILE and value not in known,
                0.6,
                f"First transaction with this {label}",
            )
        near = any(t * 0.95 <= current["amount"] < t for t in STRUCTURING_THRESHOLDS)
        signals["structuring"] = _signal(
            0.20, near, 0.7, "Amount sits just below a common reporting threshold"
        )

        remaining = 1.0
        for item in signals.values():
            remaining *= 1.0 - item["weight"] * item["score"]
        risk = float(np.clip(1.0 - remaining, 0.0, 1.0))
        reasons = [item["reason"] for item in signals.values() if item["reason"]]
        level = "high" if risk >= 0.6 else "medium" if risk >= 0.3 else "low"
        return {
            "is_anomaly": risk >= 0.5,
            "risk_score": round(risk, 4),
            "anomaly_score": round(risk, 4),
            "risk_level": level,
            "severity": level,
            "reasons": reasons,
            "risk_factors": reasons,
            "signals": {
                k: round(v["weight"] * v["score"], 4) for k, v in signals.items()
            },
            "history_size": len(past),
            "recommended_action": (
                "block" if risk >= 0.8 else "review" if risk >= 0.5 else "allow"
            ),
        }

    def score_batch(self, transactions: Sequence[Any]) -> List[Dict[str, Any]]:
        if not isinstance(transactions, (list, tuple)):
            raise ValidationError("transactions must be a list")
        if len(transactions) > 5000:
            raise ValidationError("At most 5000 transactions per batch")
        ordered = sorted(
            enumerate(transactions),
            key=lambda pair: try_parse_timestamp(
                require_dict(pair[1], "transaction").get("timestamp")
            )
            or utcnow(),
        )
        results: Dict[int, Dict[str, Any]] = {}
        seen: List[Any] = []
        for index, item in ordered:
            results[index] = self.score_transaction(item, seen)
            seen.append(item)
        return [results[i] for i in range(len(transactions))]
