import logging
import os
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

AI_SERVICE_URL = os.environ.get("AI_SERVICE_URL", "http://ai-service:5004").rstrip("/")
SCREENING_TIMEOUT = float(os.environ.get("FRAUD_SCREENING_TIMEOUT", "3"))
HISTORY_LIMIT = 200


def screening_mode() -> str:
    mode = os.environ.get("FRAUD_SCREENING_MODE", "monitor").strip().lower()
    return mode if mode in ("off", "monitor", "enforce") else "monitor"


def fail_closed() -> bool:
    return os.environ.get("FRAUD_SCREENING_FAIL_CLOSED", "false").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def blocked_actions() -> tuple:
    level = os.environ.get("FRAUD_SCREENING_BLOCK_ON", "block").strip().lower()
    return ("block", "review") if level == "review" else ("block",)


def history_payload(transactions: List[Any]) -> List[Dict[str, Any]]:
    return [
        {
            "amount": t.amount,
            "timestamp": t.created_at,
            "currency": t.currency,
            "merchant": t.reference or t.description,
            "category": t.transaction_type,
        }
        for t in transactions
        if t.amount is not None and t.created_at
    ]


def screen_transaction(
    user_id: str, transaction: Dict[str, Any], history: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    if screening_mode() == "off":
        return None
    headers = {"X-User-ID": user_id, "Content-Type": "application/json"}
    internal_key = os.environ.get("INTERNAL_SERVICE_KEY")
    if internal_key:
        headers["X-Internal-Key"] = internal_key
    try:
        response = requests.post(
            f"{AI_SERVICE_URL}/api/v1/anomalies/score",
            json={"transaction": transaction, "history": history},
            headers=headers,
            timeout=SCREENING_TIMEOUT,
        )
        if response.status_code != 200:
            logger.warning("Fraud screening returned %s", response.status_code)
            return {"available": False}
        result = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Fraud screening unavailable: %s", exc)
        return {"available": False}
    return {
        "available": True,
        "risk_score": result.get("risk_score"),
        "risk_level": result.get("risk_level"),
        "recommended_action": result.get("recommended_action"),
        "reasons": result.get("reasons", []),
    }
