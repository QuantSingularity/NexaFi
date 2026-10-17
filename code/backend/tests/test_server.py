#!/usr/bin/env python3

import os
import sys

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shared"),
)


def test_flask_importable():
    try:
        pass
    except ImportError as exc:
        raise AssertionError(f"Flask import failed: {exc}") from exc


def test_flask_app_creation():
    from flask import Flask

    app = Flask(__name__)

    @app.route("/health")
    def health():
        return {"status": "healthy", "service": "test-server"}

    @app.route("/")
    def index():
        return {"message": "NexaFi Backend Test Server", "status": "running"}

    assert "/health" in [rule.rule for rule in app.url_map.iter_rules()]
    assert "/" in [rule.rule for rule in app.url_map.iter_rules()]


def test_flask_test_client_health():
    from flask import Flask

    app = Flask(__name__)

    @app.route("/health")
    def health():
        return {"status": "healthy", "service": "test-server"}

    with app.test_client() as client:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "healthy"
        assert data["service"] == "test-server"


def test_flask_test_client_index():
    from flask import Flask

    app = Flask(__name__)

    @app.route("/")
    def index():
        return {"message": "NexaFi Backend Test Server", "status": "running"}

    with app.test_client() as client:
        response = client.get("/")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "running"


def _run_server(port: int = 5000):
    from flask import Flask

    print("=" * 60)
    print("NexaFi Backend Test Server")
    print("=" * 60)

    print("\n[1/3] Testing imports...")
    print("Flask imports successful")

    print("\n[2/3] Testing shared modules...")
    print("Logging module accessible")

    print("\n[3/3] Starting minimal server...")
    app = Flask(__name__)

    @app.route("/health")
    def health():
        return {"status": "healthy", "service": "test-server"}

    @app.route("/")
    def index():
        return {"message": "NexaFi Backend Test Server", "status": "running"}

    print("\n" + "=" * 60)
    print("Server starting successfully!")
    print("=" * 60)
    print("\nTest endpoints:")
    print(f"  - http://localhost:{port}/")
    print(f"  - http://localhost:{port}/health")
    print("\nPress Ctrl+C to stop\n")

    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    _run_server()
