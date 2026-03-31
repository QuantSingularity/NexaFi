import base64
import io
import json
import secrets
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict

import jwt
import qrcode
from flask import Blueprint, current_app, jsonify, request
from flask_cors import cross_origin
from models.user import User, UserSession

user_bp = Blueprint("user", __name__)


def generate_token(user_id: Any, expires_hours: Any = 24) -> Any:
    """Generate JWT token"""
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=expires_hours),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(
        payload, current_app.config.get("SECRET_KEY", "dev-secret"), algorithm="HS256"
    )


def verify_token(token: Any) -> Any:
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


def log_audit_event(
    user_id: Any,
    action: Any,
    resource_type: Any = None,
    resource_id: Any = None,
    old_values: Any = None,
    new_values: Any = None,
    status: Any = "success",
    error_message: Any = None,
    severity: Any = "info",
) -> Any:
    """Log audit event"""
    try:
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            request_method=request.method,
            request_path=request.path,
            old_values=json.dumps(old_values) if old_values else None,
            new_values=json.dumps(new_values) if new_values else None,
            status=status,
            error_message=error_message,
            severity=severity,
        )
        db.session.add(audit_log)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(f"Failed to log audit event: {str(e)}")


def require_auth(f: Any) -> Any:
    """Authentication decorator"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header:
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return (jsonify({"error": "Invalid authorization header format"}), 401)
        if not token:
            return (jsonify({"error": "Authentication token required"}), 401)
        user_id = verify_token(token)
        if not user_id:
            return (jsonify({"error": "Invalid or expired token"}), 401)
        user = User.query.get(user_id)
        if not user or not user.is_active:
            return (jsonify({"error": "User not found or inactive"}), 401)
        if user.is_locked():
            return (jsonify({"error": "Account is locked"}), 423)
        request.current_user = user
        return f(*args, **kwargs)

    return decorated_function


def require_permission(permission_name: Any) -> Any:
    """Permission decorator"""

    def decorator(f):

        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(request, "current_user"):
                return (jsonify({"error": "Authentication required"}), 401)
            if not request.current_user.has_permission(permission_name):
                log_audit_event(
                    request.current_user.id,
                    f"permission_denied_{permission_name}",
                    status="failure",
                    severity="warning",
                )
                return (jsonify({"error": "Insufficient permissions"}), 403)
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def require_mfa_if_enabled(f: Any) -> Any:
    """MFA verification decorator"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(request, "current_user"):
            return (jsonify({"error": "Authentication required"}), 401)
        user = request.current_user
        if user.mfa_enabled:
            mfa_token = request.headers.get("X-MFA-Token")
            if not mfa_token or not user.verify_mfa_token(mfa_token):
                return (jsonify({"error": "MFA verification required"}), 403)
        return f(*args, **kwargs)

    return decorated_function


