"""
Open Banking API Gateway
Implements PSD2 compliant API gateway with FAPI 2.0 security
"""

import os
import sys
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Dict

from flask import Flask, g, jsonify, request
from flask_cors import CORS

# -------------------------------------------------------------------------
# Path Configuration
# -------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Add shared directory to path
sys.path.append(os.path.join(BASE_DIR, "..", "..", "shared"))

from audit.audit_logger import AuditEventType, AuditSeverity, audit_action, audit_logger
from database.manager import initialize_database
from middleware.auth import require_auth, require_permission

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from nexafi_logging.logger import get_logger, setup_request_logging
from open_banking_compliance import (
    AuthenticationMethod,
    ConsentStatus,
    FAPI2SecurityProfile,
    OpenBankingAPIValidator,
    PSD2ConsentManager,
    SCAManager,
    TransactionRiskAnalysis,
)
from security import (
    AdvancedEncryption,
    FraudDetectionEngine,
    MultiFactorAuthentication,
    SecurityEvent,
    SecurityEventType,
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

# -------------------------------------------------------------------------
# App Configuration & Initialization
# -------------------------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "nexafi-default-secret-change-in-production"
)

# Strict CORS policy for FAPI compliance
CORS(
    app,
    origins=os.environ.get("ALLOWED_ORIGINS", "*"),
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-User-ID",
        "X-FAPI-Auth-Date",
        "X-FAPI-Customer-IP-Address",
        "X-FAPI-Interaction-ID",
        "DPoP",
        "TPP-Signature-Certificate",
        "PSU-ID",
        "Consent-ID",
    ],
)

setup_request_logging(app)
logger = get_logger("open_banking_gateway")

# Database Setup
DB_PATH = os.environ.get(
    "DB_PATH", os.path.join(BASE_DIR, "database", "open_banking.db")
)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
db_manager, migration_manager = initialize_database(DB_PATH)

# Security Components
KEY_DIR = os.environ.get("KEY_DIR", os.path.join(BASE_DIR, "keys"))
encryption = AdvancedEncryption()
security_monitor = SecurityMonitor(db_manager)
fraud_engine = FraudDetectionEngine(db_manager)
mfa_manager = MultiFactorAuthentication(db_manager)

# FAPI Profile Setup with dynamic paths
fapi_security = FAPI2SecurityProfile(
    private_key_path=os.path.join(KEY_DIR, "private_key.pem"),
    public_key_path=os.path.join(KEY_DIR, "public_key.pem"),
)

consent_manager = PSD2ConsentManager(db_manager)
sca_manager = SCAManager(db_manager)

# -------------------------------------------------------------------------
# Schemas
# -------------------------------------------------------------------------


class AmountSchema(Schema):
    """Reusable schema for monetary amounts"""

    amount = fields.String(
        required=True,
        validate=validate.Regexp(r"^\d+(\.\d{1,2})?$"),
        description="Amount in major units (e.g. 10.50)",
    )
    currency = fields.String(
        required=True,
        validate=validate.Length(equal=3),
        description="ISO 4217 Currency Code",
    )


class AccountReferenceSchema(Schema):
    """Reusable schema for account references"""

    iban = fields.String(required=False, validate=validate.Length(min=15, max=34))
    bban = fields.String(required=False)
    pan = fields.String(required=False)
    maskedPan = fields.String(required=False)
    msisdn = fields.String(required=False)
    currency = fields.String(required=False, validate=validate.Length(equal=3))


class ConsentRequestSchema(SanitizationMixin, Schema):
    access = fields.Dict(required=True)
    recurringIndicator = fields.Bool(required=False, default=False)
    validUntil = fields.DateTime(required=False)
    frequencyPerDay = fields.Int(
        required=False, default=4, validate=validate.Range(min=1, max=10)
    )
    combinedServiceIndicator = fields.Bool(required=False, default=False)


