from typing import Any
from datetime import date
from decimal import Decimal
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


class TestAccountModel:

    def test_account_creation(self) -> Any:
        account = Account(
            user_id="user123",
            account_code="1000",
            account_name="Cash",
            account_type="asset",
            normal_balance="debit",
        )
        db.session.add(account)
        db.session.commit()
        retrieved_account = Account.query.filter_by(user_id="user123").first()
        assert retrieved_account is not None
        assert retrieved_account.account_name == "Cash"

    def test_account_balance_calculation(self) -> Any:
        user_id = "user456"
        cash_account = create_test_account(user_id, "1000", "Cash", "asset", "debit")
        revenue_account = create_test_account(
            user_id, "4000", "Revenue", "revenue", "credit"
        )
        entry = JournalEntry(
            user_id=user_id,
            entry_number="JE001",
            description="Sale",
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
        assert cash_account.get_balance() == Decimal("100.00")
        assert revenue_account.get_balance() == Decimal("100.00")


class TestJournalEntryModel:

    def test_journal_entry_creation(self) -> Any:
        user_id = "user789"
        cash_account = create_test_account(user_id, "1000", "Cash", "asset", "debit")
        revenue_account = create_test_account(
            user_id, "4000", "Revenue", "revenue", "credit"
        )
        entry = JournalEntry(
            user_id=user_id,
            entry_number="JE002",
            description="Service Income",
            entry_date=date.today(),
            total_amount=Decimal("200.00"),
            status="draft",
        )
        db.session.add(entry)
        db.session.flush()
        line1 = JournalEntryLine(
            journal_entry_id=entry.id,
            account_id=cash_account.id,
            debit_amount=Decimal("200.00"),
        )
        line2 = JournalEntryLine(
            journal_entry_id=entry.id,
            account_id=revenue_account.id,
            credit_amount=Decimal("200.00"),
        )
        db.session.add_all([line1, line2])
        db.session.commit()
        retrieved_entry = JournalEntry.query.filter_by(user_id=user_id).first()
        assert retrieved_entry is not None
        assert retrieved_entry.description == "Service Income"
        assert len(retrieved_entry.lines) == 2

    def test_journal_entry_validation(self) -> Any:
        user_id = "user101"
        cash_account = create_test_account(user_id, "1000", "Cash", "asset", "debit")
        revenue_account = create_test_account(
            user_id, "4000", "Revenue", "revenue", "credit"
        )
        entry_balanced = JournalEntry(
            user_id=user_id,
            entry_number="JE003",
            description="Balanced Entry",
            entry_date=date.today(),
            total_amount=Decimal("50.00"),
            status="draft",
        )
        db.session.add(entry_balanced)
        db.session.flush()
        line_b1 = JournalEntryLine(
            journal_entry_id=entry_balanced.id,
            account_id=cash_account.id,
            debit_amount=Decimal("50.00"),
        )
        line_b2 = JournalEntryLine(
            journal_entry_id=entry_balanced.id,
            account_id=revenue_account.id,
            credit_amount=Decimal("50.00"),
        )
        db.session.add_all([line_b1, line_b2])
        db.session.commit()
        assert entry_balanced.validate_entry() == True
        entry_unbalanced = JournalEntry(
            user_id=user_id,
            entry_number="JE004",
            description="Unbalanced Entry",
            entry_date=date.today(),
            total_amount=Decimal("100.00"),
            status="draft",
        )
        db.session.add(entry_unbalanced)
        db.session.flush()
        line_u1 = JournalEntryLine(
            journal_entry_id=entry_unbalanced.id,
            account_id=cash_account.id,
            debit_amount=Decimal("100.00"),
        )
        line_u2 = JournalEntryLine(
            journal_entry_id=entry_unbalanced.id,
            account_id=revenue_account.id,
            credit_amount=Decimal("50.00"),
        )
        db.session.add_all([line_u1, line_u2])
        db.session.commit()
        assert entry_unbalanced.validate_entry() == False


class TestFinancialPeriodModel:

    def test_financial_period_creation(self) -> Any:
        period = FinancialPeriod(
            user_id="user123",
            period_name="Q1 2024",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            period_type="quarterly",
            fiscal_year=2024,
        )
        db.session.add(period)
        db.session.commit()
        retrieved_period = FinancialPeriod.query.filter_by(user_id="user123").first()
        assert retrieved_period is not None
        assert retrieved_period.period_name == "Q1 2024"


class TestBudgetModel:

    def test_budget_creation(self) -> Any:
        user_id = "user123"
        account = create_test_account(
            user_id, "6000", "Marketing Expense", "expense", "debit"
        )
        period = FinancialPeriod(
            user_id=user_id,
            period_name="FY2024",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            period_type="yearly",
            fiscal_year=2024,
        )
        db.session.add(period)
        db.session.commit()
        budget = Budget(
            user_id=user_id,
            account_id=account.id,
            period_id=period.id,
            budgeted_amount=Decimal("5000.00"),
        )
        db.session.add(budget)
        db.session.commit()
        retrieved_budget = Budget.query.filter_by(user_id=user_id).first()
        assert retrieved_budget is not None
        assert retrieved_budget.budgeted_amount == Decimal("5000.00")
        assert retrieved_budget.account.account_name == "Marketing Expense"
        assert retrieved_budget.period.period_name == "FY2024"
