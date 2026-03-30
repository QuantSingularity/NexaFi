from typing import Any
import unittest
import pandas as pd
from NexaFi.ml.models.cash_flow_forecasting.cash_flow_forecasting import (
    CashFlowForecaster,
)


class TestCashFlowForecaster(unittest.TestCase):

    def setUp(self) -> Any:
        self.forecaster = CashFlowForecaster()
        self.data = {
            "date": pd.to_datetime(
                ["2023-01-15", "2023-02-10", "2023-03-05", "2023-04-20", "2023-05-12"]
            ),
            "amount": [1000, -500, 1200, -700, 1500],
        }
        self.df = pd.DataFrame(self.data)

    def test_preprocess_data(self) -> Any:
        processed_df = self.forecaster.preprocess_data(self.df.copy())
        self.assertIsInstance(processed_df, pd.Series)
        self.assertEqual(processed_df.index.freq, "M")
        self.assertFalse(processed_df.isnull().any())

    def test_train_and_predict(self) -> Any:
        processed_data = self.forecaster.preprocess_data(self.df.copy())
        self.forecaster.train(processed_data)
        predictions = self.forecaster.predict(3)
        self.assertEqual(len(predictions), 3)
        self.assertIsInstance(predictions, pd.Series)

    def test_predict_before_train(self) -> Any:
        with self.assertRaises(ValueError):
            self.forecaster.predict(1)


if __name__ == "__main__":
    unittest.main()
