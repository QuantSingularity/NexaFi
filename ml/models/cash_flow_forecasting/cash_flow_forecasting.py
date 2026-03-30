import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from core.logging import get_logger

logger = get_logger(__name__)


class CashFlowForecaster:

    def __init__(self) -> None:
        self.model = None
        self.model_fit = None

    def preprocess_data(self, df: Any) -> Any:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        df = df["amount"].resample("M").sum().fillna(0)
        return df

    def train(self, data: Any) -> Any:
        order = (1, 1, 1)
        self.model = ARIMA(data, order=order)
        self.model_fit = self.model.fit()

    def predict(self, steps: Any) -> Any:
        if self.model_fit is None:
            raise ValueError("Model has not been trained yet. Call train() first.")
        forecast = self.model_fit.forecast(steps=steps)
        return forecast


if __name__ == "__main__":
    data = {
        "date": pd.to_datetime(
            ["2023-01-15", "2023-02-10", "2023-03-05", "2023-04-20", "2023-05-12"]
        ),
        "amount": [1000, -500, 1200, -700, 1500],
    }
    df = pd.DataFrame(data)
    forecaster = CashFlowForecaster()
    processed_data = forecaster.preprocess_data(df)
    forecaster.train(processed_data)
    predictions = forecaster.predict(3)
    logger.info("Processed Data:\n", processed_data)
    logger.info("\nForecasted Cash Flow for next 3 months:\n", predictions)
