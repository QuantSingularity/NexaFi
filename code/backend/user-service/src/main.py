import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Tuple, Union

from dotenv import load_dotenv
from flask import Flask, Response, g, jsonify, request
from flask_cors import CORS
from middleware.internal import install_internal_auth

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.join(BASE_DIR, "..", "..", "shared")
for _path in (BASE_DIR, SHARED_DIR):
    _abs = os.path.abspath(_path)
    if _abs not in sys.path:
        sys.path.insert(0, _abs)

from audit.audit_logger import AuditEventType, AuditSeverity, audit_action, audit_logger
from database.manager import BaseModel, initialize_database
from middleware.auth import (
    auth_manager,
    get_user_permissions,
    init_auth_manager,
    require_auth,
    require_permission,
)
from models.user import User
from nexafi_logging.logger import get_logger, setup_request_logging
from validation_schemas.schemas import (
    UserLoginSchema,
    UserRegistrationSchema,
    UserUpdateSchema,
    validate_json_request,
)

app = Flask(__name__)
install_internal_auth(app)

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY not set in environment. Exiting.")

app.config["SECRET_KEY"] = SECRET_KEY
app.config["DEBUG"] = os.getenv("DEBUG", "False").lower() == "true"
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 5001))

auth_manager = init_auth_manager(app.config["SECRET_KEY"])

CORS(
    app,
    origins=os.getenv("ALLOWED_ORIGINS", "*"),
    allow_headers=["Content-Type", "Authorization", "X-User-ID"],
    supports_credentials=True,
)

setup_request_logging(app)
logger = get_logger("user_service")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set in environment. Exiting.")

