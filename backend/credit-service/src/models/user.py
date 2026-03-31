import json
from datetime import datetime
from typing import Any, Dict, Optional


class BaseModel:
    """Base model with database operations - delegates to shared BaseModel"""

    table_name = None
    db_manager = None

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def find_by_id(cls: Any, id_value: Any) -> Any:
        """Find record by ID - delegates to actual shared BaseModel if available"""
        # Import actual BaseModel from shared if available
        try:
            import os
            import sys

            sys.path.insert(
                0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared")
            )
            from database.manager import BaseModel as SharedBaseModel

            return (
                SharedBaseModel.find_by_id(id_value)
                if hasattr(SharedBaseModel, "find_by_id")
                else None
            )
        except (ImportError, AttributeError):
            return None

    @classmethod
    def find_all(cls: Any, where_clause: str = "", params: tuple = ()) -> Any:
        """Find all records - delegates to actual shared BaseModel if available"""
        try:
            import os
            import sys

            sys.path.insert(
                0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared")
            )
            from database.manager import BaseModel as SharedBaseModel

            return (
                SharedBaseModel.find_all(where_clause, params)
                if hasattr(SharedBaseModel, "find_all")
                else []
            )
        except (ImportError, AttributeError):
            return []

    @classmethod
    def find_one(cls: Any, where_clause: str, params: tuple = ()) -> Any:
        """Find one record - delegates to actual shared BaseModel if available"""
        try:
            import os
            import sys

            sys.path.insert(
                0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared")
            )
            from database.manager import BaseModel as SharedBaseModel

            return (
                SharedBaseModel.find_one(where_clause, params)
                if hasattr(SharedBaseModel, "find_one")
                else None
            )
        except (ImportError, AttributeError):
            return None

    def save(self) -> None:
        """Save record - delegates to actual shared BaseModel if available"""
        try:
            import os
            import sys

            sys.path.insert(
                0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared")
            )
            from database.manager import BaseModel as SharedBaseModel

            if hasattr(SharedBaseModel, "save"):
                SharedBaseModel.save(self)
        except (ImportError, AttributeError):
            pass

    def delete(self) -> Any:
        pass

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


class CreditScoreModel(BaseModel):
    table_name: Optional[str] = "credit_score_models"

    def get_features(self) -> Any:
        return json.loads(self.features) if self.features else []

    def set_features(self, features_list: Any) -> Any:
        self.features = json.dumps(features_list)

    def get_weights(self) -> Any:
        return json.loads(self.weights) if self.weights else {}

    def set_weights(self, weights_dict: Any) -> Any:
        self.weights = json.dumps(weights_dict)

    def get_thresholds(self) -> Any:
        return json.loads(self.thresholds) if self.thresholds else {}

    def set_thresholds(self, thresholds_dict: Any) -> Any:
        self.thresholds = json.dumps(thresholds_dict)

    def to_dict(self) -> Any:
        data = super().to_dict()
        data["features"] = self.get_features()
        data["weights"] = self.get_weights()
        data["thresholds"] = self.get_thresholds()
        return data


