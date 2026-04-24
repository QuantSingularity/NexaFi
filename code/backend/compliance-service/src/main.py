"""
Compliance Service for NexaFi
Handles AML, KYC, fraud detection, and regulatory compliance
"""

import json
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List

from flask import Flask, g, jsonify, request
from flask_cors import CORS

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "shared"))
from audit.audit_logger import AuditEventType, AuditSeverity, audit_action, audit_logger
from database.manager import BaseModel, initialize_database
from middleware.auth import require_auth, require_permission
from models.user import AMLCheck, ComplianceReport, KYCVerification, SanctionsScreening
from nexafi_logging.logger import get_logger, setup_request_logging
from validation_schemas.schemas import (
    SanitizationMixin,
    Schema,
    fields,
    validate,
    validate_json_request,
)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "nexafi-default-secret-change-in-production"
)
CORS(app, origins="*", allow_headers=["Content-Type", "Authorization", "X-User-ID"])
setup_request_logging(app)
logger = get_logger("compliance_service")
db_path = os.path.join(os.path.dirname(__file__), "database", "compliance.db")
os.makedirs(os.path.dirname(db_path), exist_ok=True)
db_manager, migration_manager = initialize_database(db_path)
COMPLIANCE_MIGRATIONS = {
    "004_create_kyc_table": {
        "description": "Create KYC verification table",
        "sql": "\n        CREATE TABLE IF NOT EXISTS kyc_verifications (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            user_id TEXT NOT NULL,\n            verification_type TEXT NOT NULL,\n            status TEXT NOT NULL DEFAULT 'pending',\n            document_type TEXT,\n            document_number TEXT,\n            verification_data TEXT,\n            risk_score INTEGER DEFAULT 0,\n            verified_at TIMESTAMP,\n            expires_at TIMESTAMP,\n            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n        );\n\n        CREATE INDEX IF NOT EXISTS idx_kyc_user_id ON kyc_verifications(user_id);\n        CREATE INDEX IF NOT EXISTS idx_kyc_status ON kyc_verifications(status);\n        ",
    },
    "005_create_aml_checks_table": {
        "description": "Create AML monitoring table",
        "sql": "\n        CREATE TABLE IF NOT EXISTS aml_checks (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            transaction_id TEXT NOT NULL,\n            user_id TEXT NOT NULL,\n            check_type TEXT NOT NULL,\n            risk_level TEXT NOT NULL DEFAULT 'low',\n            risk_score INTEGER DEFAULT 0,\n            flags TEXT,\n            status TEXT NOT NULL DEFAULT 'pending',\n            reviewed_by TEXT,\n            reviewed_at TIMESTAMP,\n            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n        );\n\n        CREATE INDEX IF NOT EXISTS idx_aml_transaction_id ON aml_checks(transaction_id);\n        CREATE INDEX IF NOT EXISTS idx_aml_user_id ON aml_checks(user_id);\n        CREATE INDEX IF NOT EXISTS idx_aml_risk_level ON aml_checks(risk_level);\n        ",
    },
    "006_create_sanctions_list_table": {
        "description": "Create sanctions screening table",
        "sql": "\n        CREATE TABLE IF NOT EXISTS sanctions_screening (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            entity_id TEXT NOT NULL,\n            entity_type TEXT NOT NULL,\n            entity_name TEXT NOT NULL,\n            screening_result TEXT NOT NULL DEFAULT 'clear',\n            match_score INTEGER DEFAULT 0,\n            matched_lists TEXT,\n            last_screened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n        );\n\n        CREATE INDEX IF NOT EXISTS idx_sanctions_entity_id ON sanctions_screening(entity_id);\n        CREATE INDEX IF NOT EXISTS idx_sanctions_result ON sanctions_screening(screening_result);\n        ",
    },
    "007_create_compliance_reports_table": {
        "description": "Create compliance reports table",
        "sql": "\n        CREATE TABLE IF NOT EXISTS compliance_reports (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            report_type TEXT NOT NULL,\n            report_period_start DATE NOT NULL,\n            report_period_end DATE NOT NULL,\n            status TEXT NOT NULL DEFAULT 'draft',\n            report_data TEXT,\n            generated_by TEXT,\n            submitted_at TIMESTAMP,\n            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n        );\n\n        CREATE INDEX IF NOT EXISTS idx_compliance_reports_type ON compliance_reports(report_type);\n        CREATE INDEX IF NOT EXISTS idx_compliance_reports_period ON compliance_reports(report_period_start, report_period_end);\n        ",
    },
}
for version, migration in COMPLIANCE_MIGRATIONS.items():
    migration_manager.apply_migration(
        version, migration["description"], migration["sql"]
    )