if DATABASE_URL.startswith("sqlite:///"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
else:
    db_path = DATABASE_URL

db_manager, migration_manager = initialize_database(db_path)
BaseModel.set_db_manager(db_manager)


def validate_password_strength(password: str) -> Tuple[bool, str]:
    if len(password) < 12:
        return (False, "Password must be at least 12 characters long")
    if not re.search("[A-Z]", password):
        return (False, "Password must contain at least one uppercase letter")
    if not re.search("[a-z]", password):
        return (False, "Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        return (False, "Password must contain at least one digit")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>\[\]\-\+_=\\]", password):
        return (False, "Password must contain at least one special character")

    common_patterns = ["123", "abc", "password", "admin", "user", "qwert"]
    for pattern in common_patterns:
        if pattern.lower() in password.lower():
            return (False, f"Password cannot contain common pattern: {pattern}")

    return (True, "Password is strong")


@app.errorhandler(400)
def handle_400(error: Exception) -> Tuple[Any, int]:
    return (jsonify({"error": "Bad request", "message": str(error)}), 400)


@app.errorhandler(401)
def handle_401(error: Exception) -> Tuple[Any, int]:
    return (
        jsonify(
            {
                "error": "Unauthorized",
                "message": "Authentication failed or token missing.",
            }
        ),
        401,
    )


@app.errorhandler(403)
def handle_403(error: Exception) -> Tuple[Any, int]:
    return (
        jsonify(
            {
                "error": "Forbidden",
                "message": "You do not have permission to access this resource.",
            }
        ),
        403,
    )


@app.errorhandler(404)
def handle_404(error: Exception) -> Tuple[Any, int]:
    return (jsonify({"error": "Not found", "message": str(error)}), 404)


@app.errorhandler(500)
def handle_500(error: Exception) -> Tuple[Any, int]:
    logger.error(f"Internal Server Error: {error}", exc_info=True)
    return (
        jsonify(
            {
                "error": "Internal server error",
                "message": "An unexpected error occurred",
            }
        ),
        500,
    )


@app.route("/api/v1/health", methods=["GET"])
def health_check() -> object:
    return jsonify(
        {
            "status": "healthy",
            "service": "user-service",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "2.0.1",
        }
    )


@app.route("/api/v1/auth/register", methods=["POST"])
@validate_json_request(UserRegistrationSchema)
@audit_action(
    AuditEventType.USER_REGISTRATION, "user_registration", severity=AuditSeverity.HIGH
)
def register() -> Tuple[Any, int]:
    data = request.validated_data
    existing_user = User.find_one("email = ?", (data["email"],))

    if existing_user:
        audit_logger.log_security_event(
            "duplicate_registration_attempt",
            f"Registration attempt with existing email: {data['email']}",
            {"email": data["email"]},
        )
        return (jsonify({"error": "User already exists"}), 409)

    is_strong, message = validate_password_strength(data["password"])
    if not is_strong:
        return (jsonify({"error": message}), 400)

    user = User(
        email=data["email"],
        first_name=data["first_name"],
        last_name=data["last_name"],
        phone=data.get("phone"),
        company_name=data.get("company_name"),
    )
    user.set_password(data["password"], auth_manager)
    user.save()
    user.add_role("user")

    audit_logger.log_user_action(
        AuditEventType.USER_REGISTRATION,
        str(user.id),
        "user_registered",
        details={
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
        },
    )
    logger.info(f"New user registered: {user.email}")

    return (
        jsonify({"message": "User registered successfully", "user": user.to_dict()}),
        201,
    )


@app.route("/api/v1/auth/login", methods=["POST"])
@validate_json_request(UserLoginSchema)
@audit_action(AuditEventType.USER_LOGIN, "user_login", severity=AuditSeverity.MEDIUM)
def login() -> Tuple[Any, int]:
    data = request.validated_data
    user = User.find_one("email = ?", (data["email"],))

    if not user:
        audit_logger.log_security_event(
            "login_attempt_unknown_user",
            f"Login attempt with unknown email: {data['email']}",
            {"email": data["email"]},
        )
        return (jsonify({"error": "Invalid credentials"}), 401)

    if user.is_locked():
        audit_logger.log_security_event(
            "login_attempt_locked_account",
            f"Login attempt on locked account: {user.email}",
            {"user_id": str(user.id), "email": user.email},
        )
        return (jsonify({"error": "Account is temporarily locked"}), 423)

    if not user.is_active:
        audit_logger.log_security_event(
            "login_attempt_inactive_account",
            f"Login attempt on inactive account: {user.email}",
            {"user_id": str(user.id), "email": user.email},
        )
        return (jsonify({"error": "Account is inactive"}), 401)

    if not user.check_password(data["password"], auth_manager):
        user.increment_failed_attempts()
        audit_logger.log_security_event(
            "failed_login_attempt",
            f"Failed login attempt for user: {user.email}",
            {
                "user_id": str(user.id),
                "email": user.email,
                "failed_attempts": user.failed_login_attempts,
            },
        )
        if user.is_locked():
            logger.warning(f"Account locked: {user.email}")
        return (jsonify({"error": "Invalid credentials"}), 401)

    user.reset_failed_attempts()
    roles = user.get_roles()
    access_token, refresh_token = auth_manager.generate_tokens(
        str(user.id), user.email, roles
    )

    audit_logger.log_user_action(
        AuditEventType.USER_LOGIN,
        str(user.id),
        "user_logged_in",
        details={"email": user.email, "roles": roles},
    )
    logger.info(f"User logged in: {user.email}")

    return (
        jsonify(
            {
                "message": "Login successful",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": user.to_dict(),
                "permissions": get_user_permissions(roles),
            }
        ),
        200,
    )


@app.route("/api/v1/auth/refresh", methods=["POST"])
def refresh_token() -> Union[Tuple[Response, int], Response]:
    data = request.get_json() or {}
    refresh_token = data.get("refresh_token")

    if not refresh_token:
        return (jsonify({"error": "Refresh token required"}), 400)

    result = auth_manager.refresh_access_token(refresh_token)

    if not result:
        return (jsonify({"error": "Invalid or expired refresh token"}), 401)

    access_token, new_refresh_token = result

    return (
        jsonify({"access_token": access_token, "refresh_token": new_refresh_token}),
        200,
    )


@app.route("/api/v1/auth/logout", methods=["POST"])
@require_auth
@audit_action(AuditEventType.USER_LOGOUT, "user_logout")
def logout() -> Tuple[Any, int]:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        auth_manager.revoke_token(token)

    user_id = g.get("current_user", {}).get("user_id")
    if user_id:
        audit_logger.log_user_action(
            AuditEventType.USER_LOGOUT, str(user_id), "user_logged_out"
        )

    return jsonify({"message": "Logged out successfully"}), 200


@app.route("/api/v1/users/profile", methods=["GET"])
@require_auth
def get_profile() -> Tuple[Any, int]:
    user_id = g.current_user["user_id"]
    user = User.find_by_id(user_id)

    if not user:
        return (jsonify({"error": "User not found"}), 404)

    return jsonify({"user": user.to_dict()}), 200


@app.route("/api/v1/users/profile", methods=["PUT"])
@require_auth
@validate_json_request(UserUpdateSchema)
@audit_action(AuditEventType.USER_UPDATE, "user_profile_update")
def update_profile() -> Tuple[Any, int]:
    data = request.validated_data
    user_id = g.current_user["user_id"]
    user = User.find_by_id(user_id)

    if not user:
        return (jsonify({"error": "User not found"}), 404)

    before_state = user.to_dict()

    for field in ["first_name", "last_name", "phone", "company_name"]:
        if field in data:
            setattr(user, field, data[field])

    user.updated_at = datetime.now(timezone.utc)
    user.save()

    audit_logger.log_user_action(
        AuditEventType.USER_UPDATE,
        str(user.id),
        "profile_updated",
        before_state=before_state,
        after_state=user.to_dict(),
    )

    return (
        jsonify({"message": "Profile updated successfully", "user": user.to_dict()}),
        200,
    )


@app.route("/api/v1/users", methods=["GET"])
@require_auth
@require_permission("user:read")
def list_users() -> Tuple[Any, int]:
    users = User.find_all()

    return (
        jsonify({"users": [user.to_dict() for user in users], "total": len(users)}),
        200,
    )


@app.route("/api/v1/users/<int:user_id>/roles", methods=["GET"])
@require_auth
@require_permission("user:read")
def get_user_roles(user_id: int) -> Tuple[Any, int]:
    user = User.find_by_id(user_id)

    if not user:
        return (jsonify({"error": "User not found"}), 404)

    roles = user.get_roles()
    permissions = get_user_permissions(roles)

    return (
        jsonify({"user_id": user_id, "roles": roles, "permissions": permissions}),
        200,
    )


@app.route("/api/v1/users/<int:user_id>/roles", methods=["POST"])
@require_auth
@require_permission("user:write")
@audit_action(
    AuditEventType.USER_UPDATE, "user_role_granted", severity=AuditSeverity.HIGH
)
def grant_role(user_id: int) -> Tuple[Any, int]:
    data = request.get_json() or {}
    role_name = data.get("role_name")

    if not role_name:
        return (jsonify({"error": "Role name required"}), 400)

    user = User.find_by_id(user_id)
    if not user:
        return (jsonify({"error": "User not found"}), 404)

    current_roles = user.get_roles()
    if role_name in current_roles:
        return (jsonify({"error": "User already has this role"}), 409)

    admin_id = g.current_user["user_id"]
    user.add_role(role_name, admin_id)

    audit_logger.log_user_action(
        AuditEventType.USER_UPDATE,
        str(user_id),
        "role_granted",
        details={"role_name": role_name, "granted_by": admin_id},
    )

    return (
        jsonify(
            {
                "message": f"Role {role_name} granted successfully",
                "roles": user.get_roles(),
            }
        ),
        200,
    )


@app.route("/api/v1/users/<int:user_id>/roles/<string:role_name>", methods=["DELETE"])
@require_auth
@require_permission("user:write")
@audit_action(
    AuditEventType.USER_UPDATE, "user_role_revoked", severity=AuditSeverity.HIGH
)
def revoke_role(user_id: int, role_name: str) -> Tuple[Any, int]:
    user = User.find_by_id(user_id)

    if not user:
        return (jsonify({"error": "User not found"}), 404)

    if role_name not in user.get_roles():
        return (jsonify({"error": f"User does not have role: {role_name}"}), 404)

    user.remove_role(role_name)

    audit_logger.log_user_action(
        AuditEventType.USER_UPDATE,
        str(user_id),
        "role_revoked",
        details={"role_name": role_name, "revoked_by": g.current_user["user_id"]},
    )

    return (
        jsonify(
            {
                "message": f"Role {role_name} revoked successfully",
                "roles": user.get_roles(),
            }
        ),
        200,
    )


if __name__ == "__main__":
    data_dir = os.path.join(BASE_DIR, "data")
    os.makedirs(data_dir, exist_ok=True)

    logger.info(
        f"Starting User Service on {HOST}:{PORT} (Debug: {app.config['DEBUG']})"
    )
    app.run(host=HOST, port=PORT, debug=app.config["DEBUG"])