class PaymentInitiationSchema(SanitizationMixin, Schema):
    instructedAmount = fields.Nested(AmountSchema, required=True)
    debtorAccount = fields.Nested(AccountReferenceSchema, required=True)
    creditorAccount = fields.Nested(AccountReferenceSchema, required=True)
    creditorName = fields.Str(required=True, validate=validate.Length(min=1, max=70))
    remittanceInformationUnstructured = fields.Str(
        required=False, validate=validate.Length(max=140)
    )


class SCAInitiationSchema(SanitizationMixin, Schema):
    scaMethod = fields.Str(
        required=True,
        validate=validate.OneOf(
            [
                "sms_otp",
                "push_notification",
                "biometric",
                "hardware_token",
                "mobile_app",
            ]
        ),
    )
    psuMessage = fields.Str(required=False, validate=validate.Length(max=500))


# -------------------------------------------------------------------------
# Decorators
# -------------------------------------------------------------------------


def validate_tpp_certificate(f: Any) -> Any:
    """Decorator to validate TPP eIDAS certificate and extract roles"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        tpp_cert = request.headers.get("TPP-Signature-Certificate")

        if not tpp_cert:
            return (
                jsonify(
                    {
                        "error": "invalid_request",
                        "error_description": "TPP certificate header missing",
                    }
                ),
                400,
            )

        is_valid, cert_info = OpenBankingAPIValidator.validate_tpp_certificate(tpp_cert)

        if not is_valid:
            return (
                jsonify(
                    {
                        "error": "invalid_client",
                        "error_description": "Invalid or revoked TPP certificate",
                    }
                ),
                401,
            )

        # Store TPP context in Flask global
        g.tpp_id = cert_info["organization_id"]
        g.tpp_name = cert_info["organization_name"]
        g.tpp_roles = cert_info["roles"]

        return f(*args, **kwargs)

    return decorated_function


def validate_fapi_headers(f: Any) -> Any:
    """Decorator to enforce FAPI 2.0 header requirements"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        is_valid, errors = OpenBankingAPIValidator.validate_fapi_headers(
            dict(request.headers)
        )
        if not is_valid:
            return (
                jsonify(
                    {
                        "error": "invalid_request",
                        "error_description": f"FAPI compliance failed: {', '.join(errors)}",
                    }
                ),
                400,
            )
        return f(*args, **kwargs)

    return decorated_function


def log_security_event(
    event_type: SecurityEventType, threat_level: ThreatLevel = ThreatLevel.LOW
) -> Any:
    """Decorator for comprehensive security telemetry"""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Use perf_counter for high precision timing
            start_time = time.perf_counter()
            user_id = getattr(g, "user_id", request.headers.get("PSU-ID"))

            try:
                result = f(*args, **kwargs)

                # Log successful access
                duration = time.perf_counter() - start_time
                event = SecurityEvent(
                    event_type=event_type,
                    user_id=user_id,
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get("User-Agent", ""),
                    timestamp=datetime.now(timezone.utc),
                    details={
                        "endpoint": request.endpoint,
                        "method": request.method,
                        "tpp_id": getattr(g, "tpp_id", None),
                        "response_time_ms": round(duration * 1000, 2),
                        "status_code": result[1] if isinstance(result, tuple) else 200,
                    },
                    threat_level=threat_level,
                    session_id=getattr(g, "session_id", None),
                )
                security_monitor.log_security_event(event)
                return result

            except Exception as e:
                # Log security exception/anomaly
                duration = time.perf_counter() - start_time
                event = SecurityEvent(
                    event_type=SecurityEventType.SECURITY_VIOLATION,
                    user_id=user_id,
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get("User-Agent", ""),
                    timestamp=datetime.now(timezone.utc),
                    details={
                        "endpoint": request.endpoint,
                        "method": request.method,
                        "error": str(e),
                        "tpp_id": getattr(g, "tpp_id", None),
                        "response_time_ms": round(duration * 1000, 2),
                    },
                    threat_level=ThreatLevel.HIGH,
                    session_id=getattr(g, "session_id", None),
                )
                security_monitor.log_security_event(event)
                raise  # Re-raise for the global error handler

        return decorated_function

    return decorator


