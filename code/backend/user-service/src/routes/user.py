"""
User service routes - additional/extended endpoints as a Blueprint.
Core auth and user routes are handled directly in main.py.
"""

from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import Blueprint, current_app, g, jsonify, request
from models.user import User, UserSession

user_bp = Blueprint("user", __name__)


def generate_token(user_id: str, expires_hours: object = 24) -> object:
    """Generate JWT token"""
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=expires_hours),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(
        payload, current_app.config.get("SECRET_KEY", "dev-secret"), algorithm="HS256"
    )


def verify_token(token: object) -> object:
    """Verify JWT token"""
    try:
        payload = jwt.decode(
            token,
            current_app.config.get("SECRET_KEY", "dev-secret"),
            algorithms=["HS256"],
        )
        return payload["user_id"]
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def require_auth(f: object) -> object:
    """Authentication decorator for blueprint routes"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return (jsonify({"error": "Invalid authorization header format"}), 401)
        if not token:
            return (jsonify({"error": "Authentication token required"}), 401)
        user_id = verify_token(token)
        if not user_id:
            return (jsonify({"error": "Invalid or expired token"}), 401)
        user = User.find_by_id(user_id)
        if not user or not user.is_active:
            return (jsonify({"error": "User not found or inactive"}), 401)
        if user.is_locked():
            return (jsonify({"error": "Account is locked"}), 423)
        g.current_user = {
            "user_id": str(user.id),
            "email": user.email,
            "roles": user.get_roles(),
        }
        return f(*args, **kwargs)

    return decorated_function


@user_bp.route("/api/v1/users/sessions", methods=["GET"])
@require_auth
def get_sessions() -> object:
    """Get active sessions for current user"""
    user_id = g.current_user["user_id"]
    sessions = UserSession.find_all("user_id = ? AND is_active = 1", (user_id,))
    return (
        jsonify(
            {
                "sessions": [
                    {
                        "id": s.id,
                        "ip_address": s.ip_address,
                        "user_agent": s.user_agent,
                        "created_at": s.created_at,
                        "expires_at": s.expires_at,
                    }
                    for s in sessions
                ]
            }
        ),
        200,
    )


@user_bp.route("/api/v1/users/sessions/<int:session_id>", methods=["DELETE"])
@require_auth
def revoke_session(session_id: int) -> object:
    """Revoke a specific session"""
    user_id = g.current_user["user_id"]
    session = UserSession.find_one("id = ? AND user_id = ?", (session_id, user_id))
    if not session:
        return (jsonify({"error": "Session not found"}), 404)
    session.is_active = False
    session.save()
    return jsonify({"message": "Session revoked successfully"}), 200


@user_bp.route("/api/v1/users/change-password", methods=["POST"])
@require_auth
def change_password() -> object:
    """Change user password"""
    data = request.get_json() or {}
    user_id = g.current_user["user_id"]

    current_password = data.get("current_password")
    new_password = data.get("new_password")

    if not current_password or not new_password:
        return (
            jsonify({"error": "current_password and new_password are required"}),
            400,
        )

    if len(new_password) < 12:
        return (jsonify({"error": "New password must be at least 12 characters"}), 400)

    user = User.find_by_id(user_id)
    if not user:
        return (jsonify({"error": "User not found"}), 404)

    from shared.middleware.auth import auth_manager

    if not user.check_password(current_password, auth_manager):
        return (jsonify({"error": "Current password is incorrect"}), 401)

    user.set_password(new_password, auth_manager)
    user.save()

    return jsonify({"message": "Password changed successfully"}), 200
