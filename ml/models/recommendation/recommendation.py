import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from core.logging import get_logger

logger = get_logger(__name__)


class ProductRecommender:

    def __init__(self) -> None:
        self.products_df = None
        self.tfidf_matrix = None
        self.tfidf_vectorizer = None

    def load_products(self, products_data: Any) -> Any:
        self.products_df = pd.DataFrame(products_data)
        self.products_df = self.products_df.set_index("product_id")

    def train(self) -> Any:
        if self.products_df is None:
            raise ValueError("Products data not loaded. Call load_products() first.")
        self.tfidf_vectorizer = TfidfVectorizer(stop_words="english")
        self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(
            self.products_df["description"]
        )

    def recommend_products(
        self, user_preferences: Any, num_recommendations: Any = 3
    ) -> Any:
        if self.tfidf_matrix is None:
            raise ValueError("Model has not been trained yet. Call train() first.")
        user_tfidf = self.tfidf_vectorizer.transform([user_preferences])
        cosine_similarities = cosine_similarity(user_tfidf, self.tfidf_matrix).flatten()
        product_indices = cosine_similarities.argsort()[: -num_recommendations - 1 : -1]
        recommended_products = self.products_df.iloc[product_indices]
        return recommended_products


if __name__ == "__main__":
    recommender = ProductRecommender()
    products_data = [
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
        {
            "product_id": "P005",
            "description": "Mortgage loan with competitive interest rates.",
        },
        {"product_id": "P006", "description": "Personal loan for debt consolidation."},
        {
            "product_id": "P007",
            "description": "Retirement planning service with financial advisors.",
        },
    ]
    recommender.load_products(products_data)
    recommender.train()
    user_pref = "I want to save money and invest in environmentally friendly options."
    recommendations = recommender.recommend_products(user_pref, num_recommendations=2)
    logger.info("\nRecommended Products for user preferences:\n", user_pref)
    logger.info(recommendations)
    user_pref_2 = "Looking for a credit card with good rewards for travel."
    recommendations_2 = recommender.recommend_products(
        user_pref_2, num_recommendations=1
    )
    logger.info("\nRecommended Products for user preferences:\n", user_pref_2)
    logger.info(recommendations_2)
