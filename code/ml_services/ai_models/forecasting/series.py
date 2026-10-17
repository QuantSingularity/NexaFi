from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
from ai_models.core.errors import InsufficientDataError, ValidationError
from ai_models.core.validation import (
    as_float,
    as_float_list,
    parse_timestamp,
    require_dict,
    utcnow,
)

MAX_HISTORY_DAYS = 1095


@dataclass
class DailySeries:
    values: np.ndarray
    end_date: date
    source: str
    warnings: List[str] = field(default_factory=list)

    @property
    def dates(self) -> List[date]:
        n = len(self.values)
        return [self.end_date - timedelta(days=n - 1 - i) for i in range(n)]

    def __len__(self) -> int:
        return len(self.values)


def _transaction_amount(item: Dict[str, Any]) -> float:
    amount = as_float(item.get("amount"), "transactions.amount")
    if amount is None:
        raise ValidationError("Each transaction requires an amount")
    kind = str(item.get("type", item.get("direction", ""))).lower()
    if kind in ("debit", "expense", "outflow", "withdrawal", "payment", "out"):
        return -abs(amount)
    if kind in ("credit", "income", "inflow", "deposit", "in"):
        return abs(amount)
    return amount


def from_transactions(
    transactions: List[Dict[str, Any]], as_of: Optional[date] = None
) -> DailySeries:
    if not transactions:
        raise InsufficientDataError("No transactions supplied")
    buckets: Dict[date, float] = {}
    for item in transactions:
        item = require_dict(item, "transaction")
        stamp = parse_timestamp(
            item.get("date") or item.get("timestamp") or item.get("created_at"),
            "transaction date",
        )
        day = stamp.date()
        buckets[day] = buckets.get(day, 0.0) + _transaction_amount(item)
    first, last = min(buckets), max(buckets)
    end = as_of or last
    if end < last:
        end = last
    start = max(first, end - timedelta(days=MAX_HISTORY_DAYS - 1))
    n = (end - start).days + 1
    values = np.array(
        [buckets.get(start + timedelta(days=i), 0.0) for i in range(n)], dtype=float
    )
    return DailySeries(values, end, "transactions")


def parametric_baseline(data: Dict[str, Any], as_of: date) -> DailySeries:
    monthly = as_float(
        data.get("average_monthly_cash_flow"), "average_monthly_cash_flow", default=None
    )
    if monthly is None:
        raise InsufficientDataError(
            "Provide daily_cash_flows, transactions or average_monthly_cash_flow",
            {"minimum_days": 7},
        )
    trend = as_float(data.get("revenue_trend"), "revenue_trend", 0.0, 1.0, 0.5)
    seasonal = as_float(
        data.get("seasonality_index"), "seasonality_index", 0.0, 1.0, 0.3
    )
    base = monthly / 30.0
    t = np.arange(35, dtype=float)
    values = (
        base
        + base * 0.01 * (t - t.mean()) * (trend - 0.5) * 2
        + base * seasonal * np.sin(2 * np.pi * t / 7)
    )
    return DailySeries(
        values,
        as_of,
        "parametric_baseline",
        ["Forecast is derived from summary inputs only, not observed daily history"],
    )


def build_series(data: Dict[str, Any], as_of: Optional[date] = None) -> DailySeries:
    data = require_dict(data, "historical_data")
    today = as_of or utcnow().date()
    daily = as_float_list(
        data.get("daily_cash_flows"), "daily_cash_flows", MAX_HISTORY_DAYS
    )
    if len(daily) >= 7:
        return DailySeries(
            np.array(daily[-MAX_HISTORY_DAYS:], dtype=float), today, "daily_cash_flows"
        )
    transactions = data.get("transactions")
    if transactions:
        if not isinstance(transactions, list):
            raise ValidationError("transactions must be a list")
        series = from_transactions(transactions, today)
        if len(series) >= 7:
            return series
        if "average_monthly_cash_flow" not in data:
            raise InsufficientDataError(
                f"Transactions cover only {len(series)} days, at least 7 are required",
                {"days": len(series), "minimum_days": 7},
            )
    return parametric_baseline(data, today)
