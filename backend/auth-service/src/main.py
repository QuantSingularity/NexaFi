import base64
import hashlib
import json
import os
import secrets
import sys
from datetime import datetime, timedelta
from typing import Any, Optional
from urllib.parse import urlencode

import bcrypt
from flask import Flask, g, jsonify, redirect, request, url_for
from flask_cors import CORS

# --- External System Imports (Mocked paths assumed correct based on context) ---
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "shared"))

from audit.audit_logger import AuditEventType, AuditSeverity, audit_action, audit_logger
from database.manager import BaseModel, initialize_database
from middleware.auth import require_auth

# Assuming User model exists based on SQL references, added import
from models.user import AccessToken, AuthorizationCode, OAuthClient, User
from nexafi_logging.logger import get_logger, setup_request_logging
from open_banking_compliance import FAPI2SecurityProfile
from security import (
    AdvancedEncryption,
    FraudDetectionEngine,
    MultiFactorAuthentication,
    SecureSessionManager,
    SecurityEvent,
    SecurityEventType,
    SecurityLevel,
    SecurityMonitor,
    ThreatLevel,
)
from validation_schemas.schemas import (
    SanitizationMixin,
    Schema,
    fields,
    validate,
    validate_json_request,
)

# --- Configuration & Setup ---

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "nexafi-auth-service-secret-key-2024"
)

# Optimization: Restrict CORS origins in production
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*")
CORS(
    app,
    origins=ALLOWED_ORIGINS,
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-User-ID",
        "X-FAPI-Auth-Date",
        "X-FAPI-Customer-IP-Address",
        "X-FAPI-Interaction-ID",
        "DPoP",
    ],
)

setup_request_logging(app)
logger = get_logger("auth_service")

# --- Database & Security Initialization ---

db_path = os.path.join(os.path.dirname(__file__), "database", "auth.db")
os.makedirs(os.path.dirname(db_path), exist_ok=True)
db_manager, migration_manager = initialize_database(db_path)
BaseModel.set_db_manager(db_manager)

# Initialize Security Components
encryption = AdvancedEncryption()
security_monitor = SecurityMonitor(db_manager)
fraud_engine = FraudDetectionEngine(db_manager)
mfa_manager = MultiFactorAuthentication(db_manager)
session_manager = SecureSessionManager(db_manager, encryption)

# Load keys safely
PRIVATE_KEY_PATH = os.environ.get("FAPI_PRIVATE_KEY", "/home/user/keys/private_key.pem")
PUBLIC_KEY_PATH = os.environ.get("FAPI_PUBLIC_KEY", "/home/user/keys/public_key.pem")

fapi_security = FAPI2SecurityProfile(
    private_key_path=PRIVATE_KEY_PATH,
    public_key_path=PUBLIC_KEY_PATH,
)

# --- Migrations ---