BaseModel.set_db_manager(db_manager)


class KYCVerificationSchema(SanitizationMixin, Schema):
    user_id = fields.Str(required=True)
    verification_type = fields.Str(
        required=True,
        validate=validate.OneOf(["identity", "address", "income", "source_of_funds"]),
    )
    document_type = fields.Str(
        required=False,
        validate=validate.OneOf(
            [
                "passport",
                "drivers_license",
                "national_id",
                "utility_bill",
                "bank_statement",
            ]
        ),
    )
    document_number = fields.Str(required=False, validate=validate.Length(max=50))


class AMLCheckSchema(SanitizationMixin, Schema):
    transaction_id = fields.Str(required=True)
    user_id = fields.Str(required=True)
    check_type = fields.Str(
        required=True,
        validate=validate.OneOf(
            ["transaction_monitoring", "customer_screening", "due_diligence"]
        ),
    )


class SanctionsScreeningSchema(SanitizationMixin, Schema):
    entity_id = fields.Str(required=True)
    entity_type = fields.Str(
        required=True, validate=validate.OneOf(["user", "business", "transaction"])
    )
    entity_name = fields.Str(required=True, validate=validate.Length(min=1, max=200))


class RiskScorer:
    """Risk scoring engine for compliance checks"""

    @staticmethod
    def calculate_transaction_risk(
        transaction_data: Dict[str, Any],
    ) -> tuple[int, List[str], str]:
        """Calculate risk score for a transaction"""
        risk_score = 0
        flags = []
        amount = float(transaction_data.get("amount", 0))
        currency = transaction_data.get("currency", "USD")
        country = transaction_data.get("country", "US")
        if amount > 10000:
            risk_score += 30
            flags.append("high_value_transaction")
        elif amount > 5000:
            risk_score += 15
            flags.append("medium_value_transaction")
        high_risk_currencies = ["BTC", "ETH", "XMR"]
        if currency in high_risk_currencies:
            risk_score += 25
            flags.append("cryptocurrency_transaction")
        high_risk_countries = ["AF", "IR", "KP", "SY"]
        if country in high_risk_countries:
            risk_score += 40
            flags.append("high_risk_country")
        transaction_count = transaction_data.get("daily_transaction_count", 0)
        if transaction_count > 10:
            risk_score += 20
            flags.append("high_frequency_transactions")
        if risk_score >= 70:
            risk_level = "high"
        elif risk_score >= 40:
            risk_level = "medium"
        else:
            risk_level = "low"
        return (risk_score, flags, risk_level)

    @staticmethod
    def calculate_customer_risk(customer_data: Dict[str, Any]) -> tuple[int, List[str]]:
        """Calculate risk score for a customer"""
        risk_score = 0
        flags = []
        if customer_data.get("is_pep", False):
            risk_score += 50
            flags.append("politically_exposed_person")
        high_risk_professions = ["money_changer", "casino_operator", "arms_dealer"]
        if customer_data.get("profession") in high_risk_professions:
            risk_score += 30
            flags.append("high_risk_profession")
        residence_country = customer_data.get("residence_country", "US")
        high_risk_countries = ["AF", "IR", "KP", "SY"]
        if residence_country in high_risk_countries:
            risk_score += 35
            flags.append("high_risk_residence")
        account_age_days = customer_data.get("account_age_days", 0)
        if account_age_days < 30:
            risk_score += 15
            flags.append("new_customer")
        return (risk_score, flags)


