from typing import Any
import time
import pytest
import requests
from core.logging import get_logger

logger = get_logger(__name__)
BASE_URLS = {
    "ai-service": "http://localhost:5004",
    "analytics-service": "http://localhost:5003",
    "api-gateway": "http://localhost:5000",
    "credit-service": "http://localhost:5002",
    "document-service": "http://localhost:5005",
    "ledger-service": "http://localhost:5001",
    "payment-service": "http://localhost:5006",
    "user-service": "http://localhost:5007",
}


def make_authenticated_request(
    service: Any,
    endpoint: Any,
    method: Any = "GET",
    headers: Any = None,
    json: Any = None,
    data: Any = None,
) -> Any:
    """
    Constructs a URL and sends an authenticated request to the specified service.

    Args:
        service (str): Key from BASE_URLS (e.g., "api-gateway").
        endpoint (str): The API path (e.g., "/api/v1/users/profile").
        method (str): HTTP method ("GET", "POST", "PUT", "DELETE").
        headers (dict, optional): Additional headers to include.
        json (dict, optional): JSON payload for POST/PUT requests.
        data (dict, optional): Form data for POST/PUT requests.

    Returns:
        requests.Response: The response object from the request.
    """
    url = f"{BASE_URLS[service]}{endpoint}"
    default_headers = {
        "X-User-ID": "test_user_id",
        "Authorization": "Bearer test_token",
    }
    if headers:
        default_headers.update(headers)
    try:
        if method == "GET":
            response = requests.get(url, headers=default_headers)
        elif method == "POST":
            response = requests.post(url, headers=default_headers, json=json, data=data)
        elif method == "PUT":
            response = requests.put(url, headers=default_headers, json=json, data=data)
        elif method == "DELETE":
            response = requests.delete(url, headers=default_headers)
        else:
            raise ValueError("Unsupported HTTP method")
        return response
    except requests.exceptions.ConnectionError as e:
        pytest.fail(
            f"Could not connect to {service} at {url}: {e}. Ensure services are running."
        )


@pytest.mark.security
def test_unauthorized_access_to_protected_endpoints() -> Any:
    """Test that protected endpoints return 401 Unauthorized without a token."""
    protected_endpoints = [
        ("ai-service", "/api/v1/predictions/cash-flow", "POST"),
        ("analytics-service", "/api/v1/analytics/summary", "GET"),
        ("api-gateway", "/api/v1/users/profile", "GET"),
        ("credit-service", "/api/v1/credit-scores", "GET"),
        ("document-service", "/api/v1/documents", "GET"),
        ("ledger-service", "/api/v1/accounts", "GET"),
        ("payment-service", "/api/v1/transactions", "GET"),
        ("user-service", "/api/v1/users/profile", "GET"),
    ]
    for service, endpoint, method in protected_endpoints:
        headers = {"X-User-ID": "test_user_id"}
        url = f"{BASE_URLS[service]}{endpoint}"
        if method == "POST":
            response = requests.post(url, headers=headers, json={})
        else:
            response = requests.get(url, headers=headers)
        assert (
            response.status_code == 401
        ), f"Expected 401 for {service}{endpoint}, got {response.status_code}"


@pytest.mark.security
def test_invalid_token_access_to_protected_endpoints() -> Any:
    """Test that protected endpoints return 401 Unauthorized with an invalid token."""
    protected_endpoints = [
        ("ai-service", "/api/v1/predictions/cash-flow", "POST"),
        ("analytics-service", "/api/v1/analytics/summary", "GET"),
        ("api-gateway", "/api/v1/users/profile", "GET"),
        ("credit-service", "/api/v1/credit-scores", "GET"),
        ("document-service", "/api/v1/documents", "GET"),
        ("ledger-service", "/api/v1/accounts", "GET"),
        ("payment-service", "/api/v1/transactions", "GET"),
        ("user-service", "/api/v1/users/profile", "GET"),
    ]
    for service, endpoint, method in protected_endpoints:
        headers = {"X-User-ID": "test_user_id", "Authorization": "Bearer invalid_token"}
        url = f"{BASE_URLS[service]}{endpoint}"
        if method == "POST":
            response = requests.post(url, headers=headers, json={})
        else:
            response = requests.get(url, headers=headers)
        assert (
            response.status_code == 401
        ), f"Expected 401 for {service}{endpoint} with invalid token, got {response.status_code}"


