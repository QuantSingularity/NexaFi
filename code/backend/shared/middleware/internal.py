import hmac
import os
from typing import Iterable

from flask import Flask, jsonify, request

DEFAULT_OPEN_PATHS = ("/health", "/api/v1/health")


def install_internal_auth(app: Flask, open_prefixes: Iterable[str] = ()) -> bool:
    key = os.environ.get("INTERNAL_SERVICE_KEY")
    if not key:
        return False
    expected = key.encode()
    open_prefixes = tuple(open_prefixes)

    @app.before_request
    def require_internal_key():
        path = request.path
        if request.method == "OPTIONS" or path in DEFAULT_OPEN_PATHS:
            return None
        if path.endswith("/health") or path.startswith(open_prefixes):
            return None
        supplied = request.headers.get("X-Internal-Key", "")
        if not hmac.compare_digest(supplied.encode(), expected):
            return (jsonify({"error": "Forbidden"}), 403)
        return None

    return True
