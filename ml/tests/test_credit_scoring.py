from typing import Any
import unittest
import pandas as pd
from NexaFi.ml.models.credit_scoring.credit_scoring import CreditScorer


class TestCreditScorer(unittest.TestCase):

    def setUp(self) -> Any:
        self.scorer = CreditScorer()
        self.data = {
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
        self.df = pd.DataFrame(self.data)
        self.processed_df = self.scorer.preprocess_data(self.df.copy())
        self.X = self.processed_df.drop("credit_score_label", axis=1)
        self.y = self.processed_df["credit_score_label"]

    def test_preprocess_data(self) -> Any:
        processed_df = self.scorer.preprocess_data(self.df.copy())
        self.assertIn("education_university", processed_df.columns)
        self.assertIn("marital_status_single", processed_df.columns)
        self.assertFalse(processed_df.isnull().any().any())

    def test_train_and_predict(self) -> Any:
        self.scorer.train(self.X, self.y)
        new_applicant_data = {
            "age": [32],
            "income": [75000],
            "loan_amount": [22000],
            "education": ["university"],
            "marital_status": ["married"],
        }
        new_applicant_df = pd.DataFrame(new_applicant_data)
        processed_new_applicant_df = self.scorer.preprocess_data(new_applicant_df)
        train_cols = self.X.columns
        missing_cols = set(train_cols) - set(processed_new_applicant_df.columns)
        for c in missing_cols:
            processed_new_applicant_df[c] = 0
        processed_new_applicant_df = processed_new_applicant_df[train_cols]
        predictions = self.scorer.predict(processed_new_applicant_df)
        self.assertEqual(len(predictions), 1)
        self.assertIsInstance(predictions[0], float)

    def test_predict_before_train(self) -> Any:
        with self.assertRaises(ValueError):
            self.scorer.predict(self.X.iloc[:1])


if __name__ == "__main__":
    unittest.main()
