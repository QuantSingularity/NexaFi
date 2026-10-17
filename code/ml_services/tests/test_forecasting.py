from datetime import date

import numpy as np
import pytest
from ai_models.core.errors import InsufficientDataError, ValidationError
from ai_models.forecasting.cashflow import CashFlowForecaster
from ai_models.forecasting.series import build_series


def weekly(n, trend=5.0, noise=30.0, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    return (
        1000 + trend * t + 300 * np.sin(2 * np.pi * t / 7) + rng.normal(0, noise, n)
    ).tolist()


def test_ml_model_beats_naive_baseline_on_seasonal_trend_data():
    result = CashFlowForecaster().forecast({"daily_cash_flows": weekly(150)}, 14)
    metrics = result["metrics"]
    assert result["summary"]["method"] in ("ridge", "gradient_boosting")
    assert metrics["skill_vs_seasonal_naive"] > 0.2
    assert len(result["forecast"]) == 14
    first = result["forecast"][0]
    assert (
        first["confidence_interval"]["lower"]
        < first["predicted_cash_flow"]
        < first["confidence_interval"]["upper"]
    )


def test_intervals_widen_with_horizon():
    forecast = CashFlowForecaster().forecast({"daily_cash_flows": weekly(120)}, 30)[
        "forecast"
    ]
    width = (
        lambda p: p["confidence_interval"]["upper"] - p["confidence_interval"]["lower"]
    )
    assert width(forecast[-1]) > width(forecast[0])


def test_forecast_dates_follow_as_of_date():
    result = CashFlowForecaster().forecast(
        {"daily_cash_flows": weekly(60)}, 3, as_of=date(2026, 9, 28)
    )
    assert [p["date"] for p in result["forecast"]] == [
        "2026-09-29",
        "2026-09-30",
        "2026-10-01",
    ]


def test_negative_cash_flow_is_preserved():
    result = CashFlowForecaster().forecast(
        {"daily_cash_flows": [-200 + 10 * np.sin(i) for i in range(60)]}, 3
    )
    assert all(p["predicted_cash_flow"] < 0 for p in result["forecast"])


@pytest.mark.parametrize("n", [7, 10, 20, 30])
def test_short_histories_use_baselines_with_warning(n):
    result = CashFlowForecaster().forecast({"daily_cash_flows": weekly(n)}, 5)
    assert result["summary"]["method"] in ("seasonal_naive", "level_trend")
    assert result["warnings"]


def test_transactions_are_aggregated_into_daily_series():
    transactions = [
        {"date": f"2026-09-{d:02d}", "amount": 100, "type": "credit"}
        for d in range(1, 29)
    ]
    transactions.append({"date": "2026-09-10", "amount": 40, "type": "debit"})
    series = build_series({"transactions": transactions}, date(2026, 9, 28))
    assert len(series) == 28
    assert series.values[9] == 60.0
    assert series.source == "transactions"


def test_parametric_baseline_is_flagged():
    result = CashFlowForecaster().forecast({"average_monthly_cash_flow": 30000}, 5)
    assert result["summary"]["data_source"] == "parametric_baseline"
    assert result["warnings"]


def test_invalid_inputs():
    forecaster = CashFlowForecaster()
    with pytest.raises(InsufficientDataError):
        forecaster.forecast({})
    with pytest.raises(ValidationError):
        forecaster.forecast({"daily_cash_flows": "abc"})
    with pytest.raises(ValidationError):
        forecaster.forecast({"daily_cash_flows": [1, 2, "x", 4, 5, 6, 7]})
    with pytest.raises(ValidationError):
        forecaster.forecast({"daily_cash_flows": weekly(30)}, days_ahead=500)


def test_instances_do_not_share_state():
    a = CashFlowForecaster().forecast({"daily_cash_flows": weekly(80, trend=10)}, 3)
    b = CashFlowForecaster().forecast({"daily_cash_flows": weekly(80, trend=-10)}, 3)
    assert (
        a["forecast"][0]["predicted_cash_flow"]
        != b["forecast"][0]["predicted_cash_flow"]
    )
