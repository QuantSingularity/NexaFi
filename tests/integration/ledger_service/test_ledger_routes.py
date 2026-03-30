from typing import Any
from datetime import date
from decimal import Decimal
from unittest.mock import patch
import pytest
from NexaFi.backend.ledger_service.src.main import app
from NexaFi.backend.ledger_service.src.models.user import (
    Account,
    Budget,
    FinancialPeriod,
    JournalEntry,
    JournalEntryLine,
    db,
)


@pytest.fixture(scope="module")
def client() -> Any:
    """
    Setup the test client and initialize the in-memory database.
    """
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        with app.app_context():
            db.session.remove()
            db.drop_all()


@pytest.fixture(autouse=True)
def run_around_tests(client: Any) -> Any:
    """
    Clean up tables between tests.
    """
    with app.app_context():
        Account.query.delete()
        JournalEntry.query.delete()
        JournalEntryLine.query.delete()
        FinancialPeriod.query.delete()
        Budget.query.delete()
        db.session.commit()
    yield


def create_test_account(
    user_id: Any, code: Any, name: Any, type: Any, normal_balance: Any
) -> Any:
    """Helper function to create and commit an Account instance."""
    account = Account(
        user_id=user_id,
        account_code=code,
        account_name=name,
        account_type=type,
        normal_balance=normal_balance,
    )
    db.session.add(account)
    db.session.commit()
    return account