# -------------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------------


@app.route("/api/v1/health", methods=["GET"])
def health_check() -> Any:
    """Service health and compliance status"""
    return jsonify(
        {
            "status": "healthy",
            "service": "open-banking-gateway",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.1",
            "compliance": {"psd2": True, "fapi_2_0": True, "sca_ready": True},
        }
    )


@app.route("/api/v1/consents", methods=["POST"])
@validate_tpp_certificate
@validate_fapi_headers
@validate_json_request(ConsentRequestSchema)
@log_security_event(SecurityEventType.DATA_ACCESS, ThreatLevel.MODERATE)
@audit_action(
    AuditEventType.USER_UPDATE,
    "consent_creation_requested",
    severity=AuditSeverity.HIGH,
)
def create_consent() -> Any:
    """Create PSD2 consent (Account Information Service)"""
    data = request.validated_data

    # Check TPP Roles
    if "PSP_AI" not in g.tpp_roles:
        return (
            jsonify(
                {
                    "error": "unauthorized_client",
                    "error_description": "TPP missing role: Account Information Service (PSP_AI)",
                }
            ),
            403,
        )

    psu_id = request.headers.get("PSU-ID")
    if not psu_id:
        return (
            jsonify(
                {
                    "error": "invalid_request",
                    "error_description": "PSU-ID header is required",
                }
            ),
            400,
        )

    # Handle Date Parsing
    valid_until = data.get("validUntil")
    if valid_until and isinstance(valid_until, str):
        # Marshmallow usually returns datetime objects, but ensuring safety
        valid_until = datetime.fromisoformat(valid_until.replace("Z", "+00:00"))

    consent = consent_manager.create_consent(
        psu_id=psu_id,
        tpp_id=g.tpp_id,
        access_data=data["access"],
        valid_until=valid_until,
        frequency_per_day=data.get("frequencyPerDay", 4),
    )

    audit_logger.log_event(
        AuditEventType.USER_UPDATE,
        "consent_created",
        user_id=psu_id,
        resource_type="psd2_consent",
        resource_id=consent.consent_id,
        details={
            "tpp_id": g.tpp_id,
            "access_scope": data["access"],
            "valid_until": (
                consent.valid_until.isoformat() if consent.valid_until else None
            ),
        },
        severity=AuditSeverity.HIGH,
    )

    logger.info(
        f"Consent created: {consent.consent_id} for PSU {psu_id} by TPP {g.tpp_id}"
    )

    return (
        jsonify(
            {
                "consentId": consent.consent_id,
                "consentStatus": consent.status.value,
                "validUntil": (
                    consent.valid_until.isoformat() if consent.valid_until else None
                ),
                "_links": {
                    "scaRedirect": f"/api/v1/consents/{consent.consent_id}/authorisations",
                    "self": f"/api/v1/consents/{consent.consent_id}",
                    "status": f"/api/v1/consents/{consent.consent_id}/status",
                },
            }
        ),
        201,
    )


@app.route("/api/v1/consents/<consent_id>", methods=["GET"])
@validate_tpp_certificate
@validate_fapi_headers
@log_security_event(SecurityEventType.DATA_ACCESS)
def get_consent(consent_id: str) -> Any:
    """Get consent details"""
    consent = consent_manager.get_consent(consent_id)
    if not consent:
        return (
            jsonify({"error": "not_found", "error_description": "Consent not found"}),
            404,
        )

    if consent.tpp_id != g.tpp_id:
        return (
            jsonify(
                {
                    "error": "forbidden",
                    "error_description": "TPP not authorized for this consent",
                }
            ),
            403,
        )

    return jsonify(
        {
            "consentId": consent.consent_id,
            "consentStatus": consent.status.value,
            "validUntil": consent.valid_until.isoformat(),
            "frequencyPerDay": consent.frequency_per_day,
            "recurringIndicator": consent.recurring_indicator,
            "access": consent.access,
            "lastActionDate": consent.status_change_date_time.isoformat(),
        }
    )