class SanctionsChecker:
    """Sanctions list screening"""

    SANCTIONS_LISTS = {
        "OFAC_SDN": ["John Doe Sanctioned", "Jane Smith Blocked", "Evil Corp Ltd"],
        "UN_SANCTIONS": ["Terrorist Organization", "Blocked Entity Inc"],
    }

    @classmethod
    def screen_entity(cls, entity_name: str) -> tuple[str, int, List[str]]:
        """Screen entity against sanctions lists"""
        entity_name_lower = entity_name.lower()
        matched_lists = []
        max_score = 0
        for list_name, sanctioned_entities in cls.SANCTIONS_LISTS.items():
            for sanctioned_entity in sanctioned_entities:
                similarity = cls._calculate_similarity(
                    entity_name_lower, sanctioned_entity.lower()
                )
                if similarity > 80:
                    matched_lists.append(list_name)
                    max_score = max(max_score, similarity)
        if matched_lists:
            result = "match" if max_score > 95 else "potential_match"
        else:
            result = "clear"
        return (result, max_score, matched_lists)

    @staticmethod
    def _calculate_similarity(str1: str, str2: str) -> int:
        """Simple similarity calculation (Levenshtein distance approximation)"""
        if str1 == str2:
            return 100
        set1 = set(str1.replace(" ", ""))
        set2 = set(str2.replace(" ", ""))
        if not set1 or not set2:
            return 0
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        return int(intersection / union * 100)


@app.route("/api/v1/health", methods=["GET"])
def health_check() -> object:
    """Health check endpoint"""
    return jsonify(
        {
            "status": "healthy",
            "service": "compliance-service",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
        }
    )


@app.route("/api/v1/kyc/verify", methods=["POST"])
@require_auth
@require_permission("compliance:write")
@validate_json_request(KYCVerificationSchema)
@audit_action(
    AuditEventType.USER_UPDATE,
    "kyc_verification_initiated",
    severity=AuditSeverity.HIGH,
)
def initiate_kyc_verification() -> object:
    """Initiate KYC verification for a user"""
    data = request.validated_data  # type: ignore[attr-defined]
    kyc = KYCVerification(
        user_id=data["user_id"],
        verification_type=data["verification_type"],
        document_type=data.get("document_type"),
        document_number=data.get("document_number"),
        status="pending",
    )
    kyc.save()
    audit_logger.log_event(
        AuditEventType.USER_UPDATE,
        "kyc_verification_initiated",
        user_id=data["user_id"],
        resource_type="kyc_verification",
        resource_id=str(kyc.id),
        details={
            "verification_type": data["verification_type"],
            "document_type": data.get("document_type"),
        },
        severity=AuditSeverity.HIGH,
    )
    logger.info(f"KYC verification initiated for user {data['user_id']}")
    return (
        jsonify(
            {
                "message": "KYC verification initiated",
                "verification_id": kyc.id,
                "status": kyc.status,
            }
        ),
        201,
    )