class TestAccountRoutes:

    def test_get_accounts_empty(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_1"}
        response = client.get("/api/v1/accounts", headers=headers)
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["accounts"] == []
        assert json_data["total"] == 0

    def test_create_account_success(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_1"}
        data = {
            "account_code": "1010",
            "account_name": "Checking Account",
            "account_type": "asset",
            "normal_balance": "debit",
        }
        response = client.post("/api/v1/accounts", headers=headers, json=data)
        assert response.status_code == 201
        json_data = response.get_json()
        assert json_data["message"] == "Account created successfully"
        assert json_data["account"]["account_name"] == "Checking Account"
        with app.app_context():
            account = Account.query.filter_by(
                user_id="test_user_1", account_code="1010"
            ).first()
            assert account is not None

    def test_create_account_missing_field(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_1"}
        data = {
            "account_code": "1010",
            "account_name": "Checking Account",
            "account_type": "asset",
        }
        response = client.post("/api/v1/accounts", headers=headers, json=data)
        assert response.status_code == 400
        assert response.get_json()["error"] == "normal_balance is required"

    def test_create_account_duplicate_code(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_1"}
        create_test_account("test_user_1", "1010", "Existing Account", "asset", "debit")
        data = {
            "account_code": "1010",
            "account_name": "New Checking Account",
            "account_type": "asset",
            "normal_balance": "debit",
        }
        response = client.post("/api/v1/accounts", headers=headers, json=data)
        assert response.status_code == 409
        assert response.get_json()["error"] == "Account code already exists"

    def test_get_account_success(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_2"}
        account = create_test_account(
            "test_user_2", "2000", "Savings Account", "asset", "debit"
        )
        response = client.get(f"/api/v1/accounts/{account.id}", headers=headers)
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["account"]["account_name"] == "Savings Account"
        assert "balance" in json_data["account"]

    def test_get_account_not_found(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_2"}
        response = client.get("/api/v1/accounts/99999", headers=headers)
        assert response.status_code == 404
        assert response.get_json()["error"] == "Account not found"

    def test_update_account_success(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_3"}
        account = create_test_account(
            "test_user_3", "3000", "Old Name", "asset", "debit"
        )
        data = {"account_name": "New Name", "is_active": False}
        response = client.put(
            f"/api/v1/accounts/{account.id}", headers=headers, json=data
        )
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["message"] == "Account updated successfully"
        assert json_data["account"]["account_name"] == "New Name"
        assert json_data["account"]["is_active"] == False
        with app.app_context():
            updated_account = Account.query.get(account.id)
            assert updated_account.account_name == "New Name"
            assert updated_account.is_active == False

    def test_update_account_not_found(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_3"}
        data = {"account_name": "New Name"}
        response = client.put("/api/v1/accounts/99999", headers=headers, json=data)
        assert response.status_code == 404
        assert response.get_json()["error"] == "Account not found"


class TestJournalEntryRoutes:

    def test_get_journal_entries_empty(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_4"}
        response = client.get("/api/v1/journal-entries", headers=headers)
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["journal_entries"] == []
        assert json_data["pagination"]["total"] == 0

    def test_create_journal_entry_success(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_5"}
        cash_account = create_test_account(
            "test_user_5", "1000", "Cash", "asset", "debit"
        )
        revenue_account = create_test_account(
            "test_user_5", "4000", "Revenue", "revenue", "credit"
        )
        data = {
            "description": "Sale of goods",
            "lines": [
                {"account_id": cash_account.id, "debit_amount": 100.0},
                {"account_id": revenue_account.id, "credit_amount": 100.0},
            ],
        }
        response = client.post("/api/v1/journal-entries", headers=headers, json=data)
        assert response.status_code == 201
        json_data = response.get_json()
        assert json_data["message"] == "Journal entry created successfully"
        assert json_data["journal_entry"]["total_amount"] == 100.0
        assert len(json_data["journal_entry"]["lines"]) == 2
        with app.app_context():
            entry = JournalEntry.query.filter_by(user_id="test_user_5").first()
            assert entry is not None
            assert entry.status == "draft"

    def test_create_journal_entry_unbalanced(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_6"}
        cash_account = create_test_account(
            "test_user_6", "1000", "Cash", "asset", "debit"
        )
        revenue_account = create_test_account(
            "test_user_6", "4000", "Revenue", "revenue", "credit"
        )
        data = {
            "description": "Unbalanced entry",
            "lines": [
                {"account_id": cash_account.id, "debit_amount": 100.0},
                {"account_id": revenue_account.id, "credit_amount": 50.0},
            ],
        }
        response = client.post("/api/v1/journal-entries", headers=headers, json=data)
        assert response.status_code == 400
        assert response.get_json()["error"] == "Total debits must equal total credits"

    def test_post_journal_entry_success(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_7"}
        cash_account = create_test_account(
            "test_user_7", "1000", "Cash", "asset", "debit"
        )
        revenue_account = create_test_account(
            "test_user_7", "4000", "Revenue", "revenue", "credit"
        )
        entry = JournalEntry(
            user_id="test_user_7",
            entry_number="JE20240101-0001",
            description="Test Entry",
            entry_date=date.today(),
            total_amount=Decimal("100.00"),
            status="draft",
        )
        db.session.add(entry)
        db.session.flush()
        line1 = JournalEntryLine(
            journal_entry_id=entry.id,
            account_id=cash_account.id,
            debit_amount=Decimal("100.00"),
        )
        line2 = JournalEntryLine(
            journal_entry_id=entry.id,
            account_id=revenue_account.id,
            credit_amount=Decimal("100.00"),
        )
        db.session.add_all([line1, line2])
        db.session.commit()
        response = client.post(
            f"/api/v1/journal-entries/{entry.id}/post", headers=headers
        )
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["message"] == "Journal entry posted successfully"
        assert json_data["journal_entry"]["status"] == "posted"
        with app.app_context():
            posted_entry = JournalEntry.query.get(entry.id)
            assert posted_entry.status == "posted"
            assert posted_entry.posted_by == "test_user_7"
            assert posted_entry.posted_at is not None

    def test_post_journal_entry_not_found(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_7"}
        response = client.post("/api/v1/journal-entries/99999/post", headers=headers)
        assert response.status_code == 404
        assert response.get_json()["error"] == "Journal entry not found"

    def test_post_journal_entry_already_posted(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_8"}
        entry = JournalEntry(
            user_id="test_user_8",
            entry_number="JE20240101-0002",
            description="Already Posted Entry",
            entry_date=date.today(),
            total_amount=Decimal("100.00"),
            status="posted",
        )
        db.session.add(entry)
        db.session.commit()
        response = client.post(
            f"/api/v1/journal-entries/{entry.id}/post", headers=headers
        )
        assert response.status_code == 400
        assert response.get_json()["error"] == "Only draft entries can be posted"


class TestFinancialReportsRoutes:

    def test_get_trial_balance_success(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_9"}
        cash_account = create_test_account(
            "test_user_9", "1000", "Cash", "asset", "debit"
        )
        revenue_account = create_test_account(
            "test_user_9", "4000", "Revenue", "revenue", "credit"
        )
        entry = JournalEntry(
            user_id="test_user_9",
            entry_number="JE20240101-0003",
            description="Test Entry for TB",
            entry_date=date.today(),
            total_amount=Decimal("100.00"),
            status="posted",
        )
        db.session.add(entry)
        db.session.flush()
        line1 = JournalEntryLine(
            journal_entry_id=entry.id,
            account_id=cash_account.id,
            debit_amount=Decimal("100.00"),
        )
        line2 = JournalEntryLine(
            journal_entry_id=entry.id,
            account_id=revenue_account.id,
            credit_amount=Decimal("100.00"),
        )
        db.session.add_all([line1, line2])
        db.session.commit()
        response = client.get(
            "/api/v1/reports/trial-balance",
            headers=headers,
            query_string={"as_of_date": date.today().isoformat()},
        )
        assert response.status_code == 200
        json_data = response.get_json()
        assert "trial_balance" in json_data
        assert len(json_data["trial_balance"]) == 2
        assert json_data["total_debits"] == 100.0
        assert json_data["total_credits"] == 100.0

    def test_get_income_statement_success(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_10"}
        revenue_account = create_test_account(
            "test_user_10", "4000", "Sales Revenue", "revenue", "credit"
        )
        expense_account = create_test_account(
            "test_user_10", "6000", "Salaries Expense", "expense", "debit"
        )
        cash_account = create_test_account(
            "test_user_10", "1000", "Cash", "asset", "debit"
        )
        entry1 = JournalEntry(
            user_id="test_user_10",
            entry_number="JE20240101-0004",
            description="Revenue Entry",
            entry_date=date.today(),
            total_amount=Decimal("500.00"),
            status="posted",
        )
        db.session.add(entry1)
        db.session.flush()
        line1_1 = JournalEntryLine(
            journal_entry_id=entry1.id,
            account_id=cash_account.id,
            debit_amount=Decimal("500.00"),
        )
        line1_2 = JournalEntryLine(
            journal_entry_id=entry1.id,
            account_id=revenue_account.id,
            credit_amount=Decimal("500.00"),
        )
        db.session.add_all([line1_1, line1_2])
        db.session.commit()
        entry2 = JournalEntry(
            user_id="test_user_10",
            entry_number="JE20240101-0005",
            description="Expense Entry",
            entry_date=date.today(),
            total_amount=Decimal("200.00"),
            status="posted",
        )
        db.session.add(entry2)
        db.session.flush()
        line2_1 = JournalEntryLine(
            journal_entry_id=entry2.id,
            account_id=expense_account.id,
            debit_amount=Decimal("200.00"),
        )
        line2_2 = JournalEntryLine(
            journal_entry_id=entry2.id,
            account_id=cash_account.id,
            credit_amount=Decimal("200.00"),
        )
        db.session.add_all([line2_1, line2_2])
        db.session.commit()
        response = client.get(
            "/api/v1/reports/income-statement",
            headers=headers,
            query_string={
                "start_date": date.today().isoformat(),
                "end_date": date.today().isoformat(),
            },
        )
        assert response.status_code == 200
        json_data = response.get_json()
        assert "income_statement" in json_data
        assert json_data["income_statement"]["total_revenue"] == 500.0
        assert json_data["income_statement"]["total_expenses"] == 200.0
        assert json_data["income_statement"]["net_income"] == 300.0

    def test_get_balance_sheet_success(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_11"}
        cash_account = create_test_account(
            "test_user_11", "1000", "Cash", "asset", "debit"
        )
        ap_account = create_test_account(
            "test_user_11", "2000", "Accounts Payable", "liability", "credit"
        )
        equity_account = create_test_account(
            "test_user_11", "3000", "Owner's Equity", "equity", "credit"
        )
        entry1 = JournalEntry(
            user_id="test_user_11",
            entry_number="JE20240101-0006",
            description="Initial Investment",
            entry_date=date.today(),
            total_amount=Decimal("1000.00"),
            status="posted",
        )
        db.session.add(entry1)
        db.session.flush()
        line1_1 = JournalEntryLine(
            journal_entry_id=entry1.id,
            account_id=cash_account.id,
            debit_amount=Decimal("1000.00"),
        )
        line1_2 = JournalEntryLine(
            journal_entry_id=entry1.id,
            account_id=equity_account.id,
            credit_amount=Decimal("1000.00"),
        )
        db.session.add_all([line1_1, line1_2])
        db.session.commit()
        response = client.get(
            "/api/v1/reports/balance-sheet",
            headers=headers,
            query_string={"as_of_date": date.today().isoformat()},
        )
        assert response.status_code == 200
        json_data = response.get_json()
        assert "balance_sheet" in json_data
        assert json_data["balance_sheet"]["total_assets"] == 1000.0
        assert json_data["balance_sheet"]["total_liabilities"] == 0.0
        assert json_data["balance_sheet"]["total_equity"] == 1000.0
        assert json_data["balance_sheet"]["total_liabilities_equity"] == 1000.0


class TestFinancialPeriodRoutes:

    def test_get_financial_periods_empty(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_12"}
        response = client.get("/api/v1/financial-periods", headers=headers)
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["financial_periods"] == []
        assert json_data["total"] == 0

    def test_create_financial_period_success(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_12"}
        data = {
            "period_name": "Q1 2024",
            "start_date": "2024-01-01",
            "end_date": "2024-03-31",
            "period_type": "quarterly",
        }
        response = client.post("/api/v1/financial-periods", headers=headers, json=data)
        assert response.status_code == 201
        json_data = response.get_json()
        assert json_data["message"] == "Financial period created successfully"
        assert json_data["financial_period"]["period_name"] == "Q1 2024"
        with app.app_context():
            period = FinancialPeriod.query.filter_by(
                user_id="test_user_12", period_name="Q1 2024"
            ).first()
            assert period is not None

    def test_close_financial_period_success(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_13"}
        period = FinancialPeriod(
            user_id="test_user_13",
            period_name="Q4 2023",
            start_date=date(2023, 10, 1),
            end_date=date(2023, 12, 31),
            period_type="quarterly",
            status="open",
        )
        db.session.add(period)
        db.session.commit()
        response = client.post(
            f"/api/v1/financial-periods/{period.id}/close", headers=headers
        )
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["message"] == "Financial period closed successfully"
        assert json_data["financial_period"]["status"] == "closed"
        with app.app_context():
            closed_period = FinancialPeriod.query.get(period.id)
            assert closed_period.status == "closed"
            assert closed_period.closed_at is not None


class TestBudgetRoutes:

    def test_get_budgets_empty(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_14"}
        response = client.get("/api/v1/budgets", headers=headers)
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["budgets"] == []
        assert json_data["total"] == 0

    def test_create_budget_success(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_14"}
        data = {
            "budget_name": "Marketing Budget 2024",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "budget_amount": 10000.0,
            "currency": "USD",
        }
        response = client.post("/api/v1/budgets", headers=headers, json=data)
        assert response.status_code == 201
        json_data = response.get_json()
        assert json_data["message"] == "Budget created successfully"
        assert json_data["budget"]["budget_name"] == "Marketing Budget 2024"
        with app.app_context():
            budget = Budget.query.filter_by(
                user_id="test_user_14", budget_name="Marketing Budget 2024"
            ).first()
            assert budget is not None

    def test_get_budget_performance_success(self, client: Any) -> Any:
        headers = {"X-User-ID": "test_user_15"}
        expense_account = create_test_account(
            "test_user_15", "6000", "Travel Expense", "expense", "debit"
        )
        period = FinancialPeriod(
            user_id="test_user_15",
            period_name="FY2024",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            period_type="yearly",
            fiscal_year=2024,
        )
        db.session.add(period)
        db.session.commit()
        budget = Budget(
            user_id="test_user_15",
            account_id=expense_account.id,
            period_id=period.id,
            budgeted_amount=Decimal("5000.00"),
            budget_name="Travel Budget",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            currency="USD",
        )
        db.session.add(budget)
        db.session.commit()
        with patch(
            "NexaFi.backend.ledger_service.src.models.user.Account.get_balance"
        ) as mock_get_balance:
            mock_get_balance.return_value = Decimal("1500.00")
            response = client.get(
                f"/api/v1/budgets/{budget.id}/performance", headers=headers
            )
            assert response.status_code == 200
            json_data = response.get_json()
            assert "budget_performance" in json_data
            assert json_data["budget_performance"]["budget_amount"] == 5000.0
            assert json_data["budget_performance"]["actual_spend"] == 1500.0
            assert json_data["budget_performance"]["variance"] == 3500.0
            assert json_data["budget_performance"]["status"] == "under_budget"
