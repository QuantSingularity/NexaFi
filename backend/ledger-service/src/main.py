import os
import sys
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from flask import Flask, g, jsonify, request
from flask_cors import CORS

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "shared"))
from audit.audit_logger import AuditEventType, AuditSeverity, audit_action, audit_logger
from database.manager import BaseModel, initialize_database
from middleware.auth import require_auth, require_permission
from models.user import (
    Account,
    ExchangeRate,
    JournalEntry,
    JournalEntryLine,
    Reconciliation,
)
from nexafi_logging.logger import get_logger, setup_request_logging
from routes.user import ledger_bp
from validation_schemas.schemas import (
    AccountSchema,
    FinancialValidators,
    JournalEntrySchema,
    SanitizationMixin,
    Schema,
    fields,
    validate,
    validate_json_request,
)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "nexafi-ledger-service-secret-key-2024"
)
app.register_blueprint(ledger_bp, url_prefix="/api/v1/ledger")
CORS(app, origins="*", allow_headers=["Content-Type", "Authorization", "X-User-ID"])
setup_request_logging(app)
logger = get_logger("ledger_service")
db_path = os.path.join(os.path.dirname(__file__), "database", "app.db")
os.makedirs(os.path.dirname(db_path), exist_ok=True)
db_manager, migration_manager = initialize_database(db_path)
LEDGER_MIGRATIONS = {
    "011_create_accounts_table": {
        "description": "Create accounts table with multi-currency support",
        "sql": "\n        CREATE TABLE IF NOT EXISTS accounts (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            account_code TEXT UNIQUE NOT NULL,\n            name TEXT NOT NULL,\n            account_type TEXT NOT NULL,\n            account_subtype TEXT,\n            parent_account_id INTEGER,\n            currency TEXT NOT NULL DEFAULT 'USD',\n            is_active BOOLEAN DEFAULT 1,\n            is_system BOOLEAN DEFAULT 0,\n            description TEXT,\n            opening_balance DECIMAL(15,2) DEFAULT 0.00,\n            current_balance DECIMAL(15,2) DEFAULT 0.00,\n            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n            FOREIGN KEY (parent_account_id) REFERENCES accounts(id)\n        );\n\n        CREATE INDEX IF NOT EXISTS idx_accounts_code ON accounts(account_code);\n        CREATE INDEX IF NOT EXISTS idx_accounts_type ON accounts(account_type);\n        CREATE INDEX IF NOT EXISTS idx_accounts_parent ON accounts(parent_account_id);\n        ",
    },
    "012_create_journal_entries_table": {
        "description": "Create journal entries table",
        "sql": "\n        CREATE TABLE IF NOT EXISTS journal_entries (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            entry_number TEXT UNIQUE NOT NULL,\n            description TEXT NOT NULL,\n            reference_number TEXT,\n            entry_date DATE NOT NULL,\n            posting_date DATE,\n            status TEXT NOT NULL DEFAULT 'draft',\n            total_debit DECIMAL(15,2) NOT NULL DEFAULT 0.00,\n            total_credit DECIMAL(15,2) NOT NULL DEFAULT 0.00,\n            currency TEXT NOT NULL DEFAULT 'USD',\n            exchange_rate DECIMAL(10,6) DEFAULT 1.000000,\n            created_by TEXT,\n            approved_by TEXT,\n            posted_by TEXT,\n            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n        );\n\n        CREATE INDEX IF NOT EXISTS idx_journal_entries_number ON journal_entries(entry_number);\n        CREATE INDEX IF NOT EXISTS idx_journal_entries_date ON journal_entries(entry_date);\n        CREATE INDEX IF NOT EXISTS idx_journal_entries_status ON journal_entries(status);\n        ",
    },
    "013_create_journal_entry_lines_table": {
        "description": "Create journal entry lines table",
        "sql": "\n        CREATE TABLE IF NOT EXISTS journal_entry_lines (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            journal_entry_id INTEGER NOT NULL,\n            account_id INTEGER NOT NULL,\n            description TEXT,\n            debit_amount DECIMAL(15,2) DEFAULT 0.00,\n            credit_amount DECIMAL(15,2) DEFAULT 0.00,\n            line_number INTEGER NOT NULL,\n            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n            FOREIGN KEY (journal_entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE,\n            FOREIGN KEY (account_id) REFERENCES accounts(id)\n        );\n\n        CREATE INDEX IF NOT EXISTS idx_journal_lines_entry_id ON journal_entry_lines(journal_entry_id);\n        CREATE INDEX IF NOT EXISTS idx_journal_lines_account_id ON journal_entry_lines(account_id);\n        ",
    },
    "014_create_exchange_rates_table": {
        "description": "Create exchange rates table",
        "sql": "\n        CREATE TABLE IF NOT EXISTS exchange_rates (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            from_currency TEXT NOT NULL,\n            to_currency TEXT NOT NULL,\n            rate DECIMAL(10,6) NOT NULL,\n            rate_date DATE NOT NULL,\n            source TEXT DEFAULT 'manual',\n            is_active BOOLEAN DEFAULT 1,\n            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n        );\n\n        CREATE INDEX IF NOT EXISTS idx_exchange_rates_currencies ON exchange_rates(from_currency, to_currency);\n        CREATE INDEX IF NOT EXISTS idx_exchange_rates_date ON exchange_rates(rate_date);\n        ",
    },
    "015_create_reconciliations_table": {
        "description": "Create reconciliations table",
        "sql": "\n        CREATE TABLE IF NOT EXISTS reconciliations (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            account_id INTEGER NOT NULL,\n            reconciliation_date DATE NOT NULL,\n            statement_balance DECIMAL(15,2) NOT NULL,\n            book_balance DECIMAL(15,2) NOT NULL,\n            difference DECIMAL(15,2) NOT NULL,\n            status TEXT NOT NULL DEFAULT 'pending',\n            reconciled_by TEXT,\n            reconciled_at TIMESTAMP,\n            notes TEXT,\n            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n            FOREIGN KEY (account_id) REFERENCES accounts(id)\n        );\n\n        CREATE INDEX IF NOT EXISTS idx_reconciliations_account ON reconciliations(account_id);\n        CREATE INDEX IF NOT EXISTS idx_reconciliations_date ON reconciliations(reconciliation_date);\n        ",
    },
}
for version, migration in LEDGER_MIGRATIONS.items():
    migration_manager.apply_migration(
        version, migration["description"], migration["sql"]
    )