class CreditScore(BaseModel):
    table_name: Optional[str] = "credit_scores"

    def get_input_features(self) -> Any:
        return json.loads(self.input_features) if self.input_features else {}

    def set_input_features(self, features: Any) -> Any:
        self.input_features = json.dumps(features)

    def get_calculation_details(self) -> Any:
        return json.loads(self.calculation_details) if self.calculation_details else {}

    def set_calculation_details(self, details: Any) -> Any:
        self.calculation_details = json.dumps(details)

    def is_expired(self) -> Any:
        if self.expires_at:
            expires_at_dt = (
                datetime.fromisoformat(self.expires_at)
                if isinstance(self.expires_at, str)
                else self.expires_at
            )
            return datetime.utcnow() > expires_at_dt
        return False

    def calculate_grade(self) -> Any:
        """Calculate letter grade based on score"""
        score = self.score if self.score is not None else 0
        if score >= 800:
            return "A+"
        elif score >= 750:
            return "A"
        elif score >= 700:
            return "B+"
        elif score >= 650:
            return "B"
        elif score >= 600:
            return "C+"
        elif score >= 550:
            return "C"
        elif score >= 500:
            return "D"
        else:
            return "F"

    def calculate_risk_level(self) -> Any:
        """Calculate risk level based on score"""
        score = self.score if self.score is not None else 0
        if score >= 750:
            return "very_low"
        elif score >= 700:
            return "low"
        elif score >= 650:
            return "medium"
        elif score >= 600:
            return "high"
        else:
            return "very_high"

    def to_dict(self) -> Any:
        data = super().to_dict()
        data["input_features"] = self.get_input_features()
        data["calculation_details"] = self.get_calculation_details()
        data["is_expired"] = self.is_expired()
        data["grade"] = (
            self.grade
            if hasattr(self, "grade") and self.grade
            else self.calculate_grade()
        )
        data["risk_level"] = (
            self.risk_level
            if hasattr(self, "risk_level") and self.risk_level
            else self.calculate_risk_level()
        )
        return data


class LoanApplication(BaseModel):
    table_name: Optional[str] = "loan_applications"

    def get_applicant_data(self) -> Any:
        return json.loads(self.applicant_data) if self.applicant_data else {}

    def set_applicant_data(self, data: Any) -> Any:
        self.applicant_data = json.dumps(data)

    def get_financial_data(self) -> Any:
        return json.loads(self.financial_data) if self.financial_data else {}

    def set_financial_data(self, data: Any) -> Any:
        self.financial_data = json.dumps(data)

    def get_business_data(self) -> Any:
        return json.loads(self.business_data) if self.business_data else {}

    def set_business_data(self, data: Any) -> Any:
        self.business_data = json.dumps(data)

    def get_risk_assessment(self) -> Any:
        return json.loads(self.risk_assessment) if self.risk_assessment else {}

    def set_risk_assessment(self, assessment: Any) -> Any:
        self.risk_assessment = json.dumps(assessment)

    def calculate_monthly_payment(self) -> Any:
        """Calculate monthly payment based on approved terms"""
        if self.approved_amount and self.interest_rate and self.term_months:
            monthly_rate = self.interest_rate / 100 / 12
            if monthly_rate == 0:
                return self.approved_amount / self.term_months
            payment = (
                self.approved_amount
                * (monthly_rate * (1 + monthly_rate) ** self.term_months)
                / ((1 + monthly_rate) ** self.term_months - 1)
            )
            return round(payment, 2)
        return None

    def calculate_total_interest(self) -> Any:
        """Calculate total interest over loan term"""
        if self.monthly_payment and self.term_months and self.approved_amount:
            total_payments = self.monthly_payment * self.term_months
            return round(total_payments - self.approved_amount, 2)
        return None

    def to_dict(self) -> Any:
        data = super().to_dict()
        data["applicant_data"] = self.get_applicant_data()
        data["financial_data"] = self.get_financial_data()
        data["business_data"] = self.get_business_data()
        data["risk_assessment"] = self.get_risk_assessment()
        data["monthly_payment"] = (
            self.monthly_payment
            if hasattr(self, "monthly_payment") and self.monthly_payment
            else self.calculate_monthly_payment()
        )
        data["total_interest"] = (
            self.total_interest
            if hasattr(self, "total_interest") and self.total_interest
            else self.calculate_total_interest()
        )
        return data


class Loan(BaseModel):
    table_name: Optional[str] = "loans"

    def calculate_remaining_balance(self) -> Any:
        """Calculate remaining loan balance"""
        return (
            (self.principal_balance or 0)
            + (self.interest_balance or 0)
            + (self.fees_balance or 0)
        )

    def calculate_payoff_amount(self) -> Any:
        """Calculate amount needed to pay off loan"""
        return self.calculate_remaining_balance()

    def update_delinquency_status(self) -> Any:
        """Update delinquency status based on payment history"""
        if self.next_payment_date:
            next_payment_dt = (
                datetime.fromisoformat(self.next_payment_date)
                if isinstance(self.next_payment_date, str)
                else self.next_payment_date
            )
            if datetime.utcnow() > next_payment_dt:
                self.days_past_due = (datetime.utcnow() - next_payment_dt).days
                self.is_delinquent = self.days_past_due > 0
            else:
                self.days_past_due = 0
                self.is_delinquent = False
        else:
            self.days_past_due = 0
            self.is_delinquent = False

    def to_dict(self) -> Any:
        data = super().to_dict()
        data["remaining_balance"] = self.calculate_remaining_balance()
        data["payoff_amount"] = self.calculate_payoff_amount()
        return data


