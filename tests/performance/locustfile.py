import random
from typing import Any

from locust import HttpUser, between, task


class WebsiteUser(HttpUser):
    wait_time = between(1, 2)
    host = "http://localhost:5000"

    def on_start(self) -> Any:
        self.client.post(
            "/auth/login", json={"email": "test@example.com", "password": "password123"}
        )

    @task
    def index_page(self) -> Any:
        self.client.get("/", name="01_Homepage")

    @task(3)
    def login(self) -> Any:
        self.client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "password123"},
            name="02_Login",
        )

    @task
    def get_user_profile(self) -> Any:
        self.client.get("/users/profile", name="03_UserProfile")

    @task
    def update_user_profile(self) -> Any:
        self.client.put(
            "/users/profile",
            json={
                "first_name": f"TestUser{random.randint(1, 1000)}",
                "last_name": "Locust",
                "email": "test@example.com",
            },
            name="04_UpdateUserProfile",
        )

    @task
    def get_accounts(self) -> Any:
        self.client.get("/accounts", name="05_GetAccounts")

    @task
    def create_account(self) -> Any:
        self.client.post(
            "/accounts",
            json={
                "account_name": f"Locust Account {random.randint(1, 10000)}",
                "account_code": str(random.randint(1000, 9999)),
                "account_type": random.choice(
                    ["asset", "liability", "equity", "revenue", "expense"]
                ),
                "description": "Account created by Locust",
            },
            name="06_CreateAccount",
        )

    @task
    def get_journal_entries(self) -> Any:
        self.client.get("/journal-entries", name="07_GetJournalEntries")

    @task
    def create_journal_entry(self) -> Any:
        self.client.post(
            "/journal-entries",
            json={
                "entry_date": "2024-06-15",
                "description": f"Locust Test Entry {random.randint(1, 10000)}",
                "line_items": [
                    {"account_id": "1", "debit": random.uniform(10, 1000), "credit": 0},
                    {"account_id": "2", "debit": 0, "credit": random.uniform(10, 1000)},
                ],
            },
            name="08_CreateJournalEntry",
        )

    @task
    def get_financial_summary(self) -> Any:
        self.client.get("/dashboard/financial-summary", name="09_FinancialSummary")

    @task
    def get_transactions(self) -> Any:
        self.client.get("/transactions", name="10_GetTransactions")

    @task
    def create_transaction(self) -> Any:
        self.client.post(
            "/transactions",
            json={
                "amount": random.uniform(10, 500),
                "type": random.choice(["income", "expense"]),
                "description": f"Locust Transaction {random.randint(1, 10000)}",
                "payment_method_id": "some_method_id",
            },
            name="11_CreateTransaction",
        )

    @task
    def predict_cash_flow(self) -> Any:
        self.client.post(
            "/predictions/cash-flow",
            json={"data": [random.uniform(100, 1000) for _ in range(12)]},
            name="12_PredictCashFlow",
        )

    @task
    def get_insights(self) -> Any:
        self.client.get("/insights", name="13_GetInsights")

    @task
    def health_check(self) -> Any:
        self.client.get("/health", name="14_HealthCheck")