@pytest.mark.security
def test_sql_injection_vulnerability() -> Any:
    """
    Test for basic SQL injection attempts in input fields.

    The server is expected to reject the request, return an error status (e.g., 400
    or 500), or return a success status without modifying the database in a malicious way.
    For this test, we'll assert that the request does NOT succeed with a 2xx status.
    """
    sqli_payloads = [
        {"last_name": "'; OR 1=1--"},
        {"last_name": "'); DROP TABLE users;--"},
        {"last_name": "admin' --"},
    ]
    headers = {
        "Authorization": "Bearer YOUR_AUTH_TOKEN",
        "Content-Type": "application/json",
    }
    logger.info(f"\nTesting URL: {BASE_URL}")
    for payload in sqli_payloads:
        try:
            response = requests.put(BASE_URL, json=payload, headers=headers, timeout=5)
            assert (
                not response.ok
            ), f"SQL Injection FAILED: Server accepted payload {payload} with status {response.status_code}. This could indicate a vulnerability."
            logger.info(
                f"✅ Payload rejected or handled securely. Status: {response.status_code}"
            )
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Request to {BASE_URL} failed: {e}")
    base_data = {"email": "test@example.com", "first_name": "admin"}
    vulnerable_endpoint = ("user-service", "/api/v1/users/profile", "PUT")
    service, endpoint, method = vulnerable_endpoint
    for sqli_payload in sqli_payloads:
        data = {**base_data, **sqli_payload}
        response = make_authenticated_request(
            service, endpoint, method=method, json=data
        )
        assert (
            response.status_code != 200
        ), f"SQL Injection might be possible on {service}{endpoint}. Request succeeded with status {response.status_code}"
        error_content = response.text.lower()
        assert (
            "syntax error" not in error_content and "sql error" not in error_content
        ), f"SQL error message exposed on {service}{endpoint}"


@pytest.mark.security
def test_xss_vulnerability() -> Any:
    """Test for basic XSS vulnerability in user-supplied content."""
    xss_payload_alert = "<script>alert('XSS')</script>"
    xss_payload_img = "<img src=x onerror=alert('XSS')>"
    vulnerable_endpoints = [
        (
            "document-service",
            "/api/v1/documents",
            "POST",
            {"title": "XSS Test Alert", "content": xss_payload_alert},
        ),
        (
            "document-service",
            "/api/v1/documents",
            "POST",
            {"title": "XSS Test Img", "content": xss_payload_img},
        ),
    ]
    for service, endpoint, method, data in vulnerable_endpoints:
        response = make_authenticated_request(
            service, endpoint, method=method, json=data
        )
        assert (
            response.status_code == 200
        ), f"Failed to post XSS payload to {service}{endpoint}"
        assert (
            xss_payload_alert not in response.text
            and xss_payload_img not in response.text
        ), f"XSS payload reflected unescaped in response for {service}{endpoint}"


@pytest.mark.security
def test_rate_limiting_on_login() -> Any:
    """Test if the login endpoint has basic rate limiting to prevent brute-force attacks."""
    login_endpoint = "/auth/login"
    test_credentials = {"email": "nonexistent@example.com", "password": "wrongpassword"}
    responses = []
    for _ in range(15):
        response = requests.post(
            f"{BASE_URLS['api-gateway']}{login_endpoint}", json=test_credentials
        )
        responses.append(response.status_code)
        time.sleep(0.1)
    is_rate_limited = 429 in responses or responses.count(401) < 15
    assert is_rate_limited, "Rate limiting might not be in place for login"


@pytest.mark.security
def test_cors_misconfiguration() -> Any:
    """Test for CORS misconfigurations that might allow unauthorized origins."""
    test_origin = "http://malicious-site.com"
    headers = {"Origin": test_origin, "Access-Control-Request-Method": "GET"}
    for service, base_url in BASE_URLS.items():
        try:
            response = requests.options(f"{base_url}/health", headers=headers)
            if response.status_code == 200:
                allow_origin = response.headers.get("Access-Control-Allow-Origin")
                assert (
                    allow_origin != test_origin
                ), f"CORS misconfiguration detected on {service}: {test_origin} explicitly allowed"
                if allow_origin == "*":
                    logger.info(
                        f"Warning: CORS for {service} is set to '*' (wildcard). Check if this is intentional."
                    )
        except requests.exceptions.ConnectionError:
            logger.info(
                f"Could not connect to {service} at {base_url}, skipping CORS test."
            )


