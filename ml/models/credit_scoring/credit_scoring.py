from typing import Any
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from core.logging import get_logger

logger = get_logger(__name__)


class CreditScorer:

    def __init__(self) -> None:
        self.model = None

    def preprocess_data(self, df: Any) -> Any:
        df = pd.get_dummies(
            df, columns=["education", "marital_status"], drop_first=True
        )
        df = df.fillna(df.mean(numeric_only=True))
        return df

    def train(self, X: Any, y: Any) -> Any:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        self.model = LogisticRegression(max_iter=1000)
        self.model.fit(X_train, y_train)
        y_pred = self.model.predict(X_test)
        logger.info("\nCredit Scoring Model Performance:")
        logger.info(f"Accuracy: {accuracy_score(y_test, y_pred):.2f}")
        logger.info("Classification Report:\n", classification_report(y_test, y_pred))

    def predict(self, X_new: Any) -> Any:
        if self.model is None:
            raise ValueError("Model has not been trained yet. Call train() first.")
        return self.model.predict_proba(X_new)[:, 1]


if __name__ == "__main__":
    data = {
        "age": [25, 30, 35, 40, 45, 50, 55, 60, 28, 33],
        "income": [
            50000,
            60000,
            70000,
            80000,
            90000,
            100000,
            110000,
            120000,
            55000,
            65000,
        ],
        "loan_amount": [
            10000,
            15000,
            20000,
            25000,
            30000,
            35000,
            40000,
            45000,
            12000,
            18000,
        ],
        "education": [
            "high_school",
            "university",
            "university",
            "graduate",
            "graduate",
            "university",
            "graduate",
            "university",
            "high_school",
            "university",
        ],
        "marital_status": [
            "single",
            "married",
            "single",
            "married",
            "single",
            "married",
            "single",
            "married",
            "single",
            "married",
        ],
        "credit_score_label": [0, 1, 1, 0, 1, 0, 1, 0, 0, 1],
    }
    df = pd.DataFrame(data)
    scorer = CreditScorer()
    processed_df = scorer.preprocess_data(df.copy())
    X = processed_df.drop("credit_score_label", axis=1)
    y = processed_df["credit_score_label"]
    scorer.train(X, y)
    new_applicant_data = {
        "age": [32],
        "income": [75000],
        "loan_amount": [22000],
        "education": ["university"],
        "marital_status": ["married"],
    }
    new_applicant_df = pd.DataFrame(new_applicant_data)
    processed_new_applicant_df = scorer.preprocess_data(new_applicant_df)
    train_cols = X.columns
    missing_cols = set(train_cols) - set(processed_new_applicant_df.columns)
    for c in missing_cols:
        processed_new_applicant_df[c] = 0
    processed_new_applicant_df = processed_new_applicant_df[train_cols]
    credit_probability = scorer.predict(processed_new_applicant_df)
    logger.info(
        f"\nProbability of good credit for new applicant: {credit_probability[0]:.2f}"
    )
