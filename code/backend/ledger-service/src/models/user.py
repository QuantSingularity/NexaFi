from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional


class BaseModel:
    """Base model with database operations - delegates to shared BaseModel"""

    table_name = None
    db_manager = None

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def find_by_id(cls: Any, id_value: Any) -> Any:
        """Find record by ID - delegates to actual shared BaseModel if available"""
        # Import actual BaseModel from shared if available
        try:
            import os
            import sys

            sys.path.insert(
                0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared")
            )
            from database.manager import BaseModel as SharedBaseModel

            return (
                SharedBaseModel.find_by_id(id_value)
                if hasattr(SharedBaseModel, "find_by_id")
                else None
            )
        except (ImportError, AttributeError):
            return None

    @classmethod
    def find_all(cls: Any, where_clause: str = "", params: tuple = ()) -> Any:
        """Find all records - delegates to actual shared BaseModel if available"""
        try:
            import os
            import sys

            sys.path.insert(
                0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared")
            )
            from database.manager import BaseModel as SharedBaseModel

            return (
                SharedBaseModel.find_all(where_clause, params)
                if hasattr(SharedBaseModel, "find_all")
                else []
            )
        except (ImportError, AttributeError):
            return []

    @classmethod
    def find_one(cls: Any, where_clause: str, params: tuple = ()) -> Any:
        """Find one record - delegates to actual shared BaseModel if available"""
        try:
            import os
            import sys

            sys.path.insert(
                0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared")
            )
            from database.manager import BaseModel as SharedBaseModel

            return (
                SharedBaseModel.find_one(where_clause, params)
                if hasattr(SharedBaseModel, "find_one")
                else None
            )
        except (ImportError, AttributeError):
            return None

    def save(self) -> None:
        """Save record - delegates to actual shared BaseModel if available"""
        try:
            import os
            import sys

            sys.path.insert(
                0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared")
            )
            from database.manager import BaseModel as SharedBaseModel

            if hasattr(SharedBaseModel, "save"):
                SharedBaseModel.save(self)
        except (ImportError, AttributeError):
            pass

    def delete(self) -> Any:
        pass

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


class Account(BaseModel):
    table_name: Optional[str] = "accounts"

    def get_balance(self, as_of_date: Optional[datetime] = None) -> Decimal:
        """Calculate account balance as of a specific date"""
        if as_of_date is None:
            return Decimal(str(self.current_balance))
        return Decimal(str(self.current_balance))

    def to_dict(self) -> Any:
        data = super().to_dict()
        data["opening_balance"] = str(data.get("opening_balance", 0))
        data["current_balance"] = str(data.get("current_balance", 0))
        return data


class JournalEntry(BaseModel):
    table_name: Optional[str] = "journal_entries"

    def to_dict(self, include_lines: Any = False) -> Any:
        data = super().to_dict()
        data["total_debit"] = str(data.get("total_debit", 0))
        data["total_credit"] = str(data.get("total_credit", 0))
        if include_lines:
            data["lines"] = []
        return data


class JournalEntryLine(BaseModel):
    table_name: Optional[str] = "journal_entry_lines"

    def to_dict(self) -> Any:
        data = super().to_dict()
        data["debit_amount"] = str(data.get("debit_amount", 0))
        data["credit_amount"] = str(data.get("credit_amount", 0))
        return data


class ExchangeRate(BaseModel):
    table_name: Optional[str] = "exchange_rates"

    def to_dict(self) -> Any:
        data = super().to_dict()
        data["rate"] = str(data.get("rate", 1.0))
        return data


class Reconciliation(BaseModel):
    table_name: Optional[str] = "reconciliations"

    def to_dict(self) -> Any:
        data = super().to_dict()
        data["statement_balance"] = str(data.get("statement_balance", 0))
        data["book_balance"] = str(data.get("book_balance", 0))
        data["difference"] = str(data.get("difference", 0))
        return data


class FinancialPeriod(BaseModel):
    table_name: Optional[str] = "financial_periods"

    def to_dict(self) -> Any:
        return super().to_dict()


class Budget(BaseModel):
    table_name: Optional[str] = "budgets"

    def to_dict(self) -> Any:
        data = super().to_dict()
        data["budgeted_amount"] = str(data.get("budgeted_amount", 0))
        data["actual_amount"] = str(data.get("actual_amount", 0))
        data["variance"] = str(data.get("variance", 0))
        return data