@user_bp.route("/api/v1/auth/register", methods=["POST"])
@cross_origin()
def register() -> Any:
    """User registration with validation"""
    try:
        data = request.get_json()
        required_fields = ["email", "password", "first_name", "last_name"]
        for field in required_fields:
            if not data.get(field):
                return (jsonify({"error": f"{field} is required"}), 400)
        if User.query.filter_by(email=data["email"]).first():
            return (jsonify({"error": "Email already registered"}), 409)
        password = data["password"]
        if len(password) < 8:
            return (
                jsonify({"error": "Password must be at least 8 characters long"}),
                400,
            )
        user = User(
            email=data["email"].lower().strip(),
            first_name=data["first_name"].strip(),
            last_name=data["last_name"].strip(),
            phone=data.get("phone", "").strip(),
            business_type=data.get("business_type"),
            company_size=data.get("company_size"),
            industry=data.get("industry"),
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        profile = UserProfile(
            user_id=user.id,
            company_name=data.get("company_name"),
            timezone=data.get("timezone", "UTC"),
            language=data.get("language", "en"),
            currency_preference=data.get("currency_preference", "USD"),
        )
        db.session.add(profile)
        default_role = Role.query.filter_by(name="business_owner").first()
        if default_role:
            user_role = UserRole(user_id=user.id, role_id=default_role.id)
            db.session.add(user_role)
        custom_fields = data.get("custom_fields", {})
        for field_name, field_value in custom_fields.items():
            custom_field = UserCustomField(
                user_id=user.id,
                field_name=field_name,
                field_value=str(field_value),
                field_type=data.get("custom_field_types", {}).get(field_name, "text"),
            )
            db.session.add(custom_field)
        db.session.commit()
        log_audit_event(user.id, "user_registration", "user", user.id)
        access_token = generate_token(user.id)
        refresh_token = secrets.token_urlsafe(32)
        session = UserSession(
            user_id=user.id,
            session_token=access_token,
            refresh_token=refresh_token,
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        db.session.add(session)
        db.session.commit()
        return (
            jsonify(
                {
                    "message": "User registered successfully",
                    "user": user.to_dict(),
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expires_in": 86400,
                }
            ),
            201,
        )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Registration error: {str(e)}")
        return (jsonify({"error": "Registration failed"}), 500)


@user_bp.route("/api/v1/auth/login", methods=["POST"])
@cross_origin()
def login() -> Any:
    """Login with MFA support and security features"""
    try:
        data = request.get_json()
        email = data.get("email", "").lower().strip()
        password = data.get("password", "")
        mfa_token = data.get("mfa_token")
        if not email or not password:
            return (jsonify({"error": "Email and password are required"}), 400)
        user = User.query.filter_by(email=email).first()
        if not user:
            log_audit_event(
                None,
                "login_attempt_invalid_email",
                status="failure",
                severity="warning",
            )
            return (jsonify({"error": "Invalid credentials"}), 401)
        if user.is_locked():
            log_audit_event(
                user.id,
                "login_attempt_locked_account",
                status="failure",
                severity="warning",
            )
            return (
                jsonify({"error": "Account is locked. Please try again later."}),
                423,
            )
        if not user.check_password(password):
            user.increment_failed_login()
            db.session.commit()
            log_audit_event(
                user.id,
                "login_attempt_invalid_password",
                status="failure",
                severity="warning",
            )
            return (jsonify({"error": "Invalid credentials"}), 401)
        if not user.is_active:
            log_audit_event(
                user.id,
                "login_attempt_inactive_account",
                status="failure",
                severity="warning",
            )
            return (jsonify({"error": "Account is inactive"}), 401)
        if user.mfa_enabled:
            if not mfa_token:
                return (
                    jsonify({"error": "MFA token required", "mfa_required": True}),
                    403,
                )
            if not user.verify_mfa_token(mfa_token):
                log_audit_event(
                    user.id, "login_mfa_failure", status="failure", severity="warning"
                )
                return (jsonify({"error": "Invalid MFA token"}), 403)
        user.failed_login_attempts = 0
        user.last_login = datetime.utcnow()
        access_token = generate_token(user.id)
        refresh_token = secrets.token_urlsafe(32)
        session = UserSession(
            user_id=user.id,
            session_token=access_token,
            refresh_token=refresh_token,
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        db.session.add(session)
        db.session.commit()
        log_audit_event(user.id, "user_login", "user", user.id)
        return (
            jsonify(
                {
                    "message": "Login successful",
                    "user": user.to_dict(),
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expires_in": 86400,
                    "permissions": user.get_permissions(),
                }
            ),
            200,
        )
    except Exception as e:
        current_app.logger.error(f"Login error: {str(e)}")
        return (jsonify({"error": "Login failed"}), 500)


@user_bp.route("/api/v1/auth/logout", methods=["POST"])
@cross_origin()
@require_auth
def logout() -> Any:
    """Logout and invalidate session"""
    try:
        auth_header = request.headers.get("Authorization")
        if auth_header:
            token = auth_header.split(" ")[1]
            session = UserSession.query.filter_by(session_token=token).first()
            if session:
                session.is_active = False
                db.session.commit()
        log_audit_event(request.current_user.id, "user_logout")
        return (jsonify({"message": "Logout successful"}), 200)
    except Exception as e:
        current_app.logger.error(f"Logout error: {str(e)}")
        return (jsonify({"error": "Logout failed"}), 500)


@user_bp.route("/api/v1/auth/refresh", methods=["POST"])
@cross_origin()
def refresh_token() -> Any:
    """Refresh access token"""
    try:
        data = request.get_json()
        refresh_token = data.get("refresh_token")
        if not refresh_token:
            return (jsonify({"error": "Refresh token required"}), 400)
        session = UserSession.query.filter_by(
            refresh_token=refresh_token, is_active=True
        ).first()
        if not session or session.is_expired():
            return (jsonify({"error": "Invalid or expired refresh token"}), 401)
        user = session.user
        if not user.is_active:
            return (jsonify({"error": "User account is inactive"}), 401)
        new_access_token = generate_token(user.id)
        new_refresh_token = secrets.token_urlsafe(32)
        session.session_token = new_access_token
        session.refresh_token = new_refresh_token
        session.extend_session()
        db.session.commit()
        return (
            jsonify(
                {
                    "access_token": new_access_token,
                    "refresh_token": new_refresh_token,
                    "expires_in": 86400,
                }
            ),
            200,
        )
    except Exception as e:
        current_app.logger.error(f"Token refresh error: {str(e)}")
        return (jsonify({"error": "Token refresh failed"}), 500)


@user_bp.route("/api/v1/auth/mfa/setup", methods=["POST"])
@cross_origin()
@require_auth
def setup_mfa() -> Any:
    """Setup MFA for user"""
    try:
        user = request.current_user
        if user.mfa_enabled:
            return (jsonify({"error": "MFA is already enabled"}), 400)
        secret, backup_codes = user.setup_mfa()
        qr_url = user.get_mfa_qr_code_url()
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img_buffer = io.BytesIO()
        img.save(img_buffer, format="PNG")
        img_buffer.seek(0)
        qr_code_base64 = base64.b64encode(img_buffer.getvalue()).decode()
        db.session.commit()
        log_audit_event(user.id, "mfa_setup_initiated", "user", user.id)
        return (
            jsonify(
                {
                    "message": "MFA setup initiated",
                    "secret": secret,
                    "qr_code": f"data:image/png;base64,{qr_code_base64}",
                    "backup_codes": backup_codes,
                }
            ),
            200,
        )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"MFA setup error: {str(e)}")
        return (jsonify({"error": "MFA setup failed"}), 500)


@user_bp.route("/api/v1/auth/mfa/enable", methods=["POST"])
@cross_origin()
@require_auth
def enable_mfa() -> Any:
    """Enable MFA after verification"""
    try:
        data = request.get_json()
        token = data.get("token")
        if not token:
            return (jsonify({"error": "MFA token required"}), 400)
        user = request.current_user
        if user.mfa_enabled:
            return (jsonify({"error": "MFA is already enabled"}), 400)
        if not user.mfa_secret:
            return (jsonify({"error": "MFA setup not initiated"}), 400)
        if not user.verify_mfa_token(token):
            return (jsonify({"error": "Invalid MFA token"}), 400)
        user.mfa_enabled = True
        db.session.commit()
        log_audit_event(user.id, "mfa_enabled", "user", user.id)
        return (jsonify({"message": "MFA enabled successfully"}), 200)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"MFA enable error: {str(e)}")
        return (jsonify({"error": "MFA enable failed"}), 500)


@user_bp.route("/api/v1/auth/mfa/disable", methods=["POST"])
@cross_origin()
@require_auth
@require_mfa_if_enabled
def disable_mfa() -> Any:
    """Disable MFA"""
    try:
        data = request.get_json()
        password = data.get("password")
        if not password:
            return (jsonify({"error": "Password required to disable MFA"}), 400)
        user = request.current_user
        if not user.check_password(password):
            log_audit_event(
                user.id,
                "mfa_disable_attempt_invalid_password",
                status="failure",
                severity="warning",
            )
            return (jsonify({"error": "Invalid password"}), 401)
        user.mfa_enabled = False
        user.mfa_secret = None
        user.backup_codes = None
        db.session.commit()
        log_audit_event(user.id, "mfa_disabled", "user", user.id, severity="warning")
        return (jsonify({"message": "MFA disabled successfully"}), 200)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"MFA disable error: {str(e)}")
        return (jsonify({"error": "MFA disable failed"}), 500)


