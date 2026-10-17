import math
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from ai_models.core.errors import InsufficientDataError
from ai_models.core.validation import as_int
from ai_models.forecasting.series import build_series
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

CONFIDENCE_LEVEL = 0.90
CV_STEP = 7
CV_FOLDS = 3
MIN_ML_DAYS = 42
MIN_DAYS = 7
MAX_HORIZON = 180


def _calendar(day: date) -> List[float]:
    weekday = day.weekday()
    next_day = day + timedelta(days=1)
    return [
        math.sin(2 * math.pi * weekday / 7),
        math.cos(2 * math.pi * weekday / 7),
        day.day / 31.0,
        1.0 if next_day.month != day.month else 0.0,
        1.0 if weekday >= 5 else 0.0,
    ]


def _lags(window: np.ndarray) -> List[float]:
    last14 = window[-14:]
    lag7 = float(window[-7]) if len(window) >= 7 else float(window.mean())
    slope = (
        float(np.polyfit(np.arange(len(last14)), last14, 1)[0])
        if len(last14) >= 3
        else 0.0
    )
    return [
        float(window[-1]),
        lag7,
        float(window[-7:].mean()),
        float(last14.mean()),
        float(last14.std()),
        slope,
    ]


def _features(day: date, window: np.ndarray) -> List[float]:
    return _calendar(day) + _lags(window)


def _design(
    values: np.ndarray, dates: List[date], start: int
) -> Tuple[np.ndarray, np.ndarray]:
    rows = [
        _features(dates[i], values[max(0, i - 28) : i])
        for i in range(start, len(values))
    ]
    return np.array(rows), values[start:]


class _SeasonalNaive:
    name = "seasonal_naive"

    def fit(self, values: np.ndarray, dates: List[date]) -> "_SeasonalNaive":
        self.values, self.dates = values, dates
        return self

    def predict(self, days: List[date]) -> np.ndarray:
        by_weekday: Dict[int, List[float]] = {}
        for value, day in zip(self.values[-35:], self.dates[-35:]):
            by_weekday.setdefault(day.weekday(), []).append(float(value))
        overall = float(np.mean(self.values[-28:]))
        return np.array(
            [float(np.mean(by_weekday.get(d.weekday(), [overall]))) for d in days]
        )


class _LevelTrend:
    name = "level_trend"
    PHI = 0.9

    def fit(self, values: np.ndarray, dates: List[date]) -> "_LevelTrend":
        alpha = 0.3
        level = float(values[0])
        for value in values[1:]:
            level = alpha * float(value) + (1 - alpha) * level
        tail = values[-14:]
        self.level = level
        self.slope = (
            float(np.polyfit(np.arange(len(tail)), tail, 1)[0])
            if len(tail) >= 3
            else 0.0
        )
        return self

    def predict(self, days: List[date]) -> np.ndarray:
        out, cumulative = [], 0.0
        for h in range(1, len(days) + 1):
            cumulative += self.PHI**h
            out.append(self.level + self.slope * cumulative)
        return np.array(out)


class _Regressor:
    def __init__(self, name: str, factory: Callable[[], Any]) -> None:
        self.name = name
        self.factory = factory

    def fit(self, values: np.ndarray, dates: List[date]) -> "_Regressor":
        start = min(14, len(values) - 10)
        X, y = _design(values, dates, max(start, 7))
        self.model = self.factory()
        self.model.fit(X, y)
        self.values, self.dates = list(values), list(dates)
        return self

    def predict(self, days: List[date]) -> np.ndarray:
        history = list(self.values)
        out = []
        for day in days:
            row = np.array([_features(day, np.array(history[-28:]))])
            value = float(self.model.predict(row)[0])
            out.append(value)
            history.append(value)
        return np.array(out)


def _candidates(n: int, seed: int) -> List[Callable[[], Any]]:
    makers: List[Callable[[], Any]] = [_SeasonalNaive, _LevelTrend]
    if n >= MIN_ML_DAYS:
        makers.append(
            lambda: _Regressor(
                "ridge", lambda: make_pipeline(StandardScaler(), Ridge(alpha=3.0))
            )
        )
        makers.append(
            lambda: _Regressor(
                "gradient_boosting",
                lambda: GradientBoostingRegressor(
                    n_estimators=120,
                    max_depth=3,
                    learning_rate=0.05,
                    subsample=0.8,
                    random_state=seed,
                ),
            )
        )
    return makers


def _future_days(last: date, steps: int) -> List[date]:
    return [last + timedelta(days=i) for i in range(1, steps + 1)]