def run_migrations():
    """Execute database migrations on startup."""
    auth_migrations = {
        "008_create_oauth_clients_table": {
            "description": "Create OAuth 2.1 clients table",
            "sql": """
                CREATE TABLE IF NOT EXISTS oauth_clients (
                    client_id TEXT PRIMARY KEY,
                    client_secret_hash TEXT,
                    client_name TEXT NOT NULL,
                    client_type TEXT NOT NULL DEFAULT 'confidential',
                    redirect_uris TEXT NOT NULL,
                    scope TEXT DEFAULT 'openid profile',
                    grant_types TEXT DEFAULT 'authorization_code',
                    response_types TEXT DEFAULT 'code',
                    token_endpoint_auth_method TEXT DEFAULT 'client_secret_basic',
                    jwks_uri TEXT,
                    software_statement TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE
                );

                CREATE TABLE IF NOT EXISTS oauth_authorization_codes (
                    code TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    redirect_uri TEXT NOT NULL,
                    scope TEXT,
                    code_challenge TEXT,
                    code_challenge_method TEXT DEFAULT 'S256',
                    expires_at TIMESTAMP NOT NULL,
                    used BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES oauth_clients(client_id),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS oauth_access_tokens (
                    token_id TEXT PRIMARY KEY,
                    access_token_hash TEXT NOT NULL,
                    refresh_token_hash TEXT,
                    client_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    scope TEXT,
                    expires_at TIMESTAMP NOT NULL,
                    refresh_expires_at TIMESTAMP,
                    is_revoked BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES oauth_clients(client_id),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE INDEX IF NOT EXISTS idx_oauth_codes_client_id ON oauth_authorization_codes(client_id);
                CREATE INDEX IF NOT EXISTS idx_oauth_codes_user_id ON oauth_authorization_codes(user_id);
                CREATE INDEX IF NOT EXISTS idx_oauth_tokens_client_id ON oauth_access_tokens(client_id);
                CREATE INDEX IF NOT EXISTS idx_oauth_tokens_user_id ON oauth_access_tokens(user_id);
            """,
        },
        "009_create_device_registration_table": {
            "description": "Create device registration table",
            "sql": """
                CREATE TABLE IF NOT EXISTS registered_devices (
                    device_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    device_name TEXT NOT NULL,
                    device_type TEXT NOT NULL,
                    device_fingerprint TEXT,
                    public_key TEXT,
                    registration_token TEXT,
                    is_trusted BOOLEAN DEFAULT FALSE,
                    last_used TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE INDEX IF NOT EXISTS idx_registered_devices_user_id ON registered_devices(user_id);
                CREATE INDEX IF NOT EXISTS idx_registered_devices_fingerprint ON registered_devices(device_fingerprint);
            """,
        },
    }

    for version, migration in auth_migrations.items():
        try:
            migration_manager.apply_migration(
                version, migration["description"], migration["sql"]
            )
        except Exception as e:
            logger.error(f"Migration failed for {version}: {str(e)}")
            # In production, you might want to exit here


# --- Schemas ---


class LoginSchema(SanitizationMixin, Schema):
    username = fields.Str(required=True, validate=validate.Length(min=3, max=50))
    password = fields.Str(required=True, validate=validate.Length(min=8, max=128))
    device_fingerprint = fields.Str(required=False)
    remember_me = fields.Bool(required=False, default=False)


class MFASetupSchema(SanitizationMixin, Schema):
    method = fields.Str(required=True, validate=validate.OneOf(["totp", "sms"]))
    phone_number = fields.Str(
        required=False, validate=validate.Regexp(r"^\+[1-9]\d{1,14}$")
    )


class MFAVerifySchema(SanitizationMixin, Schema):
    token = fields.Str(required=True, validate=validate.Length(min=4, max=10))
    method = fields.Str(
        required=True, validate=validate.OneOf(["totp", "sms", "backup_code"])
    )


class OAuth2AuthorizeSchema(SanitizationMixin, Schema):
    response_type = fields.Str(required=True, validate=validate.OneOf(["code"]))
    client_id = fields.Str(required=True)
    redirect_uri = fields.Str(required=True, validate=validate.URL())
    scope = fields.Str(required=False, default="openid profile")
    state = fields.Str(required=False)
    code_challenge = fields.Str(required=False)
    code_challenge_method = fields.Str(
        required=False, validate=validate.OneOf(["S256", "plain"])
    )


class OAuth2TokenSchema(SanitizationMixin, Schema):
    grant_type = fields.Str(
        required=True, validate=validate.OneOf(["authorization_code", "refresh_token"])
    )
    code = fields.Str(required=False)
    redirect_uri = fields.Str(required=False)
    client_id = fields.Str(required=True)
    client_secret = fields.Str(required=False)
    code_verifier = fields.Str(required=False)
    refresh_token = fields.Str(required=False)


# --- Helper Functions ---


def generate_secure_token(length: int = 32) -> str:
    """Generate cryptographically secure token"""
    return secrets.token_urlsafe(length)


def hash_token(token: str) -> str:
    """Hash token for storage"""
    return hashlib.sha256(token.encode()).hexdigest()


def verify_client_authentication(
    client_id: str, client_secret: Optional[str] = None
) -> bool:
    """Verify OAuth client authentication"""
    try:
        client = OAuthClient.find_by_field("client_id", client_id)
        if not client or not client.is_active:
            return False

        if client.client_type == "public":
            return True

        if not client_secret:
            return False

        return bcrypt.checkpw(
            client_secret.encode(), client.client_secret_hash.encode()
        )
    except Exception as e:
        logger.error(f"Client auth error: {e}")
        return False


