import os
import sys
import tempfile

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CODE = os.path.abspath(os.path.join(ROOT, ".."))
for path in (
    os.path.join(ROOT, "ai-service", "src"),
    os.path.join(CODE, "backend", "shared"),
    ROOT,
):
    if path not in sys.path:
        sys.path.insert(0, path)

INTERNAL_KEY = "test-internal-key"


class FakePayments:
    def __init__(self, transactions=None):
        self.items = transactions or []

    def transactions(self, user_id, limit=1000):
        return list(self.items)


@pytest.fixture
def ai_app():
    from app_factory import build_services, create_app
    from service_config import Config

    directory = tempfile.mkdtemp()
    config = Config(
        secret_key="unit-test-secret-key-with-sufficient-length",
        internal_key=INTERNAL_KEY,
        allow_user_header=False,
        db_path=os.path.join(directory, "ai.db"),
        model_dir=os.path.join(directory, "models"),
        payment_service_url="http://payments.invalid",
        request_timeout=1.0,
        cors_origins=("*",),
        port=5004,
    )
    services = build_services(config, {"payments": FakePayments()})
    app = create_app(config, services)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(ai_app):
    return ai_app.test_client()


@pytest.fixture
def headers():
    return {"X-Internal-Key": INTERNAL_KEY, "X-User-ID": "user-1"}