class LoanPayment(BaseModel):
    table_name: Optional[str] = "loan_payments"

    def is_late(self) -> Any:
        if self.payment_date and self.due_date:
            payment_dt = (
                datetime.fromisoformat(self.payment_date)
                if isinstance(self.payment_date, str)
                else self.payment_date
            )
            due_dt = (
                datetime.fromisoformat(self.due_date)
                if isinstance(self.due_date, str)
                else self.due_date
            )
            return payment_dt > due_dt
        return False

    def days_late(self) -> Any:
        if self.is_late():
            payment_dt = (
                datetime.fromisoformat(self.payment_date)
                if isinstance(self.payment_date, str)
                else self.payment_date
            )
            due_dt = (
                datetime.fromisoformat(self.due_date)
                if isinstance(self.due_date, str)
                else self.due_date
            )
            return (payment_dt - due_dt).days
        return 0

    def to_dict(self) -> Any:
        data = super().to_dict()
        data["is_late"] = self.is_late()
        data["days_late"] = self.days_late()
        return data


class RiskAssessment(BaseModel):
    table_name: Optional[str] = "risk_assessments"

    def get_risk_factors(self) -> Any:
        return json.loads(self.risk_factors) if self.risk_factors else {}

    def set_risk_factors(self, factors: Any) -> Any:
        self.risk_factors = json.dumps(factors)

    def get_risk_scores(self) -> Any:
        return json.loads(self.risk_scores) if self.risk_scores else {}

    def set_risk_scores(self, scores: Any) -> Any:
        self.risk_scores = json.dumps(scores)

    def get_recommendations(self) -> Any:
        return json.loads(self.recommendations) if self.recommendations else []

    def set_recommendations(self, recommendations: Any) -> Any:
        self.recommendations = json.dumps(recommendations)

    def get_mitigation_strategies(self) -> Any:
        return (
            json.loads(self.mitigation_strategies) if self.mitigation_strategies else []
        )

    def set_mitigation_strategies(self, strategies: Any) -> Any:
        self.mitigation_strategies = json.dumps(strategies)

    def get_data_sources(self) -> Any:
        return json.loads(self.data_sources) if self.data_sources else []

    def set_data_sources(self, sources: Any) -> Any:
        self.data_sources = json.dumps(sources)

    def is_expired(self) -> Any:
        if self.valid_until:
            valid_until_dt = (
                datetime.fromisoformat(self.valid_until)
                if isinstance(self.valid_until, str)
                else self.valid_until
            )
            return datetime.utcnow() > valid_until_dt
        return False

    def to_dict(self) -> Any:
        data = super().to_dict()
        data["risk_factors"] = self.get_risk_factors()
        data["risk_scores"] = self.get_risk_scores()
        data["recommendations"] = self.get_recommendations()
        data["mitigation_strategies"] = self.get_mitigation_strategies()
        data["data_sources"] = self.get_data_sources()
        data["is_expired"] = self.is_expired()
        return data


class LoanDocument(BaseModel):
    table_name: Optional[str] = "loan_documents"

    def get_extracted_data(self) -> Any:
        return json.loads(self.extracted_data) if self.extracted_data else {}

    def set_extracted_data(self, data: Any) -> Any:
        self.extracted_data = json.dumps(data)

    def to_dict(self) -> Any:
        data = super().to_dict()
        data["extracted_data"] = self.get_extracted_data()
        return data


class LoanApplicationHistory(BaseModel):
    table_name: Optional[str] = "loan_application_history"

    def to_dict(self) -> Any:
        return super().to_dict()