def _cv_step(n: int) -> int:
    return min(CV_STEP, max(2, n // 3))


def _cross_validate(
    makers: List[Callable[[], Any]], values: np.ndarray, dates: List[date]
) -> Dict[str, Dict[str, Any]]:
    n = len(values)
    step = _cv_step(n)
    min_train = 14 if n >= 28 else 5
    origins = [
        n - step * k for k in range(CV_FOLDS, 0, -1) if n - step * k >= min_train
    ]
    results: Dict[str, Dict[str, Any]] = {}
    for make in makers:
        errors: List[np.ndarray] = []
        actuals: List[np.ndarray] = []
        name = None
        for origin in origins:
            model = make().fit(values[:origin], dates[:origin])
            name = model.name
            horizon = min(step, n - origin)
            predicted = model.predict(_future_days(dates[origin - 1], horizon))
            actual = values[origin : origin + horizon]
            errors.append(predicted - actual)
            actuals.append(actual)
        if name is None:
            name = make().name
        if errors:
            flat = np.concatenate(errors)
            truth = np.concatenate(actuals)
            denom = np.abs(truth) + np.abs(truth + flat)
            smape = float(
                np.mean(
                    np.where(
                        denom == 0,
                        0.0,
                        2 * np.abs(flat) / np.where(denom == 0, 1, denom),
                    )
                )
            )
            results[name] = {
                "mae": float(np.mean(np.abs(flat))),
                "rmse": float(np.sqrt(np.mean(flat**2))),
                "smape": smape,
                "errors": errors,
            }
    return results


class CashFlowForecaster:
    def __init__(self, seed: int = 42) -> None:
        self.seed = seed

    def forecast(
        self,
        historical_data: Dict[str, Any],
        days_ahead: Any = 30,
        as_of: Optional[date] = None,
    ) -> Dict[str, Any]:
        horizon = as_int(days_ahead, "days_ahead", 1, MAX_HORIZON, 30)
        series = build_series(historical_data, as_of)
        if len(series) < MIN_DAYS:
            raise InsufficientDataError(
                f"At least {MIN_DAYS} days of history are required",
                {"days": len(series)},
            )
        values, dates = series.values, series.dates
        warnings = list(series.warnings)
        makers = _candidates(len(values), self.seed)
        scores = _cross_validate(makers, values, dates)
        if not scores:
            raise InsufficientDataError(
                "History is too short to validate a forecast model"
            )
        chosen = min(scores, key=lambda key: scores[key]["mae"])
        winner = next(make for make in makers if _name_of(make) == chosen)
        model = winner().fit(values, dates)
        days = _future_days(series.end_date, horizon)
        point = model.predict(days)
        pooled = np.abs(np.concatenate(scores[chosen]["errors"]))
        if len(pooled) >= 5:
            base_error = float(np.quantile(pooled, CONFIDENCE_LEVEL))
        else:
            base_error = (
                float(np.std(np.diff(values)) * 1.645)
                if len(values) > 2
                else float(abs(values).mean())
            )
        base_error = max(base_error, 1e-6)
        forecasts = []
        for h, (day, value) in enumerate(zip(days, point), start=1):
            half = base_error * math.sqrt(max(1.0, h / _cv_step(len(values))))
            forecasts.append(
                {
                    "date": day.isoformat(),
                    "predicted_cash_flow": round(float(value), 2),
                    "confidence_interval": {
                        "lower": round(float(value - half), 2),
                        "upper": round(float(value + half), 2),
                    },
                    "confidence_level": CONFIDENCE_LEVEL,
                }
            )
        naive = scores.get("seasonal_naive", {}).get("mae")
        mae = scores[chosen]["mae"]
        skill = 1.0 - mae / naive if naive and naive > 0 else 0.0
        if len(values) < MIN_ML_DAYS:
            warnings.append(
                f"Only {len(values)} days of history, statistical baselines used instead of machine learning models"
            )
        total = float(sum(f["predicted_cash_flow"] for f in forecasts))
        return {
            "forecast": forecasts,
            "summary": {
                "total_predicted_cash_flow": round(total, 2),
                "average_daily_cash_flow": round(total / len(forecasts), 2),
                "method": chosen,
                "data_source": series.source,
                "history_days": len(values),
                "confidence_level": CONFIDENCE_LEVEL,
            },
            "metrics": {
                "cv_mae": round(mae, 4),
                "cv_rmse": round(scores[chosen]["rmse"], 4),
                "cv_smape": round(scores[chosen]["smape"], 4),
                "skill_vs_seasonal_naive": round(skill, 4),
                "folds": len(scores[chosen]["errors"]),
                "candidates": {k: round(v["mae"], 4) for k, v in scores.items()},
            },
            "warnings": warnings,
        }


def _name_of(make: Callable[[], Any]) -> str:
    if isinstance(make, type):
        return make.name
    return make().name