def authenticate_user_credentials(username: str, password: str) -> Optional[object]:
    """
    Authenticate user against the database.
    Replaces hardcoded check.
    """
    try:
        user = User.find_by_field("email", username)  # Assuming username is email
        if not user:
            # Timing attack mitigation
            bcrypt.checkpw(password.encode(), b"$2b$12$......................")
            return None

        if bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            return user
        return None
    except Exception as e:
        logger.error(f"User auth error: {e}")
        return None


# --- Routes ---


@app.route("/api/v1/health", methods=["GET"])
def health_check() -> Any:
    """Health check endpoint"""
    return jsonify(
        {
            "status": "healthy",
            "service": "auth-service",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "features": {
                "oauth2_1": True,
                "fapi_2_0": True,
                "mfa": True,
                "device_registration": True,
                "fraud_detection": True,
            },
        }
    )


@app.route("/api/v1/auth/login", methods=["POST"])
@validate_json_request(LoginSchema)
@audit_action(AuditEventType.USER_LOGIN, "login_attempt", severity=AuditSeverity.MEDIUM)
def login() -> Any:
    """Login with fraud detection"""
    data = request.validated_data  # type: ignore[attr-defined]

    # 1. Fraud Detection Analysis
    risk_score, risk_factors = fraud_engine.analyze_login_behavior(
        data["username"],
        request.remote_addr,
        request.headers.get("User-Agent", ""),
        data.get("device_fingerprint"),
    )

    # 2. Log Security Event
    event = SecurityEvent(
        event_type=SecurityEventType.LOGIN_ATTEMPT,
        user_id=data["username"],
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent", ""),
        timestamp=datetime.utcnow(),
        details={
            "risk_score": risk_score,
            "risk_factors": risk_factors,
            "device_fingerprint": data.get("device_fingerprint"),
        },
        threat_level=(
            ThreatLevel.HIGH
            if risk_score > 70
            else ThreatLevel.MODERATE if risk_score > 40 else ThreatLevel.LOW
        ),
    )
    security_monitor.log_security_event(event)

    # 3. Block High Risk
    if risk_score > 80:
        return (
            jsonify(
                {
                    "error": "account_locked",
                    "message": "Account temporarily locked due to suspicious activity",
                    "requires_verification": True,
                }
            ),
            423,
        )

    # 4. Credential Verification
    user = authenticate_user_credentials(data["username"], data["password"])

    if user:
        user_id = str(user.id)

        # Determine Security Level based on Risk
        if risk_score > 50:
            security_level = SecurityLevel.HIGH
        elif risk_score > 30:
            security_level = SecurityLevel.MEDIUM
        else:
            security_level = SecurityLevel.LOW

        session_id = session_manager.create_session(
            user_id,
            request.remote_addr,
            request.headers.get("User-Agent"),
            data.get("device_fingerprint"),
            security_level,
        )

        mfa_required = risk_score > 40 or security_level in [
            SecurityLevel.HIGH,
            SecurityLevel.CRITICAL,
        ]

        audit_logger.log_event(
            AuditEventType.USER_LOGIN,
            "login_successful",
            user_id=user_id,
            details={
                "session_id": session_id,
                "risk_score": risk_score,
                "mfa_required": mfa_required,
            },
            severity=AuditSeverity.MEDIUM,
        )

        response_data = {
            "success": True,
            "session_id": session_id,
            "user_id": user_id,
            "security_level": security_level.value,
            "mfa_required": mfa_required,
            "risk_score": risk_score,
        }

        if mfa_required:
            response_data["next_step"] = "mfa_verification"
            response_data["available_methods"] = ["totp", "sms"]

        return jsonify(response_data)
    else:
        audit_logger.log_event(
            AuditEventType.USER_LOGIN,
            "login_failed",
            user_id=data["username"],
            details={"reason": "invalid_credentials"},
            severity=AuditSeverity.HIGH,
        )
        return (
            jsonify(
                {
                    "error": "invalid_credentials",
                    "message": "Invalid username or password",
                }
            ),
            401,
        )