@user_bp.route("/api/v1/users/profile", methods=["GET"])
@cross_origin()
@require_auth
def get_profile() -> Any:
    """Get user profile"""
    try:
        user = request.current_user
        profile_data = user.to_dict()
        if user.profile:
            profile_data["profile"] = user.profile.to_dict()
        custom_fields: Dict[str, Any] = {}
        for cf in user.custom_fields:
            custom_fields[cf.field_name] = cf.get_typed_value()
        profile_data["custom_fields"] = custom_fields
        profile_data["roles"] = [
            ur.to_dict() for ur in user.roles if ur.is_active and (not ur.is_expired())
        ]
        profile_data["permissions"] = user.get_permissions()
        return (jsonify({"user": profile_data}), 200)
    except Exception as e:
        current_app.logger.error(f"Get profile error: {str(e)}")
        return (jsonify({"error": "Failed to get profile"}), 500)


@user_bp.route("/api/v1/users/profile", methods=["PUT"])
@cross_origin()
@require_auth
def update_profile() -> Any:
    """Update user profile"""
    try:
        data = request.get_json()
        user = request.current_user
        old_values = user.to_dict()
        user_fields = [
            "first_name",
            "last_name",
            "phone",
            "business_type",
            "company_size",
            "industry",
        ]
        for field in user_fields:
            if field in data:
                setattr(user, field, data[field])
        if not user.profile:
            user.profile = UserProfile(user_id=user.id)
        profile_fields = [
            "bio",
            "timezone",
            "language",
            "currency_preference",
            "date_format",
            "company_name",
            "company_address",
            "company_website",
            "tax_id",
            "business_registration_number",
            "fiscal_year_start",
            "accounting_method",
            "default_payment_terms",
            "email_notifications",
            "sms_notifications",
            "push_notifications",
            "marketing_emails",
            "session_timeout",
            "require_mfa_for_sensitive_actions",
        ]
        for field in profile_fields:
            if field in data:
                setattr(user.profile, field, data[field])
        custom_fields = data.get("custom_fields", {})
        for field_name, field_value in custom_fields.items():
            custom_field = UserCustomField.query.filter_by(
                user_id=user.id, field_name=field_name
            ).first()
            if custom_field:
                custom_field.field_value = str(field_value)
                custom_field.updated_at = datetime.utcnow()
            else:
                custom_field = UserCustomField(
                    user_id=user.id,
                    field_name=field_name,
                    field_value=str(field_value),
                    field_type=data.get("custom_field_types", {}).get(
                        field_name, "text"
                    ),
                )
                db.session.add(custom_field)
        db.session.commit()
        new_values = user.to_dict()
        log_audit_event(
            user.id,
            "profile_updated",
            "user",
            user.id,
            old_values=old_values,
            new_values=new_values,
        )
        return (
            jsonify(
                {"message": "Profile updated successfully", "user": user.to_dict()}
            ),
            200,
        )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Update profile error: {str(e)}")
        return (jsonify({"error": "Failed to update profile"}), 500)