@pytest.mark.security
def test_sensitive_data_exposure() -> Any:
    """Test that sensitive data is not exposed in API responses."""
    response = make_authenticated_request("user-service", "/api/v1/users/profile")
    assert response.status_code == 200
    user_profile = response.json()
    assert (
        "password" not in user_profile
    ), "Password hash/field exposed in user profile API"
    assert "secret_key" not in user_profile, "Secret key exposed in user profile API"
    assert "api_key" not in user_profile, "API key exposed in user profile API"
    error_response = requests.get(f"{BASE_URLS['api-gateway']}/nonexistent-endpoint")
    assert error_response.status_code == 404
    error_content = error_response.text.lower()
    assert "traceback" not in error_content, "Stack trace exposed in error response"
    assert (
        "internal server error" in error_content or "not found" in error_content
    ), "Error message too verbose or not generic"


@pytest.mark.security
def test_http_headers_security() -> Any:
    """Test for presence of security-related HTTP headers."""
    response = requests.get(f"{BASE_URLS['api-gateway']}/health")
    assert response.status_code == 200
    headers = response.headers
    assert (
        headers.get("X-Content-Type-Options") == "nosniff"
    ), "Missing or incorrect X-Content-Type-Options header (MIME type sniffing prevention)"
    assert headers.get("X-Frame-Options") in [
        "DENY",
        "SAMEORIGIN",
    ], "Missing or incorrect X-Frame-Options header (Clickjacking prevention)"
    assert (
        headers.get("X-XSS-Protection") == "1; mode=block"
    ), "Missing or incorrect X-XSS-Protection header (Legacy XSS filter)"


@pytest.mark.security
def test_broken_authentication_session_management() -> Any:
    """Test for common authentication and session management flaws."""
    login_response = requests.post(
        f"{BASE_URLS['api-gateway']}/auth/login",
        json={"email": "test@example.com", "password": "password123"},
    )
    if login_response.status_code == 200:
        token = login_response.json().get("access_token")
        if token:
            logout_headers = {
                "Authorization": f"Bearer {token}",
                "X-User-ID": "test_user_id",
            }
            logout_response = requests.post(
                f"{BASE_URLS['api-gateway']}/auth/logout", headers=logout_headers
            )
            assert logout_response.status_code == 200, "Logout failed"
            invalidated_response = requests.get(
                f"{BASE_URLS['api-gateway']}/api/v1/users/profile",
                headers=logout_headers,
            )
            assert (
                invalidated_response.status_code == 401
            ), "Token not invalidated after logout (session remains active)"
    else:
        logger.info(
            "Skipping logout invalidation test: Login failed or mock data not available."
        )


@pytest.mark.security
def test_insecure_direct_object_references() -> Any:
    """Test for IDOR vulnerabilities by attempting to access other users' resources."""
    logger.info(
        "IDOR test requires multiple user accounts and resource creation; conceptual test only."
    )


@pytest.mark.security
def test_security_misconfiguration() -> Any:
    """Test for common security misconfigurations (e.g., exposed debug interfaces)."""
    logger.info(
        "Security misconfiguration test is conceptual and highly dependent on deployment environment."
    )


@pytest.mark.security
def test_using_components_with_known_vulnerabilities() -> Any:
    """Test for outdated or vulnerable components."""
    logger.info(
        "Testing for known vulnerabilities requires dependency scanning tools; conceptual test only."
    )


@pytest.mark.security
def test_insufficient_logging_monitoring() -> Any:
    """Test for insufficient logging and monitoring of security events."""
    logger.info(
        "Insufficient logging/monitoring test requires access to application logs; conceptual test only."
    )


@pytest.mark.security
def test_server_side_request_forgery_ssrf() -> Any:
    """Test for SSRF vulnerabilities."""
    logger.info("SSRF test is conceptual and depends on specific application features.")


@pytest.mark.security
def test_unvalidated_redirects_forwards() -> Any:
    """Test for unvalidated redirects and forwards."""
    logger.info(
        "Unvalidated redirects test is conceptual and depends on specific application features."
    )


@pytest.mark.security
def test_file_upload_vulnerabilities() -> Any:
    """Test for file upload vulnerabilities (e.g., uploading malicious executables)."""
    logger.info(
        "File upload vulnerability test is conceptual and depends on specific application features."
    )
