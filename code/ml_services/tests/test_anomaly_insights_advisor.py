import numpy as np
import pytest
from ai_models.advisor.assistant import FinancialAssistant, classify
from ai_models.anomaly.detector import TransactionAnomalyDetector
from ai_models.core.errors import ValidationError
from ai_models.insights.engine import InsightEngine

HISTORY = [
    {
        "amount": 40 + (i % 7) * 5,
        "timestamp": f"2026-09-{1 + i % 28:02d}T1{i % 6}:00:00Z",
        "merchant": "cafe",
        "country": "US",
        "currency": "USD",
    }
    for i in range(40)
]


def test_normal_transaction_is_low_risk():
    result = TransactionAnomalyDetector().score_transaction(
        {
            "amount": 45,
            "timestamp": "2026-10-01T12:00:00Z",
            "merchant": "cafe",
            "country": "US",
            "currency": "USD",
        },
        HISTORY,
    )
    assert result["risk_level"] == "low" and result["recommended_action"] == "allow"


def test_unusual_transaction_is_flagged_with_reasons():
    result = TransactionAnomalyDetector().score_transaction(
        {
            "amount": 9800,
            "timestamp": "2026-10-01T03:00:00",
            "merchant": "x",
            "country": "RU",
            "currency": "EUR",
        },
        HISTORY,
    )
    assert result["risk_level"] == "high" and result["is_anomaly"]
    assert result["risk_factors"] == result["reasons"] and len(result["reasons"]) >= 3
    assert result["severity"] == result["risk_level"]


def test_mixed_naive_and_aware_timestamps_do_not_crash():
    history = [{"amount": 50, "timestamp": "2026-09-01T10:00:00"}] * 6 + [
        {"amount": 50, "timestamp": "2026-09-02T10:00:00Z"}
    ] * 6
    result = TransactionAnomalyDetector().score_transaction(
        {"amount": 50, "timestamp": "2026-09-03T10:00:00+02:00"}, history
    )
    assert result["history_size"] == 12


def test_velocity_burst_detected():
    burst = [
        {"amount": 20, "timestamp": f"2026-10-01T10:{m:02d}:00Z"} for m in range(15)
    ]
    result = TransactionAnomalyDetector(velocity_limit=10).score_transaction(
        {"amount": 20, "timestamp": "2026-10-01T10:20:00Z"}, burst
    )
    assert result["signals"]["velocity"] > 0


def test_structuring_just_below_threshold():
    result = TransactionAnomalyDetector().score_transaction(
        {"amount": 9900, "timestamp": "2026-10-01T12:00:00Z"}, HISTORY
    )
    assert result["signals"]["structuring"] > 0


def test_detector_validates_input():
    detector = TransactionAnomalyDetector()
    with pytest.raises(ValidationError):
        detector.score_transaction({"timestamp": "2026-10-01T12:00:00Z"})
    with pytest.raises(ValidationError):
        detector.score_transaction({"amount": 5, "timestamp": "yesterday"})
    assert (
        len(
            detector.score_batch(
                [{"amount": 5, "timestamp": "2026-10-01T12:00:00Z"}] * 3
            )
        )
        == 3
    )


def test_insights_are_derived_from_data():
    rng = np.random.default_rng(1)
    flows = rng.normal(1000, 100, 14).tolist() + rng.normal(700, 100, 14).tolist()
    result = InsightEngine().generate(
        {
            "daily_cash_flows": flows,
            "balance": 20000,
            "expenses_by_category": {"marketing": [1000, 1100, 900, 1000, 2000]},
            "revenue_by_customer": {"A": 90, "B": 10},
        }
    )
    kinds = {i["insight_type"] for i in result["insights"]}
    assert {"cash_flow_trend", "expense_spike", "revenue_concentration"} <= kinds
    trend = next(
        i for i in result["insights"] if i["insight_type"] == "cash_flow_trend"
    )
    assert trend["severity"] == "warning" and trend["evidence"]["change_pct"] < -20


def test_no_data_yields_no_fabricated_insights():
    result = InsightEngine().generate({})
    assert result["insights"] == [] and result["notes"]


def test_runway_insight_uses_balance_and_burn():
    result = InsightEngine().generate(
        {"daily_cash_flows": [-100.0] * 30, "balance": 1500}
    )
    runway = next(i for i in result["insights"] if i["insight_type"] == "runway")
    assert (
        runway["severity"] == "critical" and runway["evidence"]["runway_days"] == 15.0
    )


def test_intent_classification():
    assert classify("forecast my cash flow next month")[0] == "cash_flow_forecast"
    assert classify("is this fraud?")[0] == "anomaly_review"
    assert classify("zzz qqq")[0] == "unknown"


def test_assistant_answers_with_computed_numbers_or_asks_for_data():
    assistant = FinancialAssistant()
    asks = assistant.respond("what is my credit score?")
    assert asks["requires_data"] and asks["data"] is None
    answered = assistant.respond(
        "forecast cash flow",
        {
            "historical_data": {
                "daily_cash_flows": [100 + i % 7 * 10 for i in range(60)]
            }
        },
    )
    assert (
        "30 days" in answered["content"]
        and answered["data"]["summary"]["history_days"] == 60
    )
    with pytest.raises(ValidationError):
        assistant.respond("")