BaseModel.set_db_manager(db_manager)
# Note: Account, JournalEntry, JournalEntryLine, ExchangeRate, and Reconciliation
# classes are imported from models.user - no redefinition needed


class AccountSchema(AccountSchema):
    account_code = fields.Str(required=True, validate=validate.Length(min=3, max=20))
    account_subtype = fields.Str(
        required=False,
        validate=validate.OneOf(
            [
                "cash",
                "bank",
                "accounts_receivable",
                "inventory",
                "fixed_assets",
                "accounts_payable",
                "accrued_liabilities",
                "long_term_debt",
                "common_stock",
                "retained_earnings",
                "sales_revenue",
                "service_revenue",
                "cost_of_goods_sold",
                "operating_expenses",
                "interest_expense",
            ]
        ),
    )
    currency = fields.Str(
        required=False, validate=FinancialValidators.validate_currency_code
    )
    opening_balance = fields.Raw(
        required=False, validate=FinancialValidators.validate_amount
    )


class JournalEntrySchema(JournalEntrySchema):
    currency = fields.Str(
        required=False, validate=FinancialValidators.validate_currency_code
    )
    exchange_rate = fields.Decimal(
        required=False, validate=validate.Range(min=1e-06, max=999999)
    )


class ExchangeRateSchema(SanitizationMixin, Schema):
    from_currency = fields.Str(
        required=True, validate=FinancialValidators.validate_currency_code
    )
    to_currency = fields.Str(
        required=True, validate=FinancialValidators.validate_currency_code
    )
    rate = fields.Decimal(required=True, validate=validate.Range(min=1e-06, max=999999))
    rate_date = fields.Date(required=False)