@app.route("/api/v1/consents/<consent_id>/authorisations", methods=["POST"])
@validate_tpp_certificate
@validate_fapi_headers
@validate_json_request(SCAInitiationSchema)
@log_security_event(SecurityEventType.LOGIN_ATTEMPT, ThreatLevel.MODERATE)
def initiate_consent_authorisation(consent_id: str) -> Any:
    """Initiate Strong Customer Authentication for consent"""
    data = request.validated_data

    is_valid, message = consent_manager.validate_consent(consent_id, g.tpp_id)
    if not is_valid:
        return jsonify({"error": "invalid_consent", "error_description": message}), 400

    consent = consent_manager.get_consent(consent_id)

    try:
        sca_method = AuthenticationMethod(data["scaMethod"])
    except ValueError:
        return (
            jsonify(
                {
                    "error": "invalid_request",
                    "error_description": "Invalid SCA method provided",
                }
            ),
            400,
        )

    sca_data = sca_manager.initiate_sca(
        psu_id=consent.psu_id, sca_method=sca_method, consent_id=consent_id
    )

    logger.info(f"SCA initiated for consent {consent_id}: {sca_data.authentication_id}")

    return (
        jsonify(
            {
                "scaStatus": sca_data.status.value,
                "authorisationId": sca_data.authentication_id,
                "scaMethod": sca_data.sca_method.value,
                "psuMessage": data.get(
                    "psuMessage", "Please authenticate to authorize consent"
                ),
                "_links": {
                    "scaStatus": f"/api/v1/consents/{consent_id}/authorisations/{sca_data.authentication_id}",
                    "scaOAuth": f"/oauth2/authorize?consent_id={consent_id}&auth_id={sca_data.authentication_id}",
                },
            }
        ),
        201,
    )


@app.route(
    "/api/v1/consents/<consent_id>/authorisations/<authorisation_id>", methods=["PUT"]
)
@validate_tpp_certificate
@validate_fapi_headers
@log_security_event(SecurityEventType.LOGIN_ATTEMPT, ThreatLevel.HIGH)
def update_consent_authorisation(consent_id: str, authorisation_id: str) -> Any:
    """Update SCA authorisation with authentication data"""
    data = request.get_json() or {}
    auth_response = data.get("scaAuthenticationData")

    if not auth_response:
        return (
            jsonify(
                {
                    "error": "invalid_request",
                    "error_description": "SCA authentication data required",
                }
            ),
            400,
        )

    is_verified, sca_status = sca_manager.verify_sca(authorisation_id, auth_response)

    if is_verified:
        consent_manager.update_consent_status(consent_id, ConsentStatus.VALID)
        logger.info(f"Consent {consent_id} authorized successfully")
        return jsonify(
            {"scaStatus": sca_status.value, "consentStatus": ConsentStatus.VALID.value}
        )
    else:
        logger.warning(f"SCA verification failed for consent {consent_id}")
        return (
            jsonify(
                {
                    "scaStatus": sca_status.value,
                    "error": "authentication_failed",
                    "error_description": "Strong Customer Authentication failed",
                }
            ),
            401,
        )


