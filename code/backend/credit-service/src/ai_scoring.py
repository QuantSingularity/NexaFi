import logging
import os
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

AI_SERVICE_URL = os.environ.get("AI_SERVICE_URL", "http://ai-service:5004").rstrip("/")
AI_TIMEOUT = float(os.environ.get("SERVICE_REQUEST_TIMEOUT", "10"))


def score_with_ai(user_id: str, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    headers = {"X-User-ID": user_id, "Content-Type": "application/json"}
    internal_key = os.environ.get("INTERNAL_SERVICE_KEY")
    if internal_key:
        headers["X-Internal-Key"] = internal_key
    try:
        response = requests.post(
            f"{AI_SERVICE_URL}/api/v1/predictions/credit-score",
            json={"business_data": features},
            headers=headers,
            timeout=AI_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning("AI scoring unavailable: %s", exc)
        return None
    if response.status_code != 200:
        logger.warning(
            "AI scoring returned %s: %s", response.status_code, response.text[:200]
        )
        return None
    try:
        return response.json()
    except ValueError:
        return None


def rule_based_score(features: Dict[str, Any]) -> int:
    adjustment = 0
    income = float(features.get("annual_income") or features.get("annual_revenue") or 0)
    if income > 100000:
        adjustment += 50
    elif income < 50000:
        adjustment -= 30
    debt = float(features.get("total_debt") or 0)
    if debt > 50000:
        adjustment -= 40
    elif debt < 10000:
        adjustment += 20
    return max(300, min(850, 650 + adjustment))