@app.route("/api/v1/auth/mfa/setup", methods=["POST"])
@require_auth
@validate_json_request(MFASetupSchema)
@audit_action(AuditEventType.USER_UPDATE, "mfa_setup", severity=AuditSeverity.HIGH)
def setup_mfa() -> Any:
    """Setup Multi-Factor Authentication"""
    data = request.validated_data  # type: ignore[attr-defined]
    user_id = g.user_id

    # Retrieve user email for TOTP issuer (optimization)
    user = User.find_by_field("id", user_id)
    user_email = user.email if user else f"{user_id}@nexafi.com"

    if data["method"] == "totp":
        secret, provisioning_uri, backup_codes = mfa_manager.setup_totp(
            user_id, user_email
        )
        return jsonify(
            {
                "method": "totp",
                "secret": secret,
                "qr_code_uri": provisioning_uri,
                "backup_codes": backup_codes,
                "message": "Scan QR code with authenticator app",
            }
        )
    elif data["method"] == "sms":
        phone_number = data.get("phone_number")
        if not phone_number:
            return (
                jsonify(
                    {
                        "error": "phone_number_required",
                        "message": "Phone number required for SMS setup",
                    }
                ),
                400,
            )

        # Trigger SMS sending logic here (Mocked)
        # sms_service.send_verification(phone_number)

        return jsonify(
            {
                "method": "sms",
                "phone_number": phone_number,
                "message": "SMS MFA setup initiated",
            }
        )


@app.route("/api/v1/auth/mfa/verify", methods=["POST"])
@require_auth
@validate_json_request(MFAVerifySchema)
@audit_action(
    AuditEventType.USER_LOGIN, "mfa_verification", severity=AuditSeverity.HIGH
)
def verify_mfa() -> Any:
    """Verify Multi-Factor Authentication"""
    data = request.validated_data  # type: ignore[attr-defined]
    user_id = g.user_id
    session_id = g.session_id
    is_verified = False

    try:
        if data["method"] == "totp":
            is_verified = mfa_manager.verify_totp(
                user_id,
                data["token"],
                request.remote_addr,
                request.headers.get("User-Agent"),
            )
        elif data["method"] == "backup_code":
            is_verified = mfa_manager.verify_backup_code(
                user_id,
                data["token"],
                request.remote_addr,
                request.headers.get("User-Agent"),
            )
        # Added SMS verification logic branch
        elif data["method"] == "sms":
            is_verified = mfa_manager.verify_sms(user_id, data["token"])
    except Exception as e:
        logger.error(f"MFA verification error: {e}")
        return (
            jsonify({"error": "verification_error", "message": "Internal error"}),
            500,
        )

    if is_verified:
        session_manager.mark_mfa_verified(session_id)
        audit_logger.log_event(
            AuditEventType.USER_LOGIN,
            "mfa_verification_successful",
            user_id=user_id,
            details={"method": data["method"]},
            severity=AuditSeverity.HIGH,
        )
        return jsonify(
            {
                "success": True,
                "message": "MFA verification successful",
                "session_verified": True,
            }
        )
    else:
        audit_logger.log_event(
            AuditEventType.USER_LOGIN,
            "mfa_verification_failed",
            user_id=user_id,
            details={"method": data["method"]},
            severity=AuditSeverity.HIGH,
        )
        return jsonify({"error": "invalid_token", "message": "Invalid MFA token"}), 401