@app.route("/api/v1/payments/sepa-credit-transfers", methods=["POST"])
@validate_tpp_certificate
@validate_fapi_headers
@validate_json_request(PaymentInitiationSchema)
@log_security_event(SecurityEventType.FRAUD_DETECTION, ThreatLevel.HIGH)
@audit_action(
    AuditEventType.TRANSACTION_CREATE,
    "payment_initiation_requested",
    severity=AuditSeverity.CRITICAL,
)
def initiate_payment() -> Any:
    """Initiate SEPA Credit Transfer (Payment Initiation Service)"""
    data = request.validated_data

    if "PSP_PI" not in g.tpp_roles:
        return (
            jsonify(
                {
                    "error": "unauthorized_client",
                    "error_description": "TPP missing role: Payment Initiation Service (PSP_PI)",
                }
            ),
            403,
        )

    psu_id = request.headers.get("PSU-ID")
    if not psu_id:
        return (
            jsonify(
                {
                    "error": "invalid_request",
                    "error_description": "PSU identification required",
                }
            ),
            400,
        )

    # Data Preparation
    amount_val = float(data["instructedAmount"]["amount"])
    currency_val = data["instructedAmount"]["currency"]

    transaction_data = {
        "amount": amount_val,
        "currency": currency_val,
        "merchant_category": "bank_transfer",
        "country": "DE",  # In prod, extract from IBAN/Context
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Fraud Detection Analysis
    risk_score, risk_factors = fraud_engine.analyze_transaction_behavior(
        psu_id,
        transaction_data["amount"],
        transaction_data["currency"],
        transaction_data["merchant_category"],
        request.remote_addr,
    )

    exemption_eligible = TransactionRiskAnalysis.is_eligible_for_exemption(
        risk_score, transaction_data["amount"], "low_risk"
    )

    payment_id = f"payment_{int(time.time())}_{psu_id[:8]}"

    # Logic: SCA is required if risk is high OR not eligible for exemption
    sca_required = not exemption_eligible or risk_score > 30

    response_data: Dict[str, Any] = {}
    if sca_required:
        sca_data = sca_manager.initiate_sca(
            psu_id=psu_id,
            sca_method=AuthenticationMethod.SMS_OTP,
            transaction_id=payment_id,
        )
        response_data = {
            "paymentId": payment_id,
            "transactionStatus": "RCVD",
            "scaRequired": True,
            "scaStatus": sca_data.status.value,
            "authorisationId": sca_data.authentication_id,
            "_links": {
                "scaRedirect": f"/api/v1/payments/sepa-credit-transfers/{payment_id}/authorisations/{sca_data.authentication_id}",
                "self": f"/api/v1/payments/sepa-credit-transfers/{payment_id}",
                "status": f"/api/v1/payments/sepa-credit-transfers/{payment_id}/status",
            },
        }

        # Create fraud alert if risk is critical
        if risk_score > 50:
            fraud_engine.create_fraud_alert(
                psu_id,
                "high_risk_payment",
                risk_score,
                {"payment_id": payment_id, "risk_factors": risk_factors},
            )
    else:
        # Exemption applied
        response_data = {
            "paymentId": payment_id,
            "transactionStatus": "ACCP",
            "scaRequired": False,
            "scaExemption": "lowRisk",
            "_links": {
                "self": f"/api/v1/payments/sepa-credit-transfers/{payment_id}",
                "status": f"/api/v1/payments/sepa-credit-transfers/{payment_id}/status",
            },
        }

    audit_logger.log_financial_transaction(
        AuditEventType.TRANSACTION_CREATE,
        psu_id,
        payment_id,
        str(transaction_data["amount"]),
        transaction_data["currency"],
        details={
            "tpp_id": g.tpp_id,
            "creditor_name": data["creditorName"],
            "risk_score": risk_score,
            "sca_required": sca_required,
        },
    )

    logger.info(
        f"Payment initiated: {payment_id} for PSU {psu_id} by TPP {g.tpp_id} (Risk: {risk_score})"
    )
    return jsonify(response_data), 201


@app.route("/api/v1/accounts", methods=["GET"])
@validate_tpp_certificate
@validate_fapi_headers
@log_security_event(SecurityEventType.DATA_ACCESS)
def get_accounts() -> Any:
    """Get account list (Account Information Service)"""
    consent_id = request.headers.get("Consent-ID")
    if not consent_id:
        return (
            jsonify(
                {
                    "error": "invalid_request",
                    "error_description": "Consent-ID header required",
                }
            ),
            400,
        )

    is_valid, message = consent_manager.validate_consent(consent_id, g.tpp_id)
    if not is_valid:
        return jsonify({"error": "invalid_consent", "error_description": message}), 403

    consent = consent_manager.get_consent(consent_id)
    if "accounts" not in consent.access:
        return (
            jsonify(
                {
                    "error": "insufficient_scope",
                    "error_description": "Consent does not include accounts access",
                }
            ),
            403,
        )

    # In a real app, fetch from Core Banking System
    accounts = [
        {
            "resourceId": "account_001",
            "iban": "DE89370400440532013000",
            "currency": "EUR",
            "accountType": "Girokonto",
            "cashAccountType": "CACC",
            "name": "Main Account",
            "_links": {
                "balances": "/api/v1/accounts/account_001/balances",
                "transactions": "/api/v1/accounts/account_001/transactions",
            },
        }
    ]
    return jsonify({"accounts": accounts})


@app.route("/api/v1/accounts/<account_id>/balances", methods=["GET"])
@validate_tpp_certificate
@validate_fapi_headers
@log_security_event(SecurityEventType.DATA_ACCESS)
def get_account_balances(account_id: str) -> Any:
    """Get account balances"""
    consent_id = request.headers.get("Consent-ID")
    if not consent_id:
        return (
            jsonify(
                {
                    "error": "invalid_request",
                    "error_description": "Consent-ID header required",
                }
            ),
            400,
        )

    is_valid, message = consent_manager.validate_consent(consent_id, g.tpp_id)
    if not is_valid:
        return jsonify({"error": "invalid_consent", "error_description": message}), 403

    balances = [
        {
            "balanceType": "closingBooked",
            "balanceAmount": {"amount": "1500.00", "currency": "EUR"},
            "referenceDate": datetime.now(timezone.utc).date().isoformat(),
        },
        {
            "balanceType": "expected",
            "balanceAmount": {"amount": "1500.00", "currency": "EUR"},
        },
    ]
    return jsonify(
        {"account": {"iban": "DE89370400440532013000"}, "balances": balances}
    )


@app.route("/api/v1/security/threat-summary", methods=["GET"])
@require_auth
@require_permission("security:read")
def get_threat_summary() -> Any:
    """Get security threat summary"""
    try:
        hours = int(request.args.get("hours", 24))
    except ValueError:
        hours = 24

    summary = security_monitor.get_threat_summary(hours)
    return jsonify(summary)


# -------------------------------------------------------------------------
# Error Handlers
# -------------------------------------------------------------------------


@app.errorhandler(400)
def bad_request(error: Any) -> Any:
    return (
        jsonify(
            {
                "error": "invalid_request",
                "error_description": "The request is malformed or invalid",
            }
        ),
        400,
    )


@app.errorhandler(401)
def unauthorized(error: Any) -> Any:
    return (
        jsonify(
            {
                "error": "unauthorized",
                "error_description": "Authentication required or invalid",
            }
        ),
        401,
    )


@app.errorhandler(403)
def forbidden(error: Any) -> Any:
    return (
        jsonify(
            {"error": "forbidden", "error_description": "Insufficient permissions"}
        ),
        403,
    )


@app.errorhandler(404)
def not_found(error: Any) -> Any:
    return (
        jsonify({"error": "not_found", "error_description": "Resource not found"}),
        404,
    )


@app.errorhandler(500)
def internal_error(error: Any) -> Any:
    logger.error(f"Internal server error: {str(error)}", exc_info=True)
    return (
        jsonify(
            {
                "error": "server_error",
                "error_description": "An internal server error occurred",
            }
        ),
        500,
    )


if __name__ == "__main__":
    # Ensure critical directories exist
    os.makedirs(os.path.join(BASE_DIR, "database"), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, "keys"), exist_ok=True)

    # Run app (Debug should be False in production)
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    port = int(os.environ.get("PORT", 5010))

    app.run(host="0.0.0.0", port=port, debug=debug_mode)
