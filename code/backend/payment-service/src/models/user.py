from typing import Any, Dict, Optional


class BaseModel:
    table_name = None
    db_manager = None

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def find_by_id(cls: Any, id_value: Any) -> Any:
        pass

    @classmethod
    def find_all(cls: Any, where_clause: str = "", params: tuple = ()) -> Any:
        pass

    @classmethod
    def find_one(cls: Any, where_clause: str, params: tuple = ()) -> Any:
        pass

    def save(self) -> Any:
        pass

    def delete(self) -> Any:
        pass

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


class PaymentMethod(BaseModel):
    table_name: Optional[str] = "payment_methods"

    def to_dict(self, include_sensitive: Any = False) -> Any:
        data = super().to_dict()
        if data.get("details"):
            if data.get("type") == "card":
                data["masked_details"] = {
                    "last_four": data["details"].get("last_four"),
                    "brand": data["details"].get("brand"),
                    "exp_month": data["details"].get("exp_month"),
                    "exp_year": data["details"].get("exp_year"),
                }
            elif data.get("type") == "bank_account":
                data["masked_details"] = {
                    "last_four": data["details"].get("last_four"),
                    "bank_name": data["details"].get("bank_name"),
                    "account_type": data["details"].get("account_type"),
                }
            elif data.get("type") == "digital_wallet":
                data["masked_details"] = {
                    "email": data["details"].get("email"),
                    "wallet_type": data["details"].get("wallet_type"),
                }
        if not include_sensitive:
            data.pop("details", None)
        return data


class Transaction(BaseModel):
    table_name: Optional[str] = "transactions"

    def to_dict(self) -> Any:
        data = super().to_dict()
        data["amount"] = str(data.get("amount", 0))
        data["fees"] = str(data.get("fees", 0))
        data["net_amount"] = str(data.get("net_amount", 0))
        return data


class Wallet(BaseModel):
    table_name: Optional[str] = "wallets"

    def to_dict(self) -> Any:
        data = super().to_dict()
        data["balance"] = str(data.get("balance", 0))
        data["available_balance"] = str(data.get("available_balance", 0))
        data["pending_balance"] = str(data.get("pending_balance", 0))
        data["reserved_balance"] = str(data.get("reserved_balance", 0))
        return data


class WalletBalanceHistory(BaseModel):
    table_name: Optional[str] = "wallet_balance_history"

    def to_dict(self) -> Any:
        data = super().to_dict()
        data["amount"] = str(data.get("amount", 0))
        data["balance_before"] = str(data.get("balance_before", 0))
        data["balance_after"] = str(data.get("balance_after", 0))
        return data


class PaymentProcessor(BaseModel):
    table_name: Optional[str] = "payment_processors"

    def to_dict(self, include_sensitive: Any = False) -> Any:
        data = super().to_dict()
        if not include_sensitive:
            data.pop("api_config", None)
        return data


class RecurringPayment(BaseModel):
    table_name: Optional[str] = "recurring_payments"

    def to_dict(self) -> Any:
        data = super().to_dict()
        data["amount"] = str(data.get("amount", 0))
        return data


class ExchangeRate(BaseModel):
    table_name: Optional[str] = "exchange_rates"

    def to_dict(self) -> Any:
        data = super().to_dict()
        data["rate"] = str(data.get("rate", 0))
        return data
