import os
import sys
from datetime import datetime
from decimal import Decimal
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared"))
from database.manager import BaseModel


class Account(BaseModel):
    table_name: Optional[str] = "accounts"

    def get_balance(self, as_of_date: Optional[datetime] = None) -> Decimal:
        if as_of_date is None:
            return Decimal(str(self.current_balance))
        return Decimal(str(self.current_balance))

    def to_dict(self) -> object:
        data = super().to_dict()
        data["opening_balance"] = str(data.get("opening_balance", 0))
        data["current_balance"] = str(data.get("current_balance", 0))
        return data


class JournalEntry(BaseModel):
    table_name: Optional[str] = "journal_entries"

    def to_dict(self, include_lines: object = False) -> object:
        data = super().to_dict()
        data["total_debit"] = str(data.get("total_debit", 0))
        data["total_credit"] = str(data.get("total_credit", 0))
        if include_lines:
            data["lines"] = []
        return data


class JournalEntryLine(BaseModel):
    table_name: Optional[str] = "journal_entry_lines"

    def to_dict(self) -> object:
        data = super().to_dict()
        data["debit_amount"] = str(data.get("debit_amount", 0))
        data["credit_amount"] = str(data.get("credit_amount", 0))
        return data


class ExchangeRate(BaseModel):
    table_name: Optional[str] = "exchange_rates"

    def to_dict(self) -> object:
        data = super().to_dict()
        data["rate"] = str(data.get("rate", 1.0))
        return data


class Reconciliation(BaseModel):
    table_name: Optional[str] = "reconciliations"

    def to_dict(self) -> object:
        data = super().to_dict()
        data["statement_balance"] = str(data.get("statement_balance", 0))
        data["book_balance"] = str(data.get("book_balance", 0))
        data["difference"] = str(data.get("difference", 0))
        return data


class FinancialPeriod(BaseModel):
    table_name: Optional[str] = "financial_periods"

    def to_dict(self) -> object:
        return super().to_dict()


class Budget(BaseModel):
    table_name: Optional[str] = "budgets"

    def to_dict(self) -> object:
        data = super().to_dict()
        data["budgeted_amount"] = str(data.get("budgeted_amount", 0))
        data["actual_amount"] = str(data.get("actual_amount", 0))
        data["variance"] = str(data.get("variance", 0))
        return data
