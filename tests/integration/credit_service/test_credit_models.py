from typing import Any
import json
from datetime import datetime, timedelta
import pytest
from NexaFi.backend.credit_service.src.main import app
from NexaFi.backend.credit_service.src.models.user import (
    CreditScore,
    CreditScoreModel,
    Loan,
    LoanApplication,
    LoanApplicationHistory,
    LoanDocument,
    db,
)


@pytest.fixture(scope="module")
def client() -> Any:
    """
    Setup the test client and initialize the in-memory database.
    """
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        with app.app_context():
            db.session.remove()
            db.drop_all()


@pytest.fixture(autouse=True)
def run_around_tests(client: Any) -> Any:
    """
    Clean up tables between tests.
    """
    with app.app_context():
        CreditScoreModel.query.delete()
        CreditScore.query.delete()
        LoanApplication.query.delete()
        Loan.query.delete()
        LoanDocument.query.delete()
        LoanApplicationHistory.query.delete()
        db.session.commit()
    yield


class TestCreditScoreModel:

    def test_credit_score_model_creation(self) -> Any:
        model = CreditScoreModel(
            name="Test Credit Model",
            version="1.0",
            model_type="xgboost",
            features=json.dumps(["feature1", "feature2"]),
            weights=json.dumps({"feature1": 0.5, "feature2": 0.5}),
        )
        db.session.add(model)
        db.session.commit()
        retrieved_model = CreditScoreModel.query.filter_by(
            name="Test Credit Model"
        ).first()
        assert retrieved_model is not None
        assert retrieved_model.version == "1.0"
        assert retrieved_model.get_features() == ["feature1", "feature2"]


class TestCreditScore:

    def test_credit_score_creation(self) -> Any:
        model = CreditScoreModel(name="Test Model", version="1.0", model_type="xgboost")
        db.session.add(model)
        db.session.commit()
        score = CreditScore(
            user_id="user123", model_id=model.id, score=750, grade="A", risk_level="low"
        )
        db.session.add(score)
        db.session.commit()
        retrieved_score = CreditScore.query.filter_by(user_id="user123").first()
        assert retrieved_score is not None
        assert retrieved_score.score == 750
        assert retrieved_score.grade == "A"

    def test_credit_score_grade_calculation(self) -> Any:
        score = CreditScore(user_id="user123", score=810)
        assert score.calculate_grade() == "A+"
        score.score = 720
        assert score.calculate_grade() == "B+"

    def test_credit_score_risk_level_calculation(self) -> Any:
        score = CreditScore(user_id="user123", score=810)
        assert score.calculate_risk_level() == "very_low"
        score.score = 620
        assert score.calculate_risk_level() == "high"


class TestLoanApplication:

    def test_loan_application_creation(self) -> Any:
        app = LoanApplication(
            user_id="user123",
            loan_type="personal",
            requested_amount=10000,
            status="pending",
        )
        db.session.add(app)
        db.session.commit()
        retrieved_app = LoanApplication.query.filter_by(user_id="user123").first()
        assert retrieved_app is not None
        assert retrieved_app.requested_amount == 10000

    def test_loan_application_monthly_payment_calculation(self) -> Any:
        app = LoanApplication(
            user_id="user123",
            loan_type="personal",
            approved_amount=10000,
            interest_rate=5.0,
            term_months=60,
        )
        assert round(app.calculate_monthly_payment(), 2) == 188.71


class TestLoan:

    def test_loan_creation(self) -> Any:
        loan = Loan(
            application_id="app123",
            user_id="user123",
            loan_number="LN001",
            loan_type="personal",
            principal_amount=10000,
            interest_rate=5.0,
            term_months=60,
            monthly_payment=188.71,
            current_balance=10000,
            principal_balance=10000,
            interest_balance=0,
            fees_balance=0,
        )
        db.session.add(loan)
        db.session.commit()
        retrieved_loan = Loan.query.filter_by(loan_number="LN001").first()
        assert retrieved_loan is not None
        assert retrieved_loan.principal_amount == 10000

    def test_loan_delinquency_status(self) -> Any:
        loan = Loan(
            application_id="app123",
            user_id="user123",
            loan_number="LN002",
            loan_type="personal",
            principal_amount=1000,
            interest_rate=5.0,
            term_months=12,
            monthly_payment=85.61,
            current_balance=1000,
            principal_balance=1000,
            interest_balance=0,
            fees_balance=0,
            next_payment_date=datetime.utcnow() - timedelta(days=5),
        )
        loan.update_delinquency_status()
        assert loan.is_delinquent == True
        assert loan.days_past_due == 5
        loan.next_payment_date = datetime.utcnow() + timedelta(days=5)
        loan.update_delinquency_status()
        assert loan.is_delinquent == False
        assert loan.days_past_due == 0


class TestLoanDocument:

    def test_loan_document_creation(self) -> Any:
        doc = LoanDocument(
            application_id="app123",
            document_type="income_proof",
            file_path="/docs/income.pdf",
            status="uploaded",
        )
        db.session.add(doc)
        db.session.commit()
        retrieved_doc = LoanDocument.query.filter_by(
            document_type="income_proof"
        ).first()
        assert retrieved_doc is not None
        assert retrieved_doc.file_path == "/docs/income.pdf"


class TestLoanApplicationHistory:

    def test_loan_application_history_creation(self) -> Any:
        history = LoanApplicationHistory(
            application_id="app123",
            status_change="pending_to_approved",
            changed_by="admin",
            notes="Approved based on credit score",
        )
        db.session.add(history)
        db.session.commit()
        retrieved_history = LoanApplicationHistory.query.filter_by(
            changed_by="admin"
        ).first()
        assert retrieved_history is not None
        assert retrieved_history.status_change == "pending_to_approved"
