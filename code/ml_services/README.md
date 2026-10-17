# NexaFi ML Services

Machine learning for NexaFi: cash flow forecasting, business credit scoring, transaction anomaly detection, data driven insights and a financial assistant, served by the AI service and consumed by the credit and payment services and both frontends through the API gateway.

## Layout

```
ml_services/
  ai_models/                 domain package, no web framework dependency
    core/                    errors, input validation, time helpers
    forecasting/             series construction, model selection, cash flow forecaster
    credit/                  features, scorecard model, scorer, retraining store
    anomaly/                 per account statistical transaction detector
    insights/                insights derived from supplied financial data
    advisor/                 intent routing assistant that runs the real models
    monitoring/              population stability drift detection
    explainability/          permutation and occlusion attribution, legacy SHAP and LIME engine
    clients/                 payment history client
  ai-service/                Flask service (app factory, auth, repository, routes)
  analytics-service/         dashboards, metrics and reports service
  tests/                     package and service tests
```

## Models

| Component            | Method                                                                                             | Validation                                                                                                                        |
| -------------------- | -------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Cash flow forecaster | Per request selection between weekly seasonal naive, damped trend, ridge and gradient boosting     | Walk forward cross validation on the supplied history, reported as MAE, RMSE, sMAPE and skill against the seasonal naive baseline |
| Credit scorecard     | Logistic regression scorecard, 300 to 850 score, 50 points to double the odds                      | Holdout AUC, KS and Brier score stored in the model card                                                                          |
| Anomaly detector     | Robust log amount profile per account plus velocity, novelty, unusual hour and structuring signals | Deterministic rules with reported signal contributions                                                                            |

Notes that matter when using the output:

- The credit scorecard ships trained on a synthetic bootstrap population so that the service works on day one. The model card and every score response state `training_data: synthetic_bootstrap`. Retrain on observed loan outcomes (`POST /api/v1/models/credit-scorecard/retrain`, internal callers only) before using scores for lending decisions. Retraining needs at least 200 labelled records with at least 20 defaults and 20 repayments, and creates a new versioned model.
- Factor contributions are exact for this model: the per feature points add up to the score minus the baseline score.
- Forecasts can be negative. Short histories (under 42 days) use statistical baselines and say so in `warnings`. Forecast intervals come from out of fold errors and widen with horizon.
- Insights are computed only from the data sent. With no data the service returns no insights.

## AI service API

All routes are under `/api/v1` and require either a bearer access token or the gateway headers `X-Internal-Key` plus `X-User-ID`. Requests are scoped to the authenticated user.

| Method            | Path                                                | Purpose                                                 |
| ----------------- | --------------------------------------------------- | ------------------------------------------------------- |
| GET               | `/health`                                           | liveness and model provenance                           |
| POST              | `/predictions/cash-flow`                            | forecast from `historical_data` or `source: "payments"` |
| POST              | `/predictions/credit-score`                         | score `business_data`                                   |
| GET               | `/predictions`, `/predictions/<id>`                 | stored predictions                                      |
| POST              | `/anomalies/score`, `/anomalies/batch`              | transaction risk with reasons                           |
| GET, POST, PUT    | `/insights`, `/insights/generate`, `/insights/<id>` | insights lifecycle                                      |
| POST              | `/insights/<id>/read`                               | mark an insight read                                    |
| POST, GET, DELETE | `/chat/sessions`, `/chat/sessions/<id>/messages`    | assistant sessions                                      |
| GET               | `/models`, `/models/credit-scorecard`               | model cards                                             |
| GET               | `/models/credit-scorecard/drift`                    | input drift from recent scoring traffic                 |
| POST              | `/models/credit-scorecard/retrain`                  | retrain on outcomes (internal only)                     |

## Integration

- API gateway: verifies the token, discards any client supplied `X-User-ID`, forwards the verified identity with `X-Internal-Key`, and routes `/api/v1/predictions`, `/anomalies`, `/insights`, `/chat`, `/models` to this service, plus `/credit` and `/analytics`.
- Credit service: `POST /api/v1/credit/scores` calls the scorecard and falls back to a documented rule set (flagged in `calculation_details.method`) when the AI service is unavailable.
- Payment service: `POST /api/v1/transactions` screens each transaction. `FRAUD_SCREENING_MODE` is `off`, `monitor` (default, risk stored in transaction metadata) or `enforce` (blocks on `block`, or also on `review` when `FRAUD_SCREENING_BLOCK_ON=review`). `FRAUD_SCREENING_FAIL_CLOSED=true` declines when screening is unavailable.
- Service trust: set `INTERNAL_SERVICE_KEY` on the gateway and every service. Services then reject requests that did not come through the gateway.

## Configuration

| Variable               | Default                  | Purpose                                                          |
| ---------------------- | ------------------------ | ---------------------------------------------------------------- |
| `SECRET_KEY`           | development default      | access token verification, must match the auth service           |
| `INTERNAL_SERVICE_KEY` | unset                    | enables service to service authentication                        |
| `ALLOW_USER_HEADER`    | false                    | development only, trusts `X-User-ID` when no internal key is set |
| `AI_DB_PATH`           | `src/database/app.db`    | SQLite database path                                             |
| `AI_MODEL_DIR`         | `src/database/models`    | credit model versions                                            |
| `PAYMENT_SERVICE_URL`  | `http://localhost:5003`  | payment history source                                           |
| `AI_SERVICE_URL`       | `http://ai-service:5004` | used by credit and payment services                              |

## Tests

```
cd code/ml_services && python -m pytest
```