@app.route("/api/v1/kyc/<int:verification_id>/complete", methods=["POST"])
@require_auth
@require_permission("compliance:write")
@audit_action(
    AuditEventType.USER_UPDATE,
    "kyc_verification_completed",
    severity=AuditSeverity.HIGH,
)
def complete_kyc_verification(verification_id: object) -> object:
    """Complete KYC verification"""
    data = request.get_json() or {}
    kyc = KYCVerification.find_by_id(verification_id)
    if not kyc:
        return (jsonify({"error": "KYC verification not found"}), 404)
    kyc.status = data.get("status", "approved")
    kyc.verification_data = json.dumps(data.get("verification_data", {}))
    kyc.risk_score = data.get("risk_score", 0)
    kyc.verified_at = datetime.utcnow()
    if kyc.verification_type == "identity":
        kyc.expires_at = datetime.utcnow() + timedelta(days=365)
    kyc.save()
    audit_logger.log_event(
        AuditEventType.USER_UPDATE,
        "kyc_verification_completed",
        user_id=kyc.user_id,
        resource_type="kyc_verification",
        resource_id=str(kyc.id),
        details={"status": kyc.status, "risk_score": kyc.risk_score},
        severity=AuditSeverity.HIGH,
    )
    return jsonify(
        {
            "message": "KYC verification completed",
            "verification_id": kyc.id,
            "status": kyc.status,
            "risk_score": kyc.risk_score,
        }
    )


@app.route("/api/v1/aml/check", methods=["POST"])
@require_auth
@require_permission("compliance:write")
@validate_json_request(AMLCheckSchema)
@audit_action(
    AuditEventType.TRANSACTION_CREATE,
    "aml_check_initiated",
    severity=AuditSeverity.HIGH,
)
def perform_aml_check() -> object:
    """Perform AML check on a transaction"""
    data = request.validated_data  # type: ignore[attr-defined]
    transaction_data = request.get_json().get("transaction_data", {})
    risk_score, flags, risk_level = RiskScorer.calculate_transaction_risk(
        transaction_data
    )
    aml_check = AMLCheck(
        transaction_id=data["transaction_id"],
        user_id=data["user_id"],
        check_type=data["check_type"],
        risk_level=risk_level,
        risk_score=risk_score,
        flags=json.dumps(flags),
        status="completed" if risk_level != "high" else "requires_review",
    )
    aml_check.save()
    audit_logger.log_financial_transaction(
        AuditEventType.TRANSACTION_CREATE,
        data["user_id"],
        data["transaction_id"],
        str(transaction_data.get("amount", 0)),
        transaction_data.get("currency", "USD"),
        details={
            "aml_check_id": aml_check.id,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "flags": flags,
        },
    )
    logger.info(
        f"AML check completed for transaction {data['transaction_id']}: {risk_level} risk"
    )
    return jsonify(
        {
            "aml_check_id": aml_check.id,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "flags": flags,
            "status": aml_check.status,
            "requires_review": aml_check.status == "requires_review",
        }
    )


@app.route("/api/v1/sanctions/screen", methods=["POST"])
@require_auth
@require_permission("compliance:write")
@validate_json_request(SanctionsScreeningSchema)
@audit_action(
    AuditEventType.USER_UPDATE, "sanctions_screening", severity=AuditSeverity.HIGH
)
def screen_sanctions() -> object:
    """Screen entity against sanctions lists"""
    data = request.validated_data  # type: ignore[attr-defined]
    result, match_score, matched_lists = SanctionsChecker.screen_entity(
        data["entity_name"]
    )
    screening = SanctionsScreening(
        entity_id=data["entity_id"],
        entity_type=data["entity_type"],
        entity_name=data["entity_name"],
        screening_result=result,
        match_score=match_score,
        matched_lists=json.dumps(matched_lists),
    )
    screening.save()
    audit_logger.log_event(
        AuditEventType.USER_UPDATE,
        "sanctions_screening_performed",
        user_id=data["entity_id"] if data["entity_type"] == "user" else None,
        resource_type="sanctions_screening",
        resource_id=str(screening.id),
        details={
            "entity_type": data["entity_type"],
            "screening_result": result,
            "match_score": match_score,
            "matched_lists": matched_lists,
        },
        severity=AuditSeverity.HIGH if result != "clear" else AuditSeverity.MEDIUM,
    )
    logger.info(
        f"Sanctions screening completed for {data['entity_type']} {data['entity_id']}: {result}"
    )
    return jsonify(
        {
            "screening_id": screening.id,
            "result": result,
            "match_score": match_score,
            "matched_lists": matched_lists,
            "requires_review": result in ["match", "potential_match"],
        }
    )