@app.route("/oauth2/authorize", methods=["GET", "POST"])
def oauth2_authorize() -> Any:
    """OAuth 2.1 Authorization Endpoint with FAPI 2.0 compliance"""
    if request.method == "GET":
        data = {
            "response_type": request.args.get("response_type"),
            "client_id": request.args.get("client_id"),
            "redirect_uri": request.args.get("redirect_uri"),
            "scope": request.args.get("scope", "openid profile"),
            "state": request.args.get("state"),
            "code_challenge": request.args.get("code_challenge"),
            "code_challenge_method": request.args.get("code_challenge_method", "S256"),
        }
    else:
        data = request.validated_data  # type: ignore[attr-defined]

    client = OAuthClient.find_by_field("client_id", data["client_id"])
    if not client or not client.is_active:
        return (
            jsonify(
                {
                    "error": "invalid_client",
                    "error_description": "Invalid client identifier",
                }
            ),
            400,
        )

    try:
        allowed_uris = json.loads(client.redirect_uris)
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in redirect_uris for client {data['client_id']}")
        return jsonify({"error": "server_error"}), 500

    if data["redirect_uri"] not in allowed_uris:
        return (
            jsonify(
                {
                    "error": "invalid_request",
                    "error_description": "Invalid redirect URI",
                }
            ),
            400,
        )

    # Optimization: Check for existing valid session before redirecting to login
    auth_header = request.headers.get("Authorization")
    user_id = None

    # Simple Bearer check (Real implementation would validate the session token against SecureSessionManager)
    if auth_header and auth_header.startswith("Bearer "):
        session_token = auth_header.split(" ")[1]
        session = session_manager.validate_session(session_token)
        if session and session.is_valid:
            user_id = session.user_id

    if not user_id:
        # Redirect to login with original params preserved
        login_url = url_for(
            "login",
            client_id=data["client_id"],
            redirect_uri=data["redirect_uri"],
            state=data.get("state"),
            scope=data.get("scope"),
            code_challenge=data.get("code_challenge"),
        )
        return redirect(login_url)

    # User is authenticated, generate code
    auth_code = generate_secure_token(32)
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    code_record = AuthorizationCode(
        code=auth_code,
        client_id=data["client_id"],
        user_id=user_id,
        redirect_uri=data["redirect_uri"],
        scope=data["scope"],
        code_challenge=data.get("code_challenge"),
        code_challenge_method=data.get("code_challenge_method"),
        expires_at=expires_at,
    )
    code_record.save()

    redirect_params = {"code": auth_code}
    state_param = data.get("state")
    if state_param:
        redirect_params["state"] = state_param

    redirect_url = f"{data['redirect_uri']}?{urlencode(redirect_params)}"
    return redirect(redirect_url)


@app.route("/oauth2/token", methods=["POST"])
@validate_json_request(OAuth2TokenSchema)
def oauth2_token() -> Any:
    """OAuth 2.1 Token Endpoint with FAPI 2.0 compliance"""
    data = request.validated_data  # type: ignore[attr-defined]
    client_secret = data.get("client_secret")

    if not verify_client_authentication(data["client_id"], client_secret):
        return (
            jsonify(
                {
                    "error": "invalid_client",
                    "error_description": "Client authentication failed",
                }
            ),
            401,
        )

    if data["grant_type"] == "authorization_code":
        code_record = AuthorizationCode.find_by_field("code", data["code"])

        # Security: Invalidate used codes immediately (done later via .used=True)
        if not code_record or code_record.used:
            return (
                jsonify(
                    {
                        "error": "invalid_grant",
                        "error_description": "Invalid or expired authorization code",
                    }
                ),
                400,
            )

        # Timezone aware comparison
        code_expiry = datetime.fromisoformat(str(code_record.expires_at))
        if datetime.utcnow() > code_expiry:
            return (
                jsonify(
                    {
                        "error": "invalid_grant",
                        "error_description": "Authorization code expired",
                    }
                ),
                400,
            )

        # PKCE Verification
        if code_record.code_challenge:
            code_verifier = data.get("code_verifier")
            if not code_verifier:
                return (
                    jsonify(
                        {
                            "error": "invalid_request",
                            "error_description": "Code verifier required",
                        }
                    ),
                    400,
                )

            if code_record.code_challenge_method == "S256":
                challenge = (
                    base64.urlsafe_b64encode(
                        hashlib.sha256(code_verifier.encode()).digest()
                    )
                    .decode()
                    .rstrip("=")
                )
            else:  # plain
                challenge = code_verifier

            if challenge != code_record.code_challenge:
                return (
                    jsonify(
                        {
                            "error": "invalid_grant",
                            "error_description": "Invalid code verifier",
                        }
                    ),
                    400,
                )

        # Mark code as used
        code_record.used = True
        code_record.save()

        # Generate Tokens
        access_token = generate_secure_token(32)
        refresh_token = generate_secure_token(32)

        token_record = AccessToken(
            token_id=generate_secure_token(16),
            access_token_hash=hash_token(access_token),
            refresh_token_hash=hash_token(refresh_token),
            client_id=data["client_id"],
            user_id=code_record.user_id,
            scope=code_record.scope,
            expires_at=datetime.utcnow() + timedelta(hours=1),
            refresh_expires_at=datetime.utcnow() + timedelta(days=30),
        )
        token_record.save()

        # Generate ID Token (JWT)
        id_token_payload = {
            "sub": code_record.user_id,
            "aud": data["client_id"],
            "iss": "https://auth.nexafi.com",
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.utcnow().timestamp()),
            "auth_time": int(datetime.utcnow().timestamp()),
            # Add nonce if present in initial request (requires storing nonce in auth code)
        }

        id_token = fapi_security.create_signed_jwt(
            id_token_payload, data["client_id"], "https://auth.nexafi.com"
        )

        return jsonify(
            {
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": refresh_token,
                "id_token": id_token,
                "scope": code_record.scope,
            }
        )

    elif data["grant_type"] == "refresh_token":
        refresh_token = data.get("refresh_token")
        if not refresh_token:
            return (
                jsonify(
                    {
                        "error": "invalid_request",
                        "error_description": "Refresh token required",
                    }
                ),
                400,
            )

        token_record = AccessToken.find_by_field(
            "refresh_token_hash", hash_token(refresh_token)
        )

        if not token_record or token_record.is_revoked:
            return (
                jsonify(
                    {
                        "error": "invalid_grant",
                        "error_description": "Invalid refresh token",
                    }
                ),
                400,
            )

        refresh_expiry = datetime.fromisoformat(str(token_record.refresh_expires_at))
        if datetime.utcnow() > refresh_expiry:
            return (
                jsonify(
                    {
                        "error": "invalid_grant",
                        "error_description": "Refresh token expired",
                    }
                ),
                400,
            )

        # Refresh Rotation: Issue new Access Token AND new Refresh Token
        new_access_token = generate_secure_token(32)
        new_refresh_token = generate_secure_token(
            32
        )  # Optional but recommended for high security

        token_record.access_token_hash = hash_token(new_access_token)
        token_record.refresh_token_hash = hash_token(
            new_refresh_token
        )  # Rotate refresh token
        token_record.expires_at = datetime.utcnow() + timedelta(hours=1)
        token_record.save()

        return jsonify(
            {
                "access_token": new_access_token,
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": new_refresh_token,  # Return the rotated token
                "scope": token_record.scope,
            }
        )


