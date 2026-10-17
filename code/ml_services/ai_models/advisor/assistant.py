from typing import Any, Dict, List, Optional, Tuple

from ai_models.anomaly.detector import TransactionAnomalyDetector
from ai_models.core.errors import MLError, ValidationError
from ai_models.core.validation import require_dict
from ai_models.credit.features import FEATURE_NAMES
from ai_models.credit.scorer import CreditScorer
from ai_models.forecasting.cashflow import CashFlowForecaster
from ai_models.insights.engine import InsightEngine

INTENTS: Dict[str, Tuple[str, ...]] = {
    "cash_flow_forecast": (
        "forecast",
        "predict",
        "cash flow",
        "cashflow",
        "runway",
        "next month",
        "next week",
        "projection",
    ),
    "credit_assessment": (
        "credit score",
        "creditworthiness",
        "loan",
        "borrow",
        "eligib",
        "credit rating",
        "underwriting",
    ),
    "anomaly_review": (
        "suspicious",
        "fraud",
        "anomal",
        "unusual",
        "strange transaction",
        "risk transaction",
    ),
    "financial_insights": (
        "insight",
        "expense",
        "spending",
        "cost",
        "reduce",
        "save money",
        "profit",
        "revenue",
    ),
    "capabilities": ("help", "what can you", "how do you", "capabilit", "hello", "hi "),
}
MAX_MESSAGE = 2000


def classify(message: str) -> Tuple[str, List[str]]:
    text = f" {message.lower()} "
    best, best_hits = "capabilities", []
    for intent, terms in INTENTS.items():
        hits = [t for t in terms if t in text]
        if len(hits) > len(best_hits) or (hits and not best_hits):
            best, best_hits = intent, hits
    if not best_hits:
        return "unknown", []
    return best, best_hits


def _pick(context: Dict[str, Any], *keys: str) -> Optional[Dict[str, Any]]:
    for key in keys:
        value = context.get(key)
        if isinstance(value, dict) and value:
            return value
    return None