@app.route("/api/v1/compliance/reports/generate", methods=["POST"])
@require_auth
@require_permission("compliance:write")
@audit_action(
    AuditEventType.REPORT_GENERATE,
    "compliance_report_generated",
    severity=AuditSeverity.MEDIUM,
)
def generate_compliance_report() -> object:
    """Generate compliance report"""
    data = request.get_json() or {}
    report_type = data.get("report_type", "suspicious_activity")
    period_start = datetime.fromisoformat(
        data.get("period_start", (datetime.utcnow() - timedelta(days=30)).isoformat())
    )
    period_end = datetime.fromisoformat(
        data.get("period_end", datetime.utcnow().isoformat())
    )
    if report_type == "suspicious_activity":
        high_risk_checks = AMLCheck.find_all(
            "risk_level = 'high' AND created_at BETWEEN ? AND ?",
            (period_start.isoformat(), period_end.isoformat()),
        )
        report_data = {
            "report_type": report_type,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "suspicious_transactions": len(high_risk_checks),
            "transactions": [check.to_dict() for check in high_risk_checks],
        }
    elif report_type == "kyc_status":
        pending_kyc = len(KYCVerification.find_all("status = 'pending'"))
        approved_kyc = len(KYCVerification.find_all("status = 'approved'"))
        rejected_kyc = len(KYCVerification.find_all("status = 'rejected'"))
        report_data = {
            "report_type": report_type,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "kyc_statistics": {
                "pending": pending_kyc,
                "approved": approved_kyc,
                "rejected": rejected_kyc,
                "total": pending_kyc + approved_kyc + rejected_kyc,
            },
        }
    else:
        return (jsonify({"error": "Invalid report type"}), 400)
    report = ComplianceReport(
        report_type=report_type,
        report_period_start=period_start.date(),
        report_period_end=period_end.date(),
        report_data=json.dumps(report_data),
        generated_by=g.current_user["user_id"],
        status="generated",
    )
    report.save()
    audit_logger.log_event(
        AuditEventType.REPORT_GENERATE,
        "compliance_report_generated",
        user_id=g.current_user["user_id"],
        resource_type="compliance_report",
        resource_id=str(report.id),
        details={
            "report_type": report_type,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
        },
    )
    return jsonify(
        {
            "report_id": report.id,
            "report_type": report_type,
            "status": "generated",
            "data": report_data,
        }
    )


@app.route("/api/v1/compliance/dashboard", methods=["GET"])
@require_auth
@require_permission("compliance:read")
def compliance_dashboard() -> object:
    """Get compliance dashboard data"""
    pending_kyc = len(KYCVerification.find_all("status = 'pending'"))
    high_risk_aml = len(
        AMLCheck.find_all("risk_level = 'high' AND status = 'requires_review'")
    )
    sanctions_matches = len(
        SanctionsScreening.find_all("screening_result IN ('match', 'potential_match')")
    )
    recent_kyc = KYCVerification.find_all("1=1 ORDER BY created_at DESC LIMIT 10")
    recent_aml = AMLCheck.find_all("1=1 ORDER BY created_at DESC LIMIT 10")
    return jsonify(
        {
            "statistics": {
                "pending_kyc_verifications": pending_kyc,
                "high_risk_transactions": high_risk_aml,
                "sanctions_matches": sanctions_matches,
            },
            "recent_activity": {
                "kyc_verifications": [kyc.to_dict() for kyc in recent_kyc],
                "aml_checks": [aml.to_dict() for aml in recent_aml],
            },
        }
    )


if __name__ == "__main__":
    os.makedirs(os.path.join(os.path.dirname(__file__), "database"), exist_ok=True)
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5005)), debug=debug_mode)