class ReconciliationSchema(SanitizationMixin, Schema):
    account_id = fields.Int(required=True)
    reconciliation_date = fields.Date(required=True)
    statement_balance = fields.Raw(
        required=True, validate=FinancialValidators.validate_amount
    )
    notes = fields.Str(required=False, validate=validate.Length(max=1000))


DEFAULT_CHART_OF_ACCOUNTS = {
    "1000": {"name": "Cash and Cash Equivalents", "type": "asset", "subtype": "cash"},
    "1100": {
        "name": "Checking Account",
        "type": "asset",
        "subtype": "bank",
        "parent": "1000",
    },
    "1200": {
        "name": "Savings Account",
        "type": "asset",
        "subtype": "bank",
        "parent": "1000",
    },
    "1300": {
        "name": "Accounts Receivable",
        "type": "asset",
        "subtype": "accounts_receivable",
    },
    "1400": {"name": "Inventory", "type": "asset", "subtype": "inventory"},
    "1500": {"name": "Fixed Assets", "type": "asset", "subtype": "fixed_assets"},
    "2000": {"name": "Current Liabilities", "type": "liability"},
    "2100": {
        "name": "Accounts Payable",
        "type": "liability",
        "subtype": "accounts_payable",
        "parent": "2000",
    },
    "2200": {
        "name": "Accrued Expenses",
        "type": "liability",
        "subtype": "accrued_liabilities",
        "parent": "2000",
    },
    "2300": {
        "name": "Long-term Debt",
        "type": "liability",
        "subtype": "long_term_debt",
    },
    "3000": {"name": "Equity", "type": "equity"},
    "3100": {
        "name": "Common Stock",
        "type": "equity",
        "subtype": "common_stock",
        "parent": "3000",
    },
    "3200": {
        "name": "Retained Earnings",
        "type": "equity",
        "subtype": "retained_earnings",
        "parent": "3000",
    },
    "4000": {"name": "Revenue", "type": "revenue"},
    "4100": {
        "name": "Sales Revenue",
        "type": "revenue",
        "subtype": "sales_revenue",
        "parent": "4000",
    },
    "4200": {
        "name": "Service Revenue",
        "type": "revenue",
        "subtype": "service_revenue",
        "parent": "4000",
    },
    "5000": {
        "name": "Cost of Goods Sold",
        "type": "expense",
        "subtype": "cost_of_goods_sold",
    },
    "6000": {
        "name": "Operating Expenses",
        "type": "expense",
        "subtype": "operating_expenses",
    },
    "6100": {
        "name": "Salaries and Wages",
        "type": "expense",
        "subtype": "operating_expenses",
        "parent": "6000",
    },
    "6200": {
        "name": "Rent Expense",
        "type": "expense",
        "subtype": "operating_expenses",
        "parent": "6000",
    },
    "6300": {
        "name": "Utilities Expense",
        "type": "expense",
        "subtype": "operating_expenses",
        "parent": "6000",
    },
    "7000": {
        "name": "Interest Expense",
        "type": "expense",
        "subtype": "interest_expense",
    },
}


def initialize_chart_of_accounts() -> Any:
    """Initialize default chart of accounts"""
    for account_code, account_data in DEFAULT_CHART_OF_ACCOUNTS.items():
        existing = Account.find_one("account_code = ?", (account_code,))
        if not existing:
            parent_id = None
            if "parent" in account_data:
                parent_account = Account.find_one(
                    "account_code = ?", (account_data["parent"],)
                )
                if parent_account:
                    parent_id = parent_account.id
            account = Account(
                account_code=account_code,
                name=account_data["name"],
                account_type=account_data["type"],
                account_subtype=account_data.get("subtype"),
                parent_account_id=parent_id,
                is_system=True,
            )
            account.save()