@app.route("/oauth2/userinfo", methods=["GET"])
def oauth2_userinfo() -> Any:
    """OAuth 2.1 UserInfo Endpoint"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return (
            jsonify(
                {
                    "error": "invalid_token",
                    "error_description": "Invalid or missing access token",
                }
            ),
            401,
        )

    access_token = auth_header[7:]
    token_record = AccessToken.find_by_field(
        "access_token_hash", hash_token(access_token)
    )

    if not token_record or token_record.is_revoked:
        return (
            jsonify(
                {"error": "invalid_token", "error_description": "Invalid access token"}
            ),
            401,
        )

    token_expiry = datetime.fromisoformat(str(token_record.expires_at))
    if datetime.utcnow() > token_expiry:
        return (
            jsonify(
                {"error": "invalid_token", "error_description": "Access token expired"}
            ),
            401,
        )

    # Fetch real user data
    user = User.find_by_field("id", token_record.user_id)
    if not user:
        return (
            jsonify({"error": "invalid_token", "error_description": "User not found"}),
            401,
        )

    return jsonify(
        {
            "sub": user.id,
            "name": user.full_name,  # Assumed field
            "email": user.email,
            "email_verified": user.email_verified,  # Assumed field
            "preferred_username": user.username,
        }
    )


@app.route("/api/v1/auth/logout", methods=["POST"])
@require_auth
@audit_action(AuditEventType.USER_LOGOUT, "logout", severity=AuditSeverity.LOW)
def logout() -> Any:
    """Secure logout"""
    user_id = g.user_id
    session_id = g.session_id

    session_manager.invalidate_session(session_id)

    # Optional: Revoke OAuth tokens associated with this session if applicable

    audit_logger.log_event(
        AuditEventType.USER_LOGOUT,
        "logout_successful",
        user_id=user_id,
        details={"session_id": session_id},
        severity=AuditSeverity.LOW,
    )
    return jsonify({"success": True, "message": "Logged out successfully"})


if __name__ == "__main__":
    # Ensure directories exist
    os.makedirs(os.path.join(os.path.dirname(__file__), "database"), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), "keys"), exist_ok=True)

    # Run migrations
    run_migrations()

    # Run App (Debug disabled for safety unless explicitly requested)
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    app.run(host="0.0.0.0", port=5011, debug=debug_mode)