@user_bp.route("/api/v1/users/roles", methods=["GET"])
@cross_origin()
@require_auth
@require_permission("users.read")
def get_user_roles() -> Any:
    """Get user roles"""
    try:
        user_id = request.args.get("user_id", request.current_user.id)
        user = User.query.get(user_id)
        if not user:
            return (jsonify({"error": "User not found"}), 404)
        roles = [
            ur.to_dict() for ur in user.roles if ur.is_active and (not ur.is_expired())
        ]
        return (jsonify({"roles": roles, "permissions": user.get_permissions()}), 200)
    except Exception as e:
        current_app.logger.error(f"Get user roles error: {str(e)}")
        return (jsonify({"error": "Failed to get user roles"}), 500)


@user_bp.route("/api/v1/users/roles", methods=["POST"])
@cross_origin()
@require_auth
@require_permission("users.update")
def assign_role() -> Any:
    """Assign role to user"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        role_id = data.get("role_id")
        expires_at = data.get("expires_at")
        if not user_id or not role_id:
            return (jsonify({"error": "user_id and role_id are required"}), 400)
        user = User.query.get(user_id)
        role = Role.query.get(role_id)
        if not user or not role:
            return (jsonify({"error": "User or role not found"}), 404)
        existing_role = UserRole.query.filter_by(
            user_id=user_id, role_id=role_id, is_active=True
        ).first()
        if existing_role and (not existing_role.is_expired()):
            return (jsonify({"error": "Role already assigned to user"}), 409)
        user_role = UserRole(
            user_id=user_id,
            role_id=role_id,
            granted_by=request.current_user.id,
            expires_at=datetime.fromisoformat(expires_at) if expires_at else None,
        )
        db.session.add(user_role)
        db.session.commit()
        log_audit_event(
            request.current_user.id,
            "role_assigned",
            "user_role",
            user_role.id,
            new_values={"user_id": user_id, "role_id": role_id},
        )
        return (
            jsonify(
                {
                    "message": "Role assigned successfully",
                    "user_role": user_role.to_dict(),
                }
            ),
            201,
        )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Assign role error: {str(e)}")
        return (jsonify({"error": "Failed to assign role"}), 500)


@user_bp.route("/api/v1/users/audit-logs", methods=["GET"])
@cross_origin()
@require_auth
@require_permission("audit_logs.read")
def get_audit_logs() -> Any:
    """Get audit logs"""
    try:
        user_id = request.args.get("user_id")
        action = request.args.get("action")
        resource_type = request.args.get("resource_type")
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        page = int(request.args.get("page", 1))
        per_page = min(int(request.args.get("per_page", 50)), 100)
        query = AuditLog.query
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        if action:
            query = query.filter(AuditLog.action.ilike(f"%{action}%"))
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)
        if start_date:
            query = query.filter(
                AuditLog.created_at >= datetime.fromisoformat(start_date)
            )
        if end_date:
            query = query.filter(
                AuditLog.created_at <= datetime.fromisoformat(end_date)
            )
        query = query.order_by(AuditLog.created_at.desc())
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        return (
            jsonify(
                {
                    "audit_logs": [log.to_dict() for log in paginated.items],
                    "pagination": {
                        "page": page,
                        "per_page": per_page,
                        "total": paginated.total,
                        "pages": paginated.pages,
                        "has_next": paginated.has_next,
                        "has_prev": paginated.has_prev,
                    },
                }
            ),
            200,
        )
    except Exception as e:
        current_app.logger.error(f"Get audit logs error: {str(e)}")
        return (jsonify({"error": "Failed to get audit logs"}), 500)


@user_bp.route("/api/v1/users/sessions", methods=["GET"])
@cross_origin()
@require_auth
def get_user_sessions() -> Any:
    """Get user sessions"""
    try:
        user = request.current_user
        sessions = (
            UserSession.query.filter_by(user_id=user.id, is_active=True)
            .order_by(UserSession.last_activity.desc())
            .all()
        )
        return (jsonify({"sessions": [session.to_dict() for session in sessions]}), 200)
    except Exception as e:
        current_app.logger.error(f"Get sessions error: {str(e)}")
        return (jsonify({"error": "Failed to get sessions"}), 500)


@user_bp.route("/api/v1/users/sessions/<session_id>", methods=["DELETE"])
@cross_origin()
@require_auth
def revoke_session(session_id: Any) -> Any:
    """Revoke user session"""
    try:
        session = UserSession.query.filter_by(
            id=session_id, user_id=request.current_user.id
        ).first()
        if not session:
            return (jsonify({"error": "Session not found"}), 404)
        session.is_active = False
        db.session.commit()
        log_audit_event(
            request.current_user.id, "session_revoked", "user_session", session_id
        )
        return (jsonify({"message": "Session revoked successfully"}), 200)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Revoke session error: {str(e)}")
        return (jsonify({"error": "Failed to revoke session"}), 500)


@user_bp.route("/health", methods=["GET"])
@cross_origin()
def health_check() -> Any:
    """Health check endpoint"""
    try:
        db.session.execute("SELECT 1")
        return (
            jsonify(
                {
                    "status": "healthy",
                    "service": "user-service",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            200,
        )
    except Exception as e:
        return (
            jsonify(
                {
                    "status": "unhealthy",
                    "service": "user-service",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            503,
        )
