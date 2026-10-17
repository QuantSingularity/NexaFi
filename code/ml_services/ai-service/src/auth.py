import hmac
from typing import Any, Dict, Optional

import jwt
from ai_models.core.errors import AuthenticationError
from flask import current_app, request


def _bearer() -> Optional[str]:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


def is_internal_caller() -> bool:
    config = current_app.extensions["config"]
    supplied = request.headers.get("X-Internal-Key")
    if not config.internal_key or not supplied:
        return False
    return hmac.compare_digest(supplied.encode(), config.internal_key.encode())


def resolve_identity() -> Dict[str, Any]:
    config = current_app.extensions["config"]
    user_id = request.headers.get("X-User-ID")
    if is_internal_caller():
        if not user_id:
            raise AuthenticationError("X-User-ID is required for service calls")
        return {"user_id": user_id, "internal": True}
    token = _bearer()
    if token:
        try:
            payload = jwt.decode(token, config.secret_key, algorithms=["HS256"])
        except jwt.InvalidTokenError:
            raise AuthenticationError("Invalid or expired token")
        if payload.get("type") != "access" or not payload.get("user_id"):
            raise AuthenticationError("Invalid token type")
        return {
            "user_id": str(payload["user_id"]),
            "internal": False,
            "roles": payload.get("roles", []),
        }
    if config.allow_user_header and not config.internal_key and user_id:
        return {"user_id": user_id, "internal": False}
    raise AuthenticationError("Authentication required")


def require_internal() -> None:
    if not is_internal_caller():
        raise AuthenticationError("This operation is restricted to internal services")
