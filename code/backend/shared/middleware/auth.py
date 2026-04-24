import os
import uuid
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, List, Optional, Tuple

import bcrypt
import jwt
import redis
from flask import g, jsonify, request


class AuthManager:

    def __init__(self, secret_key: str, redis_client: object = None) -> None:
        self.secret_key = secret_key
        self.redis_client = redis_client or redis.Redis(
            host=os.environ.get("REDIS_HOST", "localhost"),
            port=int(os.environ.get("REDIS_PORT", 6379)),
            password=os.environ.get("REDIS_PASSWORD", None),
            db=1,
            decode_responses=True,
        )
        self.token_expiry = 3600
        self.refresh_token_expiry = 86400 * 7

    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

    def generate_tokens(
        self, user_id: str, email: str, roles: List[str]
    ) -> Tuple[str, str]:
        """Generate access and refresh tokens"""
        now = datetime.utcnow()
        access_payload = {
            "user_id": user_id,
            "email": email,
            "roles": roles,
            "type": "access",
            "iat": now,
            "exp": now + timedelta(seconds=self.token_expiry),
            "jti": str(uuid.uuid4()),
        }
        refresh_payload = {
            "user_id": user_id,
            "type": "refresh",
            "iat": now,
            "exp": now + timedelta(seconds=self.refresh_token_expiry),
            "jti": str(uuid.uuid4()),
        }
        access_token = jwt.encode(access_payload, self.secret_key, algorithm="HS256")
        refresh_token = jwt.encode(refresh_payload, self.secret_key, algorithm="HS256")
        self.redis_client.setex(
            f"access_token:{access_payload['jti']}", self.token_expiry, user_id
        )
        self.redis_client.setex(
            f"refresh_token:{refresh_payload['jti']}",
            self.refresh_token_expiry,
            user_id,
        )
        return (access_token, refresh_token)

    def verify_token(self, token: str, token_type: str = "access") -> Optional[Dict]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            if payload.get("type") != token_type:
                return None
            jti = payload.get("jti")
            if jti and (not self.redis_client.exists(f"{token_type}_token:{jti}")):
                return None
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def revoke_token(self, token: str) -> bool:
        """Revoke a token"""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=["HS256"],
                options={"verify_exp": False},
            )
            jti = payload.get("jti")
            token_type = payload.get("type", "access")
            if jti:
                self.redis_client.delete(f"{token_type}_token:{jti}")
                return True
        except jwt.InvalidTokenError:
            pass
        return False

    def refresh_access_token(self, refresh_token: str) -> Optional[Tuple[str, str]]:
        """Generate new access token using refresh token"""
        payload = self.verify_token(refresh_token, "refresh")
        if not payload:
            return None
        user_id = payload["user_id"]
        email = payload.get("email", f"{user_id}@nexafi.com")
        roles = payload.get("roles", ["user"])
        # Revoke old refresh token before issuing new one (rotation)
        old_jti = payload.get("jti")
        if old_jti:
            self.redis_client.delete(f"refresh_token:{old_jti}")
        return self.generate_tokens(user_id, email, roles)


auth_manager = None


def init_auth_manager(secret_key: str) -> object:
    """Initialize global auth manager"""
    global auth_manager
    auth_manager = AuthManager(secret_key)


ROLE_PERMISSIONS = {
    "admin": [
        "user:read",
        "user:write",
        "user:delete",
        "account:read",
        "account:write",
        "account:delete",
        "transaction:read",
        "transaction:write",
        "transaction:delete",
        "report:read",
        "report:write",
        "system:admin",
    ],
    "business_owner": [
        "user:read",
        "user:write",
        "account:read",
        "account:write",
        "transaction:read",
        "transaction:write",
        "report:read",
        "report:write",
    ],
    "accountant": [
        "account:read",
        "account:write",
        "transaction:read",
        "transaction:write",
        "report:read",
    ],
    "viewer": ["account:read", "transaction:read", "report:read"],
    "user": ["account:read", "transaction:read"],
}


def get_user_permissions(roles: List[str]) -> List[str]:
    """Get all permissions for user roles"""
    permissions = set()
    for role in roles:
        if role in ROLE_PERMISSIONS:
            permissions.update(ROLE_PERMISSIONS[role])
    return list(permissions)


def has_permission(user_roles: List[str], required_permission: str) -> bool:
    """Check if user has required permission"""
    user_permissions = get_user_permissions(user_roles)
    return required_permission in user_permissions


def require_auth(f: object) -> object:
    """Authentication decorator"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        if not token:
            return (jsonify({"error": "Authentication token required"}), 401)
        payload = auth_manager.verify_token(token)
        if not payload:
            return (jsonify({"error": "Invalid or expired token"}), 401)
        g.current_user = {
            "user_id": payload["user_id"],
            "email": payload["email"],
            "roles": payload["roles"],
        }
        return f(*args, **kwargs)

    return decorated_function


def require_permission(permission: str) -> object:
    """Permission-based authorization decorator"""

    def decorator(f):

        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, "current_user"):
                return (jsonify({"error": "Authentication required"}), 401)
            user_roles = g.current_user.get("roles", [])
            if not has_permission(user_roles, permission):
                return (jsonify({"error": "Insufficient permissions"}), 403)
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def require_role(required_roles: List[str]) -> object:
    """Role-based authorization decorator"""

    def decorator(f):

        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, "current_user"):
                return (jsonify({"error": "Authentication required"}), 401)
            user_roles = g.current_user.get("roles", [])
            if not any((role in user_roles for role in required_roles)):
                return (jsonify({"error": "Insufficient role privileges"}), 403)
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def optional_auth(f: object) -> object:
    """Optional authentication decorator - sets user info if token is valid"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        if token:
            payload = auth_manager.verify_token(token)
            if payload:
                g.current_user = {
                    "user_id": payload["user_id"],
                    "email": payload["email"],
                    "roles": payload["roles"],
                }
        return f(*args, **kwargs)

    return decorated_function