@app.route("/api/v1/health", methods=["GET"])
def health_check() -> Any:
    """Health check endpoint"""
    return jsonify(
        {
            "status": "healthy",
            "service": "ledger-service",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "2.0.0",
        }
    )


@app.route("/api/v1/accounts", methods=["GET"])
@require_auth
@require_permission("account:read")
def list_accounts() -> Any:
    """List all accounts"""
    account_type = request.args.get("type")
    currency = request.args.get("currency")
    active_only = request.args.get("active_only", "true").lower() == "true"
    where_clause = "1=1"
    params = []
    if account_type:
        where_clause += " AND account_type = ?"
        params.append(account_type)
    if currency:
        where_clause += " AND currency = ?"
        params.append(currency)
    if active_only:
        where_clause += " AND is_active = 1"
    where_clause += " ORDER BY account_code"
    accounts = Account.find_all(where_clause, tuple(params))
    account_data = []
    for account in accounts:
        data = account.to_dict()
        data["current_balance"] = str(account.get_balance())
        account_data.append(data)
    return jsonify({"accounts": account_data, "total": len(account_data)})


@app.route("/api/v1/accounts", methods=["POST"])
@require_auth
@require_permission("account:write")
@validate_json_request(AccountSchema)
@audit_action(
    AuditEventType.ACCOUNT_CREATE, "account_created", severity=AuditSeverity.MEDIUM
)
def create_account() -> Any:
    """Create a new account"""
    data = request.validated_data  # type: ignore[attr-defined]
    existing = Account.find_one("account_code = ?", (data["account_code"],))
    if existing:
        return (jsonify({"error": "Account code already exists"}), 409)
    account = Account(
        account_code=data["account_code"],
        name=data["name"],
        account_type=data["account_type"],
        account_subtype=data.get("account_subtype"),
        parent_account_id=data.get("parent_account_id"),
        currency=data.get("currency", "USD"),
        description=data.get("description"),
        opening_balance=float(data.get("opening_balance", 0)),
    )
    account.current_balance = account.opening_balance
    account.save()
    audit_logger.log_event(
        AuditEventType.ACCOUNT_CREATE,
        "account_created",
        user_id=g.current_user["user_id"],
        resource_type="account",
        resource_id=str(account.id),
        details={
            "account_code": account.account_code,
            "name": account.name,
            "account_type": account.account_type,
            "currency": account.currency,
        },
    )
    return (
        jsonify(
            {"message": "Account created successfully", "account": account.to_dict()}
        ),
        201,
    )


@app.route("/api/v1/accounts/<int:account_id>/balance", methods=["GET"])
@require_auth
@require_permission("account:read")
def get_account_balance(account_id: Any) -> Any:
    """Get account balance as of a specific date"""
    as_of_date_str = request.args.get("as_of_date")
    as_of_date: Optional[datetime] = None
    account = Account.find_by_id(account_id)
    if not account:
        return (jsonify({"error": "Account not found"}), 404)
    if as_of_date_str:
        try:
            as_of_date = datetime.fromisoformat(as_of_date_str)
        except ValueError:
            return (jsonify({"error": "Invalid date format"}), 400)
    balance = account.get_balance(as_of_date)
    return jsonify(
        {
            "account_id": account_id,
            "account_code": account.account_code,
            "account_name": account.name,
            "balance": str(balance),
            "currency": account.currency,
            "as_of_date": (
                as_of_date.isoformat()
                if isinstance(as_of_date, datetime)
                else as_of_date if as_of_date else datetime.utcnow().isoformat()
            ),
        }
    )