class FinancialAssistant:
    def __init__(
        self,
        forecaster: Optional[CashFlowForecaster] = None,
        scorer: Optional[CreditScorer] = None,
        detector: Optional[TransactionAnomalyDetector] = None,
        insights: Optional[InsightEngine] = None,
    ) -> None:
        self.forecaster = forecaster or CashFlowForecaster()
        self.scorer = scorer or CreditScorer()
        self.detector = detector or TransactionAnomalyDetector()
        self.insights = insights or InsightEngine()

    def respond(self, message: Any, context: Any = None) -> Dict[str, Any]:
        if not isinstance(message, str) or not message.strip():
            raise ValidationError("message is required")
        if len(message) > MAX_MESSAGE:
            raise ValidationError(f"message must be at most {MAX_MESSAGE} characters")
        context = require_dict(context, "context")
        intent, terms = classify(message)
        handler = getattr(self, f"_{intent}", self._unknown)
        try:
            reply = handler(context)
        except MLError as exc:
            reply = {
                "content": f"I could not complete that analysis: {exc.message}.",
                "data": None,
                "suggested_actions": [],
                "requires_data": [],
            }
        reply.update(intent=intent, matched_terms=terms)
        return reply

    def _cash_flow_forecast(self, context: Dict[str, Any]) -> Dict[str, Any]:
        data = _pick(context, "historical_data", "financial_data")
        if data is None and context.get("transactions"):
            data = {"transactions": context["transactions"]}
        if data is None:
            return self._needs(
                "To forecast cash flow I need your recent history.",
                [
                    "historical_data.daily_cash_flows (at least 7 daily net amounts) or transactions"
                ],
            )
        result = self.forecaster.forecast(data, 30)
        summary, metrics = result["summary"], result["metrics"]
        return {
            "content": (
                f"Over the next 30 days I project a net cash flow of {summary['total_predicted_cash_flow']:,.0f} "
                f"(about {summary['average_daily_cash_flow']:,.0f} per day) using the {summary['method']} model, "
                f"which scored a cross validated mean absolute error of {metrics['cv_mae']:,.0f} per day."
            ),
            "data": {
                "summary": summary,
                "metrics": metrics,
                "warnings": result["warnings"],
            },
            "suggested_actions": ["Open the cash flow forecast for daily detail"],
            "requires_data": [],
        }

    def _credit_assessment(self, context: Dict[str, Any]) -> Dict[str, Any]:
        data = _pick(context, "business_data", "credit_data")
        if data is None:
            return self._needs(
                "To assess creditworthiness I need business details.",
                list(FEATURE_NAMES),
            )
        result = self.scorer.score(data)
        advice = result["recommendations"][:2]
        tail = f" Biggest improvement levers: {'; '.join(advice)}." if advice else ""
        return {
            "content": (
                f"The estimated credit score is {result['credit_score']} ({result['risk_category']} risk) with a "
                f"{result['probability_of_default'] * 100:.1f}% estimated probability of default. "
                f"Policy outcome: {result['decision'].replace('_', ' ')}.{tail}"
            ),
            "data": {
                k: result[k]
                for k in (
                    "credit_score",
                    "risk_category",
                    "decision",
                    "factors",
                    "model",
                )
            },
            "suggested_actions": advice,
            "requires_data": [],
        }

    def _anomaly_review(self, context: Dict[str, Any]) -> Dict[str, Any]:
        transactions = context.get("transactions")
        if not isinstance(transactions, list) or not transactions:
            return self._needs(
                "To review transactions for anomalies I need a list of them.",
                ["transactions"],
            )
        scores = self.detector.score_batch(transactions)
        flagged = [
            {"index": i, "risk_score": s["risk_score"], "reasons": s["reasons"]}
            for i, s in enumerate(scores)
            if s["risk_level"] != "low"
        ]
        flagged.sort(key=lambda item: item["risk_score"], reverse=True)
        content = (
            f"{len(flagged)} of {len(transactions)} transactions look unusual."
            if flagged
            else f"None of the {len(transactions)} transactions look unusual."
        )
        return {
            "content": content,
            "data": {"flagged": flagged[:10], "reviewed": len(transactions)},
            "suggested_actions": ["Review the flagged transactions"] if flagged else [],
            "requires_data": [],
        }

    def _financial_insights(self, context: Dict[str, Any]) -> Dict[str, Any]:
        data = _pick(context, "financial_data", "historical_data")
        if data is None:
            return self._needs(
                "To produce insights I need your financial data.",
                [
                    "financial_data.daily_cash_flows",
                    "financial_data.expenses_by_category",
                    "financial_data.revenue_by_customer",
                ],
            )
        result = self.insights.generate(data)
        if not result["insights"]:
            return {
                "content": "I found nothing notable in the data provided.",
                "data": result,
                "suggested_actions": [],
                "requires_data": [],
            }
        top = result["insights"][0]
        return {
            "content": f"{len(result['insights'])} insights found. Most important: {top['title']}. {top['description']}",
            "data": result,
            "suggested_actions": top["recommendations"],
            "requires_data": [],
        }

    def _capabilities(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "content": "I can forecast cash flow, score business creditworthiness, flag unusual transactions and surface insights from your data. Send the relevant data in the context and ask.",
            "data": None,
            "suggested_actions": [
                "Ask for a 30 day cash flow forecast",
                "Ask for a credit assessment",
            ],
            "requires_data": [],
        }

    def _unknown(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "content": "I did not recognise that request. I can help with cash flow forecasts, credit assessments, transaction anomalies and financial insights.",
            "data": None,
            "suggested_actions": [],
            "requires_data": [],
        }

    @staticmethod
    def _needs(text: str, fields: List[str]) -> Dict[str, Any]:
        return {
            "content": text,
            "data": None,
            "suggested_actions": [],
            "requires_data": fields,
        }
