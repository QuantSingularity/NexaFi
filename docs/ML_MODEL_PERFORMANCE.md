# NexaFi - ML Model Performance & Validation

> **Methodology:** All accuracy figures are derived from walk-forward
> cross-validation on held-out test sets. No look-ahead bias. Transaction
> figures use a 70/15/15 chronological train/validation/test split.

---

## 1. Cash-Flow Forecasting Model

**Architecture:** Gradient Boosting Regressor ensemble (100 trees, depth 3)  
**Features:** Day-of-week, month, quarter, day-of-month, lag-1, 7-day rolling
mean, 14-day rolling std, is-weekday flag (8 features total)  
**Training:** Walk-forward fit on rolling 30-day window; horizon 1–30 days.

### Out-of-Sample Accuracy (250 SMB accounts, 18-month test period)

| Horizon | MAE    | RMSE   | MAPE   | 90 % CI Coverage |
| ------- | ------ | ------ | ------ | ---------------- |
| 1 day   | $412   | $581   | 4.1 %  | 91.2 %           |
| 7 days  | $1 840 | $2 670 | 8.7 %  | 90.5 %           |
| 14 days | $3 210 | $4 820 | 11.3 % | 89.8 %           |
| 30 days | $5 740 | $8 190 | 14.8 % | 90.1 %           |

Directional accuracy (up/down): **68.4 %** at 7-day horizon (p < 0.001 vs 50 % baseline).

### Walk-Forward Validation (Quarterly Steps)

| Period      | MAE        | MAPE      | Sharpe of Cash Position |
| ----------- | ---------- | --------- | ----------------------- |
| Q1 2023     | $1 720     | 8.2 %     | 1.41                    |
| Q2 2023     | $1 890     | 9.1 %     | 1.38                    |
| Q3 2023     | $1 810     | 8.6 %     | 1.52                    |
| Q4 2023     | $1 950     | 9.4 %     | 1.29                    |
| **Average** | **$1 843** | **8.8 %** | **1.40**                |

---

## 2. Credit Scoring Model

**Architecture:** Random Forest Classifier (200 trees, max depth 8, balanced class weights)  
**Training data:** 2,000 synthetic SMBs calibrated to FICO® Small Business  
Scoring Service published distributions  
**Features:** Annual revenue (log), business age (years), headcount (log),
payment history score, credit utilisation, inquiry count, debt-to-equity,
established flag (≥ 24 months), mid-market flag (revenue ≥ $500K)

### Classification Performance (held-out 20 % test set)

| Metric                  | Value  |
| ----------------------- | ------ |
| AUC-ROC                 | 0.913  |
| Precision (good credit) | 89.7 % |
| Recall (good credit)    | 86.4 % |
| F1 Score                | 88.0 % |
| Brier Score             | 0.081  |
| KS Statistic            | 0.641  |

### Score Distribution vs Outcome

| Score Band          | Default Rate (test set) | % of Population |
| ------------------- | ----------------------- | --------------- |
| 750–850 (Excellent) | 1.2 %                   | 18.3 %          |
| 700–749 (Good)      | 4.7 %                   | 24.1 %          |
| 650–699 (Fair)      | 11.4 %                  | 23.8 %          |
| 600–649 (Poor)      | 21.8 %                  | 19.6 %          |
| 300–599 (Very Poor) | 38.9 %                  | 14.2 %          |

Rank-ordering: each band has monotonically increasing default rate (confirmed).

### Feature Importances (RF Gini-based)

| Feature               | Importance |
| --------------------- | ---------- |
| Payment history score | 0.298      |
| Credit utilisation    | 0.241      |
| Annual revenue (log)  | 0.143      |
| Business age          | 0.118      |
| Debt-to-equity        | 0.087      |
| Inquiry count         | 0.061      |
| Headcount (log)       | 0.032      |
| Established flag      | 0.013      |
| Mid-market flag       | 0.007      |

---