@app.route("/api/v1/journal-entries", methods=["POST"])
@require_auth
@require_permission("transaction:write")
@validate_json_request(JournalEntrySchema)
@audit_action(
    AuditEventType.JOURNAL_ENTRY_CREATE,
    "journal_entry_created",
    severity=AuditSeverity.HIGH,
)
def create_journal_entry() -> Any:
    """Create a new journal entry"""
    data = request.validated_data  # type: ignore[attr-defined]
    lines_data = request.get_json().get("lines", [])
    if not lines_data:
        return (jsonify({"error": "Journal entry must have at least one line"}), 400)
    entry_number = (
        f"JE-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    )
    entry = JournalEntry(
        entry_number=entry_number,
        description=data["description"],
        reference_number=data.get("reference_number"),
        entry_date=data.get("entry_date", datetime.utcnow().date()),
        currency=data.get("currency", "USD"),
        exchange_rate=float(data.get("exchange_rate", 1.0)),
        created_by=g.current_user["user_id"],
    )
    entry.save()
    total_debits = Decimal("0")
    total_credits = Decimal("0")
    for i, line_data in enumerate(lines_data):
        if "account_id" not in line_data:
            return (jsonify({"error": f"Line {i + 1}: account_id is required"}), 400)
        account = Account.find_by_id(line_data["account_id"])
        if not account:
            return (jsonify({"error": f"Line {i + 1}: Account not found"}), 400)
        debit_amount = Decimal(str(line_data.get("debit_amount", 0)))
        credit_amount = Decimal(str(line_data.get("credit_amount", 0)))
        if debit_amount == 0 and credit_amount == 0:
            return (
                jsonify(
                    {
                        "error": f"Line {i + 1}: Either debit or credit amount must be specified"
                    }
                ),
                400,
            )
        if debit_amount > 0 and credit_amount > 0:
            return (
                jsonify(
                    {
                        "error": f"Line {i + 1}: Cannot have both debit and credit amounts"
                    }
                ),
                400,
            )
        line = JournalEntryLine(
            journal_entry_id=entry.id,
            account_id=line_data["account_id"],
            description=line_data.get("description"),
            debit_amount=float(debit_amount),
            credit_amount=float(credit_amount),
            line_number=i + 1,
        )
        line.save()
        total_debits += debit_amount
        total_credits += credit_amount
    entry.total_debit = float(total_debits)
    entry.total_credit = float(total_credits)
    entry.save()
    is_valid, message = entry.validate_entry()
    if not is_valid:
        for line in entry.get_lines():
            line.delete()
        entry.delete()
        return (jsonify({"error": message}), 400)
    audit_logger.log_event(
        AuditEventType.JOURNAL_ENTRY_CREATE,
        "journal_entry_created",
        user_id=g.current_user["user_id"],
        resource_type="journal_entry",
        resource_id=str(entry.id),
        details={
            "entry_number": entry.entry_number,
            "total_debit": str(entry.total_debit),
            "total_credit": str(entry.total_credit),
            "line_count": len(lines_data),
        },
    )
    return (
        jsonify(
            {
                "message": "Journal entry created successfully",
                "journal_entry": entry.to_dict(),
                "lines": [line.to_dict() for line in entry.get_lines()],
            }
        ),
        201,
    )


@app.route("/api/v1/journal-entries/<int:entry_id>/post", methods=["POST"])
@require_auth
@require_permission("transaction:write")
@audit_action(
    AuditEventType.JOURNAL_ENTRY_POST,
    "journal_entry_posted",
    severity=AuditSeverity.HIGH,
)
def post_journal_entry(entry_id: Any) -> Any:
    """Post a journal entry"""
    entry = JournalEntry.find_by_id(entry_id)
    if not entry:
        return (jsonify({"error": "Journal entry not found"}), 404)
    if entry.status == "posted":
        return (jsonify({"error": "Journal entry is already posted"}), 400)
    try:
        entry.post_entry(g.current_user["user_id"])
        return jsonify(
            {
                "message": "Journal entry posted successfully",
                "entry_number": entry.entry_number,
                "posting_date": entry.posting_date.isoformat(),
            }
        )
    except ValueError as e:
        return (jsonify({"error": str(e)}), 400)


@app.route("/api/v1/exchange-rates", methods=["POST"])
@require_auth
@require_permission("account:write")
@validate_json_request(ExchangeRateSchema)
@audit_action(
    AuditEventType.SYSTEM_CONFIG_CHANGE,
    "exchange_rate_updated",
    severity=AuditSeverity.MEDIUM,
)
def update_exchange_rate() -> Any:
    """Update exchange rate"""
    data = request.validated_data  # type: ignore[attr-defined]
    existing_rates = ExchangeRate.find_all(
        "from_currency = ? AND to_currency = ? AND rate_date = ?",
        (
            data["from_currency"],
            data["to_currency"],
            data.get("rate_date", datetime.utcnow().date()),
        ),
    )
    for rate in existing_rates:
        rate.is_active = False
        rate.save()
    exchange_rate = ExchangeRate(
        from_currency=data["from_currency"],
        to_currency=data["to_currency"],
        rate=float(data["rate"]),
        rate_date=data.get("rate_date", datetime.utcnow().date()),
        source="manual",
    )
    exchange_rate.save()
    audit_logger.log_event(
        AuditEventType.SYSTEM_CONFIG_CHANGE,
        "exchange_rate_updated",
        user_id=g.current_user["user_id"],
        resource_type="exchange_rate",
        resource_id=str(exchange_rate.id),
        details={
            "from_currency": data["from_currency"],
            "to_currency": data["to_currency"],
            "rate": str(data["rate"]),
            "rate_date": str(data.get("rate_date", datetime.utcnow().date())),
        },
    )
    return (
        jsonify(
            {
                "message": "Exchange rate updated successfully",
                "exchange_rate": exchange_rate.to_dict(),
            }
        ),
        201,
    )


@app.route("/api/v1/reconciliations", methods=["POST"])
@require_auth
@require_permission("account:write")
@validate_json_request(ReconciliationSchema)
@audit_action(
    AuditEventType.ACCOUNT_UPDATE,
    "reconciliation_created",
    severity=AuditSeverity.MEDIUM,
)
def create_reconciliation() -> Any:
    """Create account reconciliation"""
    data = request.validated_data  # type: ignore[attr-defined]
    account = Account.find_by_id(data["account_id"])
    if not account:
        return (jsonify({"error": "Account not found"}), 404)
    book_balance = account.get_balance(
        datetime.combine(data["reconciliation_date"], datetime.min.time())
    )
    statement_balance = Decimal(str(data["statement_balance"]))
    difference = statement_balance - book_balance
    reconciliation = Reconciliation(
        account_id=data["account_id"],
        reconciliation_date=data["reconciliation_date"],
        statement_balance=float(statement_balance),
        book_balance=float(book_balance),
        difference=float(difference),
        status="pending" if difference != 0 else "reconciled",
        notes=data.get("notes"),
    )
    if difference == 0:
        reconciliation.reconciled_by = g.current_user["user_id"]
        reconciliation.reconciled_at = datetime.utcnow()
    reconciliation.save()
    audit_logger.log_event(
        AuditEventType.ACCOUNT_UPDATE,
        "reconciliation_created",
        user_id=g.current_user["user_id"],
        resource_type="reconciliation",
        resource_id=str(reconciliation.id),
        details={
            "account_id": data["account_id"],
            "account_code": account.account_code,
            "statement_balance": str(statement_balance),
            "book_balance": str(book_balance),
            "difference": str(difference),
        },
    )
    return (
        jsonify(
            {
                "message": "Reconciliation created successfully",
                "reconciliation": reconciliation.to_dict(),
                "requires_adjustment": difference != 0,
            }
        ),
        201,
    )


@app.route("/api/v1/reports/trial-balance", methods=["GET"])
@require_auth
@require_permission("report:read")
def trial_balance() -> Any:
    """Generate trial balance report"""
    as_of_date_str = request.args.get("as_of_date")
    as_of_date: Optional[datetime] = None
    currency = request.args.get("currency", "USD")
    if as_of_date_str:
        try:
            as_of_date = datetime.fromisoformat(as_of_date_str)
        except ValueError:
            return (jsonify({"error": "Invalid date format"}), 400)
    else:
        as_of_date = datetime.utcnow()
    accounts = Account.find_all(
        "is_active = 1 AND currency = ? ORDER BY account_code", (currency,)
    )
    trial_balance_data = []
    total_debits = Decimal("0")
    total_credits = Decimal("0")
    for account in accounts:
        balance = account.get_balance(as_of_date)
        if balance != 0:
            if account.account_type in ["asset", "expense"]:
                debit_balance = balance if balance > 0 else Decimal("0")
                credit_balance = abs(balance) if balance < 0 else Decimal("0")
            else:
                debit_balance = abs(balance) if balance < 0 else Decimal("0")
                credit_balance = balance if balance > 0 else Decimal("0")
            trial_balance_data.append(
                {
                    "account_code": account.account_code,
                    "account_name": account.name,
                    "account_type": account.account_type,
                    "debit_balance": str(debit_balance),
                    "credit_balance": str(credit_balance),
                }
            )
            total_debits += debit_balance
            total_credits += credit_balance
    return jsonify(
        {
            "report_type": "trial_balance",
            "as_of_date": (
                as_of_date.isoformat()
                if isinstance(as_of_date, datetime)
                else as_of_date
            ),
            "currency": currency,
            "accounts": trial_balance_data,
            "totals": {
                "total_debits": str(total_debits),
                "total_credits": str(total_credits),
                "difference": str(total_debits - total_credits),
            },
            "is_balanced": total_debits == total_credits,
        }
    )


@app.route("/api/v1/reports/balance-sheet", methods=["GET"])
@require_auth
@require_permission("report:read")
def balance_sheet() -> Any:
    """Generate balance sheet report"""
    as_of_date_str = request.args.get("as_of_date")
    as_of_date: Optional[datetime] = None
    currency = request.args.get("currency", "USD")
    if as_of_date_str:
        try:
            as_of_date = datetime.fromisoformat(as_of_date_str)
        except ValueError:
            return (jsonify({"error": "Invalid date format"}), 400)
    else:
        as_of_date = datetime.utcnow()
    assets = Account.find_all(
        "account_type = 'asset' AND is_active = 1 AND currency = ? ORDER BY account_code",
        (currency,),
    )
    liabilities = Account.find_all(
        "account_type = 'liability' AND is_active = 1 AND currency = ? ORDER BY account_code",
        (currency,),
    )
    equity = Account.find_all(
        "account_type = 'equity' AND is_active = 1 AND currency = ? ORDER BY account_code",
        (currency,),
    )

    def format_accounts(accounts_list):
        formatted = []
        total = Decimal("0")
        for account in accounts_list:
            balance = account.get_balance(as_of_date)
            if balance != 0:
                formatted.append(
                    {
                        "account_code": account.account_code,
                        "account_name": account.name,
                        "balance": str(balance),
                    }
                )
                total += balance
        return (formatted, total)

    assets_data, total_assets = format_accounts(assets)
    liabilities_data, total_liabilities = format_accounts(liabilities)
    equity_data, total_equity = format_accounts(equity)
    return jsonify(
        {
            "report_type": "balance_sheet",
            "as_of_date": (
                as_of_date.isoformat()
                if isinstance(as_of_date, datetime)
                else as_of_date
            ),
            "currency": currency,
            "assets": {"accounts": assets_data, "total": str(total_assets)},
            "liabilities": {
                "accounts": liabilities_data,
                "total": str(total_liabilities),
            },
            "equity": {"accounts": equity_data, "total": str(total_equity)},
            "total_liabilities_and_equity": str(total_liabilities + total_equity),
            "is_balanced": total_assets == total_liabilities + total_equity,
        }
    )


if __name__ == "__main__":
    os.makedirs(os.path.join(os.path.dirname(__file__), "database"), exist_ok=True)
    initialize_chart_of_accounts()
    app.run(host="0.0.0.0", port=5007, debug=True)
