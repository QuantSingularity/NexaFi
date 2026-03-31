import logging
from typing import Any

import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import classification_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class FraudDetector:

    def __init__(self) -> None:
        self.model = None

    def preprocess_data(self, df: Any) -> Any:
        df = df.fillna(df.mean(numeric_only=True))
        return df

    def train(self, X: Any) -> Any:
        self.model = IsolationForest(random_state=42)
        self.model.fit(X)

    def predict(self, X_new: Any) -> Any:
        if self.model is None:
            raise ValueError("Model has not been trained yet. Call train() first.")
        return self.model.predict(X_new)

    def evaluate(self, X: Any, y_true: Any) -> Any:
        if self.model is None:
            raise ValueError("Model has not been trained yet. Call train() first.")
        y_pred = self.model.predict(X)
        y_pred_binary = [1 if p == -1 else 0 for p in y_pred]
        y_true_binary = [1 if t == 1 else 0 for t in y_true]
        logger.info("\nFraud Detection Model Performance:")
        logger.info(
            classification_report(
                y_true_binary, y_pred_binary, target_names=["Legitimate", "Fraud"]
            )
        )


if __name__ == "__main__":
    data = {
        "transaction_amount": [100, 200, 50, 1000, 150, 300, 5000, 75, 250, 80],
        "transaction_frequency_24h": [5, 3, 8, 1, 6, 4, 0, 7, 2, 9],
        "location_change": [0, 0, 0, 1, 0, 0, 1, 0, 0, 0],
        "is_fraud": [0, 0, 0, 1, 0, 0, 1, 0, 0, 0],
    }
    df = pd.DataFrame(data)
    detector = FraudDetector()
    processed_df = detector.preprocess_data(df.copy())
    X = processed_df.drop("is_fraud", axis=1)
    y = processed_df["is_fraud"]
    detector.train(X)
    predictions = detector.predict(X)
    logger.info("\nPredictions (-1 for fraud, 1 for legitimate):", predictions)
    detector.evaluate(X, y)
    new_transaction = pd.DataFrame(
        {
            "transaction_amount": [6000],
            "transaction_frequency_24h": [0],
            "location_change": [1],
        }
    )
    processed_new_transaction = detector.preprocess_data(new_transaction)
    fraud_prediction = detector.predict(processed_new_transaction)
    logger.info(
        f"\nPrediction for new transaction: {fraud_prediction[0]} (-1 means fraud)"
    )
