import logging
import uuid
from datetime import datetime, timedelta
from functools import wraps

from ai_scoring import rule_based_score, score_with_ai
from flask import Blueprint, jsonify, request
from models.user import (
    CreditScore,
    CreditScoreModel,
    Loan,
    LoanApplication,
    LoanApplicationHistory,
    RiskAssessment,
)

credit_bp = Blueprint("credit", __name__)
logger = logging.getLogger(__name__)


def require_user_id(f: object) -> object:

    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            return (jsonify({"error": "User ID is required in headers"}), 401)
        request.user_id = user_id
        return f(*args, **kwargs)

    return decorated_function


def get_default_credit_model() -> object:
    model = CreditScoreModel.find_one("is_default = ?", (1,))
    if not model:
        model = CreditScoreModel(
            id=str(uuid.uuid4()),
            name="Default Credit Model",
            version="1.0",
            description="Placeholder model for credit scoring",
            model_type="placeholder",
            is_active=True,
            is_default=True,
            accuracy=0.75,
        )
        model.save()
    return model


def log_application_history(
    application_id: object,
    action: object,
    old_status: object = None,
    new_status: object = None,
    notes: object = None,
    changed_by: object = None,
) -> object:
    history = LoanApplicationHistory(
        id=str(uuid.uuid4()),
        application_id=application_id,
        action=action,
        old_status=old_status,
        new_status=new_status,
        notes=notes,
        changed_by=changed_by,
        created_at=datetime.utcnow().isoformat(),
    )
    history.save()


@credit_bp.route("/scores", methods=["POST"])
@require_user_id
def calculate_credit_score() -> object:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return (jsonify({"error": "A JSON object body is required"}), 400)
    input_features = data.get("input_features", {})
    if not isinstance(input_features, dict) or not input_features:
        return (jsonify({"error": "input_features must be a non empty object"}), 400)
    try:
        model = get_default_credit_model()
        assessment = score_with_ai(request.user_id, input_features)
        if assessment is not None:
            final_score = int(assessment["credit_score"])
            confidence = float(assessment.get("data_completeness", 0.0))
            details = {
                "method": "ai_scorecard",
                "model": assessment.get("model"),
                "risk_category": assessment.get("risk_category"),
                "decision": assessment.get("decision"),
                "probability_of_default": assessment.get("probability_of_default"),
                "factors": assessment.get("factors"),
                "recommendations": assessment.get("recommendations"),
                "prediction_id": assessment.get("prediction_id"),
            }
        else:
            try:
                final_score = rule_based_score(input_features)
            except (TypeError, ValueError):
                return (
                    jsonify({"error": "input_features contain non numeric values"}),
                    400,
                )
            confidence = 0.5
            details = {"method": "rule_based_fallback"}
        previous_scores = CreditScore.find_all(
            "user_id = ? AND is_current = ?", (request.user_id, 1)
        )
        for score in previous_scores:
            score.is_current = False
            score.save()
        new_score = CreditScore(
            id=str(uuid.uuid4()),
            user_id=request.user_id,
            model_id=model.id,
            score=final_score,
            input_features=input_features,
            calculation_details=details,
            confidence_score=confidence,
            expires_at=(datetime.utcnow() + timedelta(days=90)).isoformat(),
            is_current=True,
            created_at=datetime.utcnow().isoformat(),
        )
        new_score.save()
        return (jsonify(new_score.to_dict()), 201)
    except Exception:
        logger.exception("Credit score calculation failed")
        return (jsonify({"error": "Failed to calculate credit score"}), 500)


@credit_bp.route("/scores/current", methods=["GET"])
@require_user_id
def get_current_credit_score() -> object:
    score = CreditScore.find_one("user_id = ? AND is_current = ?", (request.user_id, 1))
    if not score:
        return (jsonify({"error": "No current credit score found"}), 404)
    if score.is_expired():
        score.is_current = False
        score.save()
        return (jsonify({"error": "Current credit score has expired"}), 404)
    return (jsonify(score.to_dict()), 200)


@credit_bp.route("/applications", methods=["POST"])
@require_user_id
def create_loan_application() -> object:
    try:
        data = request.get_json()
        current_score = CreditScore.find_one(
            "user_id = ? AND is_current = ?", (request.user_id, 1)
        )
        risk_level = current_score.calculate_risk_level() if current_score else "medium"
        approval_probability = 0.75 if risk_level in ["very_low", "low"] else 0.5
        new_application = LoanApplication(
            id=str(uuid.uuid4()),
            user_id=request.user_id,
            loan_type=data["loan_type"],
            requested_amount=data["requested_amount"],
            purpose=data.get("purpose"),
            term_months=data.get("term_months"),
            applicant_data=data.get("applicant_data", "{}"),
            financial_data=data.get("financial_data", "{}"),
            business_data=data.get("business_data", "{}"),
            credit_score_id=current_score.id if current_score else None,
            risk_assessment={"initial_risk_level": risk_level},
            approval_probability=approval_probability,
            status="pending",
            priority="normal",
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )
        new_application.save()
        log_application_history(
            new_application.id,
            "Application Created",
            new_status="pending",
            changed_by=request.user_id,
        )
        return (jsonify(new_application.to_dict()), 201)
    except Exception as e:
        return (
            jsonify({"error": "Failed to create loan application", "details": str(e)}),
            400,
        )


