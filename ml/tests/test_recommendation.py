from typing import Any
import unittest
import pandas as pd
from NexaFi.ml.models.recommendation.recommendation import ProductRecommender


class TestProductRecommender(unittest.TestCase):

    def setUp(self) -> Any:
        self.recommender = ProductRecommender()
        self.products_data = [
            {
                "product_id": "P001",
                "description": "High-interest savings account for long-term goals.",
            },
            {
                "product_id": "P002",
                "description": "Low-fee checking account with free ATM withdrawals.",
            },
            {
                "product_id": "P003",
                "description": "Investment fund focused on sustainable energy.",
            },
            {
                "product_id": "P004",
                "description": "Credit card with travel rewards and no annual fee.",
            },
        ]
        self.recommender.load_products(self.products_data)

    def test_load_products(self) -> Any:
        self.assertIsInstance(self.recommender.products_df, pd.DataFrame)
        self.assertEqual(len(self.recommender.products_df), len(self.products_data))
        self.assertIn("description", self.recommender.products_df.columns)

    def test_train(self) -> Any:
        self.recommender.train()
        self.assertIsNotNone(self.recommender.tfidf_matrix)
        self.assertIsNotNone(self.recommender.tfidf_vectorizer)

    def test_recommend_products(self) -> Any:
        self.recommender.train()
        user_pref = "savings account"
        recommendations = self.recommender.recommend_products(
            user_pref, num_recommendations=1
        )
        self.assertEqual(len(recommendations), 1)
        self.assertEqual(recommendations.index[0], "P001")
        user_pref_2 = "Looking for a credit card."
        recommendations_2 = self.recommender.recommend_products(
            user_pref_2, num_recommendations=1
        )
        self.assertEqual(len(recommendations_2), 1)
        self.assertTrue(
            any(
                (
                    keyword in recommendations_2["description"].iloc[0].lower()
                    for keyword in ["credit", "card", "travel", "rewards"]
                )
            )
        )

    def test_recommend_before_train(self) -> Any:
        self.recommender = ProductRecommender()
        self.recommender.load_products(self.products_data)
        with self.assertRaises(ValueError):
            self.recommender.recommend_products("some preference")


if __name__ == "__main__":
    unittest.main()
