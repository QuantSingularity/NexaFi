from typing import Any, Dict, List

import numpy as np
from ai_models.core.validation import as_float, require_dict
from ai_models.forecasting.series import build_series
from scipy import stats

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2, "positive": 3}


def _insight(
    kind: str,
    title: str,
    text: str,
    severity: str,
    category: str,
    evidence: Dict[str, Any],
    actions: List[str],
) -> Dict[str, Any]:
    return {
        "insight_type": kind,
        "title": title,
        "description": text,
        "severity": severity,
        "category": category,
        "evidence": evidence,
        "recommendations": actions,
    }


def _money(value: float) -> str:
    return f"{value:,.0f}"


class InsightEngine:
    def generate(self, financial_data: Any) -> Dict[str, Any]:
        data = require_dict(financial_data, "financial_data")
        insights: List[Dict[str, Any]] = []
        notes: List[str] = []
        series = None
        if data.get("daily_cash_flows") or data.get("transactions"):
            series = build_series(data)
            values = series.values
            insights += self._trend(values)
            insights += self._volatility(values)
            balance = as_float(data.get("balance"), "balance", default=None)
            insights += self._runway(values, balance)
        else:
            notes.append("No cash flow history supplied, cash flow insights skipped")
        insights += self._categories(data.get("expenses_by_category"))
        insights += self._concentration(data.get("revenue_by_customer"))
        insights.sort(key=lambda item: SEVERITY_ORDER.get(item["severity"], 9))
        return {"insights": insights, "count": len(insights), "notes": notes}

    def _trend(self, values: np.ndarray) -> List[Dict[str, Any]]:
        if len(values) < 28:
            return []
        recent, prior = values[-14:], values[-28:-14]
        mean_recent, mean_prior = float(recent.mean()), float(prior.mean())
        if abs(mean_prior) < 1e-9:
            return []
        change = (mean_recent - mean_prior) / abs(mean_prior)
        if recent.std() < 1e-9 and prior.std() < 1e-9:
            return []
        p_value = float(stats.ttest_ind(recent, prior, equal_var=False).pvalue)
        if abs(change) < 0.10 or p_value > 0.10:
            return []
        evidence = {
            "recent_14d_mean": round(mean_recent, 2),
            "prior_14d_mean": round(mean_prior, 2),
            "change_pct": round(change * 100, 1),
            "p_value": round(p_value, 4),
        }
        if change < 0:
            return [
                _insight(
                    "cash_flow_trend",
                    "Cash flow is declining",
                    f"Average daily cash flow fell {abs(change) * 100:.1f}% over the last 14 days compared with the 14 days before (from {_money(mean_prior)} to {_money(mean_recent)}).",
                    "warning",
                    "cash_flow",
                    evidence,
                    [
                        "Review receivables aging and chase overdue invoices",
                        "Defer discretionary spending until the trend stabilises",
                    ],
                )
            ]
        return [
            _insight(
                "cash_flow_trend",
                "Cash flow is improving",
                f"Average daily cash flow rose {change * 100:.1f}% over the last 14 days compared with the 14 days before (from {_money(mean_prior)} to {_money(mean_recent)}).",
                "positive",
                "cash_flow",
                evidence,
                ["Consider moving surplus cash into reserves or a sweep account"],
            )
        ]

    def _volatility(self, values: np.ndarray) -> List[Dict[str, Any]]:
        if len(values) < 21:
            return []
        mean = float(values.mean())
        if abs(mean) < 1e-9:
            return []
        cv = float(values.std(ddof=1) / abs(mean))
        if cv < 1.5:
            return []
        return [
            _insight(
                "cash_flow_volatility",
                "Cash flow is highly volatile",
                f"Daily cash flow varies by {cv:.1f} times its average, which makes short term planning difficult.",
                "info",
                "cash_flow",
                {"coefficient_of_variation": round(cv, 2), "days": int(len(values))},
                [
                    "Keep a buffer equal to at least two weeks of average outflows",
                    "Stagger large payments to smooth outflows",
                ],
            )
        ]

    def _runway(self, values: np.ndarray, balance: Any) -> List[Dict[str, Any]]:
        if balance is None or len(values) < 14:
            return []
        recent = values[-30:]
        mean = float(recent.mean())
        if mean >= 0:
            return []
        days = balance / abs(mean) if balance > 0 else 0.0
        severity = "critical" if days < 30 else "warning" if days < 90 else "info"
        return [
            _insight(
                "runway",
                "Cash runway based on current burn",
                f"At the recent net burn of {_money(abs(mean))} per day, a balance of {_money(balance)} lasts about {days:.0f} days.",
                severity,
                "liquidity",
                {
                    "balance": balance,
                    "average_daily_burn": round(abs(mean), 2),
                    "runway_days": round(days, 1),
                },
                [
                    "Cut or defer non essential outflows",
                    "Line up financing before the runway drops below 90 days",
                ],
            )
        ]

    def _categories(self, categories: Any) -> List[Dict[str, Any]]:
        if not isinstance(categories, dict):
            return []
        out = []
        for name, series in categories.items():
            if not isinstance(series, (list, tuple)) or len(series) < 4:
                continue
            try:
                values = np.array([float(v) for v in series], dtype=float)
            except (TypeError, ValueError):
                continue
            latest, history = values[-1], values[:-1]
            median = float(np.median(history))
            if median <= 0 or latest < median * 1.25:
                continue
            rise = latest / median - 1.0
            out.append(
                _insight(
                    "expense_spike",
                    f"{name} spending is above its norm",
                    f"{name} spending is {_money(latest)} this period, {rise * 100:.0f}% above its typical {_money(median)}.",
                    "warning" if rise >= 0.5 else "info",
                    "expenses",
                    {
                        "category": name,
                        "latest": round(latest, 2),
                        "typical": round(median, 2),
                        "increase_pct": round(rise * 100, 1),
                    },
                    [
                        f"Review recent {name} transactions for one off charges or duplicates"
                    ],
                )
            )
        return out

    def _concentration(self, customers: Any) -> List[Dict[str, Any]]:
        if not isinstance(customers, dict) or len(customers) < 2:
            return []
        try:
            amounts = {k: float(v) for k, v in customers.items()}
        except (TypeError, ValueError):
            return []
        total = sum(v for v in amounts.values() if v > 0)
        if total <= 0:
            return []
        name, top = max(amounts.items(), key=lambda kv: kv[1])
        share = top / total
        if share < 0.40:
            return []
        return [
            _insight(
                "revenue_concentration",
                "Revenue depends on one customer",
                f"{name} accounts for {share * 100:.0f}% of revenue, so losing them would significantly affect cash flow.",
                "warning" if share >= 0.5 else "info",
                "revenue",
                {"customer": name, "share_pct": round(share * 100, 1)},
                [
                    "Diversify the customer base",
                    "Negotiate longer contract terms with the largest customer",
                ],
            )
        ]