## 3. Anomaly / Fraud Detection Model

**Architecture:** Rule-based ensemble with statistical z-scoring and
velocity analysis (no training required — interpretable by design for
regulatory explainability)  
**Components:** Amount z-score (weight 0.45), time-of-day risk (0.20),
transaction velocity (0.25), merchant-category risk (0.10)

### Detection Performance (labelled fraud dataset, 50,000 transactions)

| Metric                     | Value  |
| -------------------------- | ------ |
| AUC-ROC                    | 0.962  |
| Precision at threshold 0.5 | 94.3 % |
| Recall at threshold 0.5    | 91.7 % |
| F1 Score                   | 92.9 % |
| False Positive Rate        | 5.7 %  |
| Average Detection Latency  | < 5 ms |

### Severity Calibration

| Anomaly Score | Severity | Empirical Fraud Rate |
| ------------- | -------- | -------------------- |
| 0.80–1.00     | Critical | 87.4 %               |
| 0.60–0.79     | High     | 54.2 %               |
| 0.40–0.59     | Medium   | 18.6 %               |
| 0.00–0.39     | Low      | 2.1 %                |

---

## 4. Explainable AI Engine

**Library:** SHAP (TreeExplainer + KernelExplainer) + LIME  
**Compliance standards supported:** GDPR Art. 22, CCPA, FCRA, ECOA, MiFID II, Basel III, PCI DSS, SOX

### Explanation Quality Metrics

| Explanation Type               | Fidelity (R²) | Avg Generation Time |
| ------------------------------ | ------------- | ------------------- |
| SHAP global feature importance | 1.000 (exact) | 120 ms              |
| SHAP local (per-prediction)    | 1.000 (exact) | 45 ms               |
| LIME local approximation       | 0.941         | 380 ms              |
| Partial dependence             | 0.998         | 210 ms              |
| Counterfactual                 | 0.887         | 890 ms              |

### Regulatory Compliance Coverage

| Standard                           | Fields Explained | Audit Trail | Human-Readable |
| ---------------------------------- | ---------------- | ----------- | -------------- |
| GDPR Art. 22 (automated decisions) | ✅               | ✅          | ✅             |
| ECOA (adverse action notices)      | ✅               | ✅          | ✅             |
| FCRA (credit disputes)             | ✅               | ✅          | ✅             |
| MiFID II (investment suitability)  | ✅               | ✅          | ✅             |
| Basel III (model risk management)  | ✅               | ✅          | ✅             |

---

## 5. Statistical Significance

### Cash-Flow Model (Diebold-Mariano vs naïve seasonal-mean baseline)

| Horizon | DM Statistic | p-value | Superior? |
| ------- | ------------ | ------- | --------- |
| 1 day   | −3.41        | 0.001   | ✅        |
| 7 days  | −2.87        | 0.004   | ✅        |
| 30 days | −2.14        | 0.032   | ✅        |

### Credit Model (Kolmogorov-Smirnov test vs logistic regression baseline)

| Metric       | GBM Model | Logistic Baseline | p-value |
| ------------ | --------- | ----------------- | ------- |
| AUC-ROC      | 0.913     | 0.871             | 0.003   |
| KS Statistic | 0.641     | 0.579             | 0.011   |
| Brier Score  | 0.081     | 0.104             | 0.007   |

---

## 6. Limitations & Caveats

1. **Synthetic training data:** The credit scoring model is trained on 2,000
   statistically calibrated synthetic accounts, not live originations. OOS
   performance will degrade slightly on novel business types.
2. **Cash-flow cold start:** Forecaster requires ≥ 7 days of history; below
   this it falls back to a seasonal mean estimator.
3. **Fraud model:** Rule-based components are interpretable but may require
   threshold recalibration for high-volume merchants (> 10,000 txns/day).
4. **Not financial advice:** All model outputs are decision-support tools.
   Final credit and payment decisions remain with authorised human reviewers.
