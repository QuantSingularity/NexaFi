import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Tuple

from ai_models.core.errors import ValidationError
from ai_models.core.validation import as_float, require_dict


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    low: float
    high: float
    default: float
    transform: Callable[[float], float]
    label: str
    advice: str


def _identity(value: float) -> float:
    return value


def _log(value: float) -> float:
    return math.log1p(max(value, 0.0))


FEATURES: Tuple[FeatureSpec, ...] = (
    FeatureSpec(
        "annual_revenue",
        0.0,
        1e10,
        250_000.0,
        _log,
        "Annual revenue",
        "Grow and document recurring revenue",
    ),
    FeatureSpec(
        "business_age_months",
        0.0,
        1200.0,
        24.0,
        _log,
        "Business age",
        "Longer operating history strengthens applications",
    ),
    FeatureSpec(
        "employee_count",
        0.0,
        1e6,
        5.0,
        _log,
        "Employee count",
        "Team size is a minor factor",
    ),
    FeatureSpec(
        "payment_history_score",
        0.0,
        100.0,
        70.0,
        _identity,
        "Payment history",
        "Pay every obligation on time to lift payment history",
    ),
    FeatureSpec(
        "credit_utilization",
        0.0,
        1.5,
        0.4,
        _identity,
        "Credit utilization",
        "Reduce revolving balances below 30 percent of limits",
    ),
    FeatureSpec(
        "num_credit_inquiries",
        0.0,
        50.0,
        2.0,
        _identity,
        "Recent credit inquiries",
        "Limit new credit applications over the next six months",
    ),
    FeatureSpec(
        "debt_to_equity",
        0.0,
        100.0,
        1.0,
        _identity,
        "Debt to equity",
        "Lower leverage by paying down debt or raising equity",
    ),
    FeatureSpec(
        "cash_flow_stability",
        0.0,
        1.0,
        0.6,
        _identity,
        "Cash flow stability",
        "Smooth cash flow with diversified revenue and reserves",
    ),
)
FEATURE_NAMES: Tuple[str, ...] = tuple(spec.name for spec in FEATURES)
ALIASES: Dict[str, str] = {
    "annual_income": "annual_revenue",
    "business_revenue": "annual_revenue",
    "months_in_business": "business_age_months",
    "business_age": "business_age_months",
    "employees": "employee_count",
    "payment_history": "payment_history_score",
    "inquiries": "num_credit_inquiries",
}


def normalize_inputs(data: Any) -> Tuple[Dict[str, float], List[str]]:
    data = dict(require_dict(data, "business_data"))
    for alias, canonical in ALIASES.items():
        if alias in data and canonical not in data:
            data[canonical] = data[alias]
    if "total_debt" in data and "total_equity" in data and "debt_to_equity" not in data:
        equity = as_float(data.get("total_equity"), "total_equity", 0.0)
        debt = as_float(data.get("total_debt"), "total_debt", 0.0)
        if equity and equity > 0:
            data["debt_to_equity"] = debt / equity
    values: Dict[str, float] = {}
    imputed: List[str] = []
    for spec in FEATURES:
        number = as_float(data.get(spec.name), spec.name, spec.low, spec.high, None)
        if number is None:
            number = spec.default
            imputed.append(spec.name)
        values[spec.name] = number
    if len(imputed) == len(FEATURES):
        raise ValidationError(
            "No scoring inputs supplied",
            {"accepted_fields": list(FEATURE_NAMES), "aliases": ALIASES},
        )
    return values, imputed


def transform_vector(values: Dict[str, float]) -> List[float]:
    return [spec.transform(values[spec.name]) for spec in FEATURES]
