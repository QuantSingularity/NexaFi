from typing import Any
import json
import requests
from unittest.mock import MagicMock, patch
import pytest
from NexaFi.backend.api_gateway.src.main import SERVICES, app


@pytest.fixture
def client() -> Any:
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def mock_requests() -> Any:
    with patch("requests.get") as mock_get, patch("requests.post") as mock_post, patch(
        "requests.put"
    ) as mock_put, patch("requests.delete") as mock_delete:
        yield (mock_get, mock_post, mock_put, mock_delete)


class TestAPIGatewayRoutes:

    def test_gateway_health_healthy(self, client: Any, mock_requests: Any) -> Any:
        mock_get, _, _, _ = mock_requests
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 0.05
        mock_get.return_value = mock_response
        response = client.get("/health")
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["status"] == "healthy"
        assert "user-service" in json_data["services"]
        assert json_data["services"]["user-service"]["status"] == "healthy"

    def test_gateway_health_degraded(self, client: Any, mock_requests: Any) -> Any:
        mock_get, _, _, _ = mock_requests
        mock_response_healthy = MagicMock()
        mock_response_healthy.status_code = 200
        mock_response_healthy.elapsed.total_seconds.return_value = 0.05
        mock_response_unhealthy = MagicMock()
        mock_response_unhealthy.status_code = 500
        mock_response_unhealthy.elapsed.total_seconds.return_value = 0.1
        mock_get.side_effect = [
            mock_response_healthy,
            mock_response_unhealthy,
            mock_response_healthy,
            mock_response_healthy,
        ]
        response = client.get("/health")
        assert response.status_code == 503
        json_data = response.get_json()
        assert json_data["status"] == "degraded"
        if "ledger-service" in json_data["services"]:
            assert json_data["services"]["ledger-service"]["status"] == "unhealthy"

    def test_proxy_user_service_get(self, client: Any, mock_requests: Any) -> Any:
        mock_get, _, _, _ = mock_requests
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps({"message": "User data"}).encode("utf-8")
        mock_response.json.return_value = {"message": "User data"}
        mock_get.return_value = mock_response
        response = client.get("/api/v1/users/123", headers={"X-User-ID": "test_user"})
        assert response.status_code == 200
        assert response.get_json() == {"message": "User data"}
        mock_get.assert_called_once_with(
            f"{SERVICES['user-service']['url']}/api/v1/users/123",
            headers={"X-User-ID": "test_user"},
            params={},
            timeout=30,
        )

    def test_proxy_user_service_post(self, client: Any, mock_requests: Any) -> Any:
        _, mock_post, _, _ = mock_requests
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.content = json.dumps({"message": "User created"}).encode("utf-8")
        mock_response.json.return_value = {"message": "User created"}
        mock_post.return_value = mock_response
        data = {"username": "newuser", "email": "new@example.com"}
        response = client.post(
            "/api/v1/users",
            headers={"X-User-ID": "test_user", "Content-Type": "application/json"},
            json=data,
        )
        assert response.status_code == 201
        assert response.get_json() == {"message": "User created"}
        mock_post.assert_called_once_with(
            f"{SERVICES['user-service']['url']}/api/v1/users",
            headers={"X-User-ID": "test_user", "Content-Type": "application/json"},
            json=data,
            params={},
            timeout=30,
        )

    def test_proxy_user_service_put(self, client: Any, mock_requests: Any) -> Any:
        _, _, mock_put, _ = mock_requests
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps({"message": "User updated"}).encode("utf-8")
        mock_response.json.return_value = {"message": "User updated"}
        mock_put.return_value = mock_response
        data = {"email": "updated@example.com"}
        response = client.put(
            "/api/v1/users/123",
            headers={"X-User-ID": "test_user", "Content-Type": "application/json"},
            json=data,
        )
        assert response.status_code == 200
        assert response.get_json() == {"message": "User updated"}
        mock_put.assert_called_once_with(
            f"{SERVICES['user-service']['url']}/api/v1/users/123",
            headers={"X-User-ID": "test_user", "Content-Type": "application/json"},
            json=data,
            params={},
            timeout=30,
        )

    def test_proxy_user_service_delete(self, client: Any, mock_requests: Any) -> Any:
        _, _, _, mock_delete = mock_requests
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.content = b""
        mock_response.json.return_value = {}
        mock_delete.return_value = mock_response
        response = client.delete(
            "/api/v1/users/123", headers={"X-User-ID": "test_user"}
        )
        assert response.status_code == 204
        assert response.get_data() == b""
        mock_delete.assert_called_once_with(
            f"{SERVICES['user-service']['url']}/api/v1/users/123",
            headers={"X-User-ID": "test_user"},
            params={},
            timeout=30,
        )

    def test_proxy_service_not_found(self, client: Any) -> Any:
        response = client.get("/api/v1/non-existent-service/endpoint")
        assert response.status_code == 404
        assert response.get_json()["error"] == "Service not found for this endpoint"

    def test_proxy_service_timeout(self, client: Any, mock_requests: Any) -> Any:
        mock_get, _, _, _ = mock_requests
        mock_get.side_effect = requests.exceptions.Timeout
        response = client.get("/api/v1/users/123", headers={"X-User-ID": "test_user"})
        assert response.status_code == 504
        assert response.get_json()["error"] == "Service timeout"

    def test_proxy_service_unavailable(self, client: Any, mock_requests: Any) -> Any:
        mock_get, _, _, _ = mock_requests
        mock_get.side_effect = requests.exceptions.ConnectionError
        response = client.get("/api/v1/users/123", headers={"X-User-ID": "test_user"})
        assert response.status_code == 503
        assert response.get_json()["error"] == "Service unavailable"

    def test_list_services(self, client: Any) -> Any:
        response = client.get("/api/v1/services")
        assert response.status_code == 200
        json_data = response.get_json()
        assert "services" in json_data
        assert "total_services" in json_data
        assert len(json_data["services"]) == len(SERVICES)

    def test_root_endpoint(self, client: Any) -> Any:
        response = client.get("/")
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["message"] == "NexaFi API Gateway"
        assert "version" in json_data
        assert "timestamp" in json_data
        assert "available_endpoints" in json_data
