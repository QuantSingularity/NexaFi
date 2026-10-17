import os
from typing import Any, Dict, List, Optional

import requests
from ai_models.core.errors import DependencyError


class ServiceClient:
    def __init__(
        self, base_url: str, timeout: float = 10.0, internal_key: Optional[str] = None
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.internal_key = internal_key or os.getenv("INTERNAL_SERVICE_KEY") or None
        self.session = requests.Session()

    def get(
        self, path: str, user_id: str, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        headers = {"X-User-ID": user_id, "Accept": "application/json"}
        if self.internal_key:
            headers["X-Internal-Key"] = self.internal_key
        try:
            response = self.session.get(
                f"{self.base_url}{path}",
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise DependencyError(f"Upstream service unreachable: {exc}") from exc
        if response.status_code != 200:
            raise DependencyError(
                f"Upstream service returned {response.status_code}", {"path": path}
            )
        try:
            return response.json()
        except ValueError as exc:
            raise DependencyError("Upstream service returned invalid JSON") from exc


class PaymentHistoryClient:
    def __init__(self, client: ServiceClient) -> None:
        self.client = client

    def transactions(self, user_id: str, limit: int = 1000) -> List[Dict[str, Any]]:
        payload = self.client.get("/api/v1/transactions", user_id, {"per_page": limit})
        items = payload.get("transactions") if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            raise DependencyError("Unexpected transactions payload")
        return items
