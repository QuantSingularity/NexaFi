import tempfile

import numpy as np
import pytest
from ai_models.core.errors import InsufficientDataError, NotFoundError, ValidationError
from ai_models.credit.model import CreditModelStore, synthetic_population
from ai_models.credit.scorer import CreditScorer
from ai_models.monitoring.drift import credit_input_drift

STRONG = {
    "annual_revenue": 2_000_000,
    "business_age_months": 100,
    "payment_history_score": 92,
    "credit_utilization": 0.15,
    "num_credit_inquiries": 0,
    "debt_to_equity": 0.5,
    "cash_flow_stability": 0.85,
    "employee_count": 30,
}
WEAK = {
    "annual_revenue": 60_000,
    "business_age_months": 5,
    "payment_history_score": 40,
    "credit_utilization": 0.9,
    "num_credit_inquiries": 8,
    "debt_to_equity": 5,
    "cash_flow_stability": 0.2,
    "employee_count": 2,
}


@pytest.fixture
def scorer():
    return CreditScorer(CreditModelStore(tempfile.mkdtemp()))


def test_model_card_is_honest_about_training_data(scorer):
    card = scorer.model_card()
    assert card["training_data"] == "synthetic_bootstrap"
    assert card["warning"]
    assert 0.6 < card["metrics"]["auc"] < 0.95


def test_strong_applicant_outscores_weak(scorer):
    strong, weak = scorer.score(STRONG), scorer.score(WEAK)
    assert strong["credit_score"] > weak["credit_score"] + 150
    assert strong["probability_of_default"] < weak["probability_of_default"]
    assert strong["decision"] == "approve" and weak["decision"] == "decline"
    assert 300 <= weak["credit_score"] <= strong["credit_score"] <= 850


def test_factor_points_are_additive(scorer):
    result = scorer.score(
        {**STRONG, "payment_history_score": 75, "credit_utilization": 0.4}
    )
    total = result["baseline_score"] + sum(result["factors"].values())
    assert total == pytest.approx(result["credit_score"], abs=1.5)


def test_factor_direction_matches_economics(scorer):
    result = scorer.score(WEAK)
    assert result["factors"]["payment_history_score"] < 0
    assert result["factors"]["credit_utilization"] < 0
    assert result["recommendations"]


def test_missing_fields_are_imputed_and_reported(scorer):
    result = scorer.score({"payment_history_score": 80})
    assert "credit_utilization" in result["imputed_features"]
    assert result["data_completeness"] < 0.3


def test_aliases_and_derived_leverage(scorer):
    result = scorer.score(
        {
            "annual_income": 500000,
            "months_in_business": 36,
            "total_debt": 100,
            "total_equity": 100,
        }
    )
    assert "annual_revenue" not in result["imputed_features"]
    assert "debt_to_equity" not in result["imputed_features"]


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"payment_history_score": 150},
        {"credit_utilization": "x"},
        {"annual_revenue": -5},
        {"payment_history_score": True},
        "text",
    ],
)
def test_invalid_inputs_rejected(scorer, bad):
    with pytest.raises(ValidationError):
        scorer.score(bad)


def test_scores_are_deterministic_and_persisted():
    directory = tempfile.mkdtemp()
    first = CreditScorer(CreditModelStore(directory)).score(STRONG)
    second = CreditScorer(CreditModelStore(directory)).score(STRONG)
    assert first["credit_score"] == second["credit_score"]
    assert CreditModelStore(directory).versions() == [1]


def _outcomes(n, seed):
    X, y = synthetic_population(n, seed)
    records = []
    for row, defaulted in zip(X, y):
        record = {
            "annual_revenue": float(np.expm1(row[0])),
            "business_age_months": float(np.expm1(row[1])),
            "employee_count": float(np.expm1(row[2])),
            "payment_history_score": float(row[3]),
            "credit_utilization": float(row[4]),
            "num_credit_inquiries": float(row[5]),
            "debt_to_equity": float(row[6]),
            "cash_flow_stability": float(row[7]),
            "defaulted": bool(defaulted),
        }
        records.append(record)
    return records


def test_retraining_on_observed_outcomes_creates_new_version():
    store = CreditModelStore(tempfile.mkdtemp())
    scorer = CreditScorer(store)
    assert scorer.model.version == 1
    model = store.retrain(_outcomes(1500, 3))
    assert model.version == 2
    assert model.training_data.startswith("observed_outcomes")
    assert scorer.score(STRONG)["model"]["version"] == 2
    assert scorer.model_card()["warning"] is None
    assert store.load(1).training_data == "synthetic_bootstrap"
    with pytest.raises(NotFoundError):
        store.load(9)


def test_retraining_requires_enough_labelled_data():
    store = CreditModelStore(tempfile.mkdtemp())
    with pytest.raises(InsufficientDataError):
        store.retrain(_outcomes(50, 1))
    with pytest.raises(ValidationError):
        store.retrain([{"annual_revenue": 1}])


def test_input_drift_detection():
    store = CreditModelStore(tempfile.mkdtemp())
    model = store.current()
    base = [
        {k: v for k, v in r.items() if k != "defaulted"} for r in _outcomes(300, 99)
    ]
    assert credit_input_drift(model, base)["status"] == "stable"
    shifted = [
        dict(
            r,
            payment_history_score=r["payment_history_score"] * 0.5,
            credit_utilization=min(1.4, r["credit_utilization"] * 2.2),
        )
        for r in base
    ]
    assert credit_input_drift(model, shifted)["status"] == "significant"
    with pytest.raises(InsufficientDataError):
        credit_input_drift(model, base[:5])
