import time
from typing import Any, Dict, Optional

from ai_models.core.errors import ValidationError
from app_factory import Services
from auth import resolve_identity
from flask import current_app, request


def services() -> Services:
    return current_app.extensions["services"]


def identity() -> Dict[str, Any]:
    return resolve_identity()


def body() -> Dict[str, Any]:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError("A JSON object body is required")
    return data


def page_args() -> tuple:
    def read(name: str, default: int, high: int) -> int:
        raw = request.args.get(name)
        if raw in (None, ""):
            return default
        try:
            value = int(raw)
        except ValueError:
            raise ValidationError(f"{name} must be an integer")
        return max(1, min(value, high))

    return read("page", 1, 100000), read("per_page", 20, 100)


class Timer:
    def __enter__(self) -> "Timer":
        self.start = time.perf_counter()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.ms = int((time.perf_counter() - self.start) * 1000)


def optional_text(value: Any, name: str, limit: int = 200) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > limit:
        raise ValidationError(f"{name} must be a string of at most {limit} characters")
    return value.strip() or None
