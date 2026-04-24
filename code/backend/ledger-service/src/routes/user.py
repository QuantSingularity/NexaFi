import uuid
from datetime import date, datetime
from decimal import Decimal
from functools import wraps
from typing import Any, List

from flask import Blueprint, jsonify, request
from models.user import Account, JournalEntry, JournalEntryLine

ledger_bp = Blueprint("ledger", __name__)


def require_user_id(f: object) -> object:
    """Decorator to extract user_id from request headers"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            return (jsonify({"error": "User ID is required in headers"}), 401)
        request.user_id = user_id
        return f(*args, **kwargs)

    return decorated_function


def generate_entry_number(user_id: str) -> object:
    """Generate unique journal entry number (simulated)"""
    return f"JE-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


@ledger_bp.route("/accounts", methods=["GET"])
@require_user_id
def get_accounts() -> object:
    """Get all accounts for user"""
    try:
        account_type = request.args.get("type")
        is_active = request.args.get("active", "true").lower() == "true"
        where_clause = "user_id = ?"
        params = [request.user_id]
        if account_type:
            where_clause += " AND account_type = ?"
            params.append(account_type)
        if is_active:
            where_clause += " AND is_active = 1"
        accounts = Account.find_all(
            where_clause + " ORDER BY account_code", tuple(params)
        )
        account_data: List[Any] = []
        for account in accounts:
            data = account.to_dict()
            data["balance"] = data["current_balance"]
            account_data.append(data)
        return (jsonify({"accounts": account_data, "total": len(account_data)}), 200)
    except Exception as e:
        return (jsonify({"error": "Failed to get accounts", "details": str(e)}), 500)


@ledger_bp.route("/accounts", methods=["POST"])
@require_user_id
def create_account() -> object:
    """Create new account"""
    try:
        data = request.get_json()
        required_fields = [
            "account_code",
            "account_name",
            "account_type",
            "normal_balance",
        ]
        for field in required_fields:
            if not data.get(field):
                return (jsonify({"error": f"{field} is required"}), 400)
        existing_account = Account.find_one(
            "user_id = ? AND account_code = ?", (request.user_id, data["account_code"])
        )
        if existing_account:
            return (jsonify({"error": "Account code already exists"}), 409)
        account = Account(
            id=str(uuid.uuid4()),
            user_id=request.user_id,
            account_code=data["account_code"],
            account_name=data["account_name"],
            account_type=data["account_type"],
            account_subtype=data.get("account_subtype"),
            parent_account_id=data.get("parent_account_id"),
            normal_balance=data["normal_balance"],
            description=data.get("description"),
            opening_balance=data.get("opening_balance", 0.0),
            current_balance=data.get("opening_balance", 0.0),
            is_active=data.get("is_active", True),
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )
        account.save()
        return (
            jsonify(
                {
                    "message": "Account created successfully",
                    "account": account.to_dict(),
                }
            ),
            201,
        )
    except Exception as e:
        return (jsonify({"error": "Failed to create account", "details": str(e)}), 500)


@ledger_bp.route("/accounts/<account_id>", methods=["GET"])
@require_user_id
def get_account(account_id: object) -> object:
    """Get specific account"""
    try:
        account = Account.find_one(
            "id = ? AND user_id = ?", (account_id, request.user_id)
        )
        if not account:
            return (jsonify({"error": "Account not found"}), 404)
        balance = account.current_balance
        account_data = account.to_dict()
        account_data["balance"] = float(balance)
        return (jsonify({"account": account_data}), 200)
    except Exception as e:
        return (jsonify({"error": "Failed to get account", "details": str(e)}), 500)


@ledger_bp.route("/accounts/<account_id>", methods=["PUT"])
@require_user_id
def update_account(account_id: object) -> object:
    """Update account"""
    try:
        account = Account.find_one(
            "id = ? AND user_id = ?", (account_id, request.user_id)
        )
        if not account:
            return (jsonify({"error": "Account not found"}), 404)
        data = request.get_json()
        updatable_fields = [
            "account_name",
            "account_type",
            "account_subtype",
            "description",
            "is_active",
            "parent_account_id",
        ]
        for field in updatable_fields:
            if field in data:
                setattr(account, field, data[field])
        account.updated_at = datetime.utcnow().isoformat()
        account.save()
        return (
            jsonify(
                {
                    "message": "Account updated successfully",
                    "account": account.to_dict(),
                }
            ),
            200,
        )
    except Exception as e:
        return (jsonify({"error": "Failed to update account", "details": str(e)}), 500)


@ledger_bp.route("/journal-entries", methods=["GET"])
@require_user_id
def get_journal_entries() -> object:
    """Get journal entries for user"""
    try:
        status = request.args.get("status")
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        where_clause = "user_id = ?"
        params = [request.user_id]
        if status:
            where_clause += " AND status = ?"
            params.append(status)
        if start_date:
            where_clause += " AND entry_date >= ?"
            params.append(start_date)
        if end_date:
            where_clause += " AND entry_date <= ?"
            params.append(end_date)
        entries = JournalEntry.find_all(
            where_clause + " ORDER BY entry_date DESC, entry_number DESC", tuple(params)
        )
        return (
            jsonify(
                {
                    "journal_entries": [entry.to_dict() for entry in entries],
                    "total": len(entries),
                }
            ),
            200,
        )
    except Exception as e:
        return (
            jsonify({"error": "Failed to get journal entries", "details": str(e)}),
            500,
        )


@ledger_bp.route("/journal-entries", methods=["POST"])
@require_user_id
def create_journal_entry() -> object:
    """Create new journal entry"""
    try:
        data = request.get_json()
        if not data.get("description") or not data.get("lines"):
            return (jsonify({"error": "Description and lines are required"}), 400)
        if len(data["lines"]) < 2:
            return (jsonify({"error": "At least two lines are required"}), 400)
        entry = JournalEntry(
            id=str(uuid.uuid4()),
            user_id=request.user_id,
            entry_number=generate_entry_number(request.user_id),
            description=data["description"],
            reference=data.get("reference"),
            entry_date=data.get("entry_date", date.today().isoformat()),
            source_type=data.get("source_type", "manual"),
            source_id=data.get("source_id"),
            created_by=request.user_id,
            status="draft",
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )
        total_debits = Decimal("0")
        total_credits = Decimal("0")
        lines_to_save: List[Any] = []
        for i, line_data in enumerate(data["lines"]):
            account = Account.find_one(
                "id = ? AND user_id = ?", (line_data.get("account_id"), request.user_id)
            )
            if not account:
                return (jsonify({"error": f"Invalid account ID for line {i + 1}"}), 400)
            debit_amount = Decimal(str(line_data.get("debit_amount", 0)))
            credit_amount = Decimal(str(line_data.get("credit_amount", 0)))
            if debit_amount == 0 and credit_amount == 0:
                return (
                    jsonify(
                        {
                            "error": f"Either debit or credit amount is required for line {i + 1}"
                        }
                    ),
                    400,
                )
            if debit_amount > 0 and credit_amount > 0:
                return (
                    jsonify(
                        {
                            "error": f"Line {i + 1} cannot have both debit and credit amounts"
                        }
                    ),
                    400,
                )
            line = JournalEntryLine(
                id=str(uuid.uuid4()),
                journal_entry_id=entry.id,
                account_id=account.id,
                description=line_data.get("description"),
                debit_amount=float(debit_amount),
                credit_amount=float(credit_amount),
                line_number=i + 1,
                created_at=datetime.utcnow().isoformat(),
            )
            lines_to_save.append(line)
            total_debits += debit_amount
            total_credits += credit_amount
        if total_debits != total_credits:
            return (jsonify({"error": "Total debits must equal total credits"}), 400)
        entry.total_amount = float(total_debits)
        entry.save()
        for line in lines_to_save:
            line.save()
        if data.get("auto_post", False):
            entry.status = "posted"
            entry.posted_by = request.user_id
            entry.posted_at = datetime.utcnow().isoformat()
            entry.save()
        return (
            jsonify(
                {
                    "message": "Journal entry created successfully",
                    "journal_entry": entry.to_dict(),
                }
            ),
            201,
        )
    except Exception as e:
        return (
            jsonify({"error": "Failed to create journal entry", "details": str(e)}),
            500,
        )


@ledger_bp.route("/journal-entries/<entry_id>/post", methods=["POST"])
@require_user_id
def post_journal_entry(entry_id: object) -> object:
    """Post a journal entry (simplified, full posting logic is in main.py)"""
    try:
        entry = JournalEntry.find_one(
            "id = ? AND user_id = ?", (entry_id, request.user_id)
        )
        if not entry:
            return (jsonify({"error": "Journal entry not found"}), 404)
        if entry.status != "draft":
            return (jsonify({"error": "Only draft entries can be posted"}), 400)
        entry.status = "posted"
        entry.posted_by = request.user_id
        entry.posted_at = datetime.utcnow().isoformat()
        entry.save()
        return (
            jsonify(
                {
                    "message": "Journal entry posted successfully",
                    "journal_entry": entry.to_dict(),
                }
            ),
            200,
        )
    except Exception as e:
        return (
            jsonify({"error": "Failed to post journal entry", "details": str(e)}),
            500,
        )


@ledger_bp.route("/reports/trial-balance", methods=["GET"])
@require_user_id
def get_trial_balance() -> object:
    """Generate trial balance report (simulated)"""
    return (
        jsonify({"error": "Report generation is handled by the core logic in main.py"}),
        501,
    )


@ledger_bp.route("/reports/balance-sheet", methods=["GET"])
@require_user_id
def get_balance_sheet() -> object:
    """Generate balance sheet report (simulated)"""
    return (
        jsonify({"error": "Report generation is handled by the core logic in main.py"}),
        501,
    )


@ledger_bp.route("/reports/income-statement", methods=["GET"])
@require_user_id
def get_income_statement() -> object:
    """Generate income statement report (simulated)"""
    return (
        jsonify({"error": "Report generation is handled by the core logic in main.py"}),
        501,
    )


@ledger_bp.route("/accounts/initialize", methods=["POST"])
@require_user_id
def initialize_accounts() -> object:
    """Initialize default chart of accounts for user (simulated)"""
    try:
        existing_accounts = Account.find_all("user_id = ?", (request.user_id,))
        if len(existing_accounts) > 0:
            return (jsonify({"error": "User already has accounts initialized"}), 409)
        return (
            jsonify({"message": "Default chart of accounts created successfully"}),
            201,
        )
    except Exception as e:
        return (
            jsonify({"error": "Failed to initialize accounts", "details": str(e)}),
            500,
        )


@ledger_bp.route("/health", methods=["GET"])
def health_check() -> object:
    """Health check endpoint"""
    return (
        jsonify(
            {
                "status": "healthy",
                "service": "ledger-service",
                "timestamp": datetime.utcnow().isoformat(),
            }
        ),
        200,
    )
