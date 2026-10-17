import os
import sys
from dataclasses import dataclass
from typing import Optional

_SRC = os.path.dirname(os.path.abspath(__file__))
_CODE = os.path.abspath(os.path.join(_SRC, "..", "..", ".."))
for _path in (
    os.path.join(_CODE, "ml_services"),
    os.path.join(_CODE, "backend", "shared"),
    os.path.dirname(_SRC),
):
    if os.path.isdir(_path) and _path not in sys.path:
        sys.path.insert(0, _path)


def _truthy(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Config:
    secret_key: str
    internal_key: Optional[str]
    allow_user_header: bool
    db_path: str
    model_dir: str
    payment_service_url: str
    request_timeout: float
    cors_origins: tuple
    port: int

    @classmethod
    def from_env(cls) -> "Config":
        origins = tuple(
            o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()
        )
        return cls(
            secret_key=os.getenv(
                "SECRET_KEY", "nexafi-default-secret-change-in-production"
            ),
            internal_key=os.getenv("INTERNAL_SERVICE_KEY") or None,
            allow_user_header=_truthy(os.getenv("ALLOW_USER_HEADER")),
            db_path=os.getenv("AI_DB_PATH", os.path.join(_SRC, "database", "app.db")),
            model_dir=os.getenv(
                "AI_MODEL_DIR", os.path.join(_SRC, "database", "models")
            ),
            payment_service_url=os.getenv(
                "PAYMENT_SERVICE_URL", "http://localhost:5003"
            ).rstrip("/"),
            request_timeout=float(os.getenv("SERVICE_REQUEST_TIMEOUT", "10")),
            cors_origins=origins or ("*",),
            port=int(os.getenv("PORT", "5004")),
        )