@credit_bp.route("/applications", methods=["GET"])
@require_user_id
def get_loan_applications() -> object:
    applications = LoanApplication.find_all("user_id = ?", (request.user_id,))
    applications.sort(key=lambda x: x.created_at, reverse=True)
    return (jsonify([app.to_dict() for app in applications]), 200)


@credit_bp.route("/applications/<application_id>", methods=["GET"])
@require_user_id
def get_loan_application(application_id: object) -> object:
    application = LoanApplication.find_one(
        "id = ? AND user_id = ?", (application_id, request.user_id)
    )
    if not application:
        return (jsonify({"error": "Loan application not found"}), 404)
    return (jsonify(application.to_dict()), 200)


@credit_bp.route("/applications/<application_id>/status", methods=["PUT"])
@require_user_id
def update_loan_application_status(application_id: object) -> object:
    try:
        application = LoanApplication.find_one(
            "id = ? AND user_id = ?", (application_id, request.user_id)
        )
        if not application:
            return (jsonify({"error": "Loan application not found"}), 404)
        data = request.get_json()
        new_status = data.get("status")
        decision_reason = data.get("decision_reason")
        if new_status not in ["approved", "rejected", "withdrawn"]:
            return (jsonify({"error": "Invalid status update"}), 400)
        old_status = application.status
        application.status = new_status
        application.decision_date = datetime.utcnow().isoformat()
        application.decision_reason = decision_reason
        if new_status == "approved":
            application.approved_amount = application.requested_amount
            application.interest_rate = 0.08
            application.term_months = application.term_months or 36
            application.monthly_payment = application.calculate_monthly_payment()
            application.total_interest = application.calculate_total_interest()
        application.save()
        log_application_history(
            application_id,
            "Status Updated",
            old_status=old_status,
            new_status=new_status,
            notes=decision_reason,
            changed_by=request.user_id,
        )
        return (jsonify(application.to_dict()), 200)
    except Exception as e:
        return (
            jsonify(
                {"error": "Failed to update application status", "details": str(e)}
            ),
            500,
        )


@credit_bp.route("/applications/<application_id>/history", methods=["GET"])
@require_user_id
def get_application_history(application_id: object) -> object:
    application = LoanApplication.find_one(
        "id = ? AND user_id = ?", (application_id, request.user_id)
    )
    if not application:
        return (jsonify({"error": "Loan application not found"}), 404)
    history = LoanApplicationHistory.find_all("application_id = ?", (application_id,))
    history.sort(key=lambda x: x.created_at)
    return (jsonify([h.to_dict() for h in history]), 200)


@credit_bp.route("/loans", methods=["GET"])
@require_user_id
def get_loans() -> object:
    loans = Loan.find_all("user_id = ? AND status = ?", (request.user_id, "active"))
    loans.sort(key=lambda x: x.created_at, reverse=True)
    return (jsonify([loan.to_dict() for loan in loans]), 200)


@credit_bp.route("/loans/<loan_id>", methods=["GET"])
@require_user_id
def get_loan(loan_id: object) -> object:
    loan = Loan.find_one("id = ? AND user_id = ?", (loan_id, request.user_id))
    if not loan:
        return (jsonify({"error": "Loan not found"}), 404)
    return (jsonify(loan.to_dict()), 200)


@credit_bp.route("/risk-assessments", methods=["POST"])
@require_user_id
def create_risk_assessment() -> object:
    try:
        data = request.get_json()
        overall_risk_score = data.get("overall_risk_score", 0.5)
        if overall_risk_score < 0.3:
            risk_level = "very_low"
        elif overall_risk_score < 0.5:
            risk_level = "low"
        elif overall_risk_score < 0.7:
            risk_level = "medium"
        else:
            risk_level = "high"
        new_assessment = RiskAssessment(
            id=str(uuid.uuid4()),
            user_id=request.user_id,
            assessment_type=data["assessment_type"],
            risk_factors=data.get("risk_factors", "{}"),
            risk_scores=data.get("risk_scores", "{}"),
            overall_risk_score=overall_risk_score,
            risk_level=risk_level,
            recommendations=data.get("recommendations", "[]"),
            mitigation_strategies=data.get("mitigation_strategies", "[]"),
            valid_until=(datetime.utcnow() + timedelta(days=180)).isoformat(),
            confidence_level=data.get("confidence_level", 0.9),
            data_sources=data.get("data_sources", "[]"),
            created_at=datetime.utcnow().isoformat(),
        )
        new_assessment.save()
        return (jsonify(new_assessment.to_dict()), 201)
    except Exception as e:
        return (
            jsonify({"error": "Failed to create risk assessment", "details": str(e)}),
            400,
        )


@credit_bp.route("/risk-assessments", methods=["GET"])
@require_user_id
def get_risk_assessments() -> object:
    assessments = RiskAssessment.find_all("user_id = ?", (request.user_id,))
    assessments.sort(key=lambda x: x.created_at, reverse=True)
    return (jsonify([a.to_dict() for a in assessments]), 200)


@credit_bp.route("/risk-assessments/<assessment_id>", methods=["GET"])
@require_user_id
def get_risk_assessment(assessment_id: object) -> object:
    assessment = RiskAssessment.find_one(
        "id = ? AND user_id = ?", (assessment_id, request.user_id)
    )
    if not assessment:
        return (jsonify({"error": "Risk assessment not found"}), 404)
    return (jsonify(assessment.to_dict()), 200)
