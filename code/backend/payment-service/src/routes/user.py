import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import wraps
from typing import Optional

from flask import Blueprint, jsonify, request
from fraud_screening import (
    HISTORY_LIMIT,
    blocked_actions,
    fail_closed,
    history_payload,
    screen_transaction,
    screening_mode,
)
from models.user import (
    PaymentMethod,
    RecurringPayment,
    Transaction,
    Wallet,
    WalletBalanceHistory,
)

payment_bp = Blueprint("payment", __name__)


def require_user_id(f: object) -> object:

    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            return (jsonify({"error": "User ID is required in headers"}), 401)
        request.user_id = user_id
        return f(*args, **kwargs)

    return decorated_function


def calculate_fees(
    amount: Decimal, payment_method_type: str, processor_name: object = "default"
) -> Decimal:
    fee_structures = {
        "card": {"percentage": Decimal("0.029"), "fixed": Decimal("0.30")},
        "bank_account": {"percentage": Decimal("0.008"), "fixed": Decimal("0.00")},
        "digital_wallet": {"percentage": Decimal("0.025"), "fixed": Decimal("0.00")},
    }
    fee_structure = fee_structures.get(payment_method_type, fee_structures["card"])
    percentage_fee = amount * fee_structure["percentage"]
    total_fee = percentage_fee + fee_structure["fixed"]
    return total_fee.quantize(Decimal("0.01"))


def create_or_update_wallet(user_id: str, currency: object = "USD") -> Wallet:
    wallet = Wallet.find_one("user_id = ? AND currency = ?", (user_id, currency))
    if not wallet:
        wallet = Wallet(
            id=str(uuid.uuid4()),
            user_id=user_id,
            currency=currency,
            balance=0.0,
            available_balance=0.0,
            pending_balance=0.0,
            reserved_balance=0.0,
            is_active=True,
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )
        wallet.save()
    return wallet


def update_wallet_balance(
    wallet: Wallet,
    amount: Decimal,
    change_type: str,
    description: str,
    transaction_id: Optional[str] = None,
) -> object:
    amount_float = float(amount)
    balance_before = wallet.balance
    if change_type == "credit":
        wallet.balance += amount_float
        wallet.available_balance += amount_float
    elif change_type == "debit":
        wallet.balance -= amount_float
        wallet.available_balance -= amount_float
    elif change_type == "hold":
        wallet.available_balance -= amount_float
        wallet.reserved_balance += amount_float
    elif change_type == "release":
        wallet.available_balance += amount_float
        wallet.reserved_balance -= amount_float
    wallet.updated_at = datetime.utcnow().isoformat()
    wallet.save()
    history = WalletBalanceHistory(
        id=str(uuid.uuid4()),
        wallet_id=wallet.id,
        transaction_id=transaction_id,
        change_type=change_type,
        amount=amount_float,
        balance_before=balance_before,
        balance_after=wallet.balance,
        description=description,
        created_at=datetime.utcnow().isoformat(),
    )
    history.save()


@payment_bp.route("/payment-methods", methods=["GET"])
@require_user_id
def get_payment_methods() -> object:
    try:
        payment_methods = PaymentMethod.find_all(
            "user_id = ? AND is_active = 1 ORDER BY is_default DESC, created_at DESC",
            (request.user_id,),
        )
        return (
            jsonify(
                {
                    "payment_methods": [method.to_dict() for method in payment_methods],
                    "total": len(payment_methods),
                }
            ),
            200,
        )
    except Exception as e:
        return (
            jsonify({"error": "Failed to get payment methods", "details": str(e)}),
            500,
        )


@payment_bp.route("/payment-methods", methods=["POST"])
@require_user_id
def create_payment_method() -> object:
    try:
        data = request.get_json()
        required_fields = ["type", "provider", "details"]
        for field in required_fields:
            if not data.get(field):
                return (jsonify({"error": f"{field} is required"}), 400)
        valid_types = ["card", "bank_account", "digital_wallet"]
        if data["type"] not in valid_types:
            return (
                jsonify(
                    {
                        "error": f"Invalid payment method type. Must be one of: {valid_types}"
                    }
                ),
                400,
            )
        if data.get("is_default"):
            existing_defaults = PaymentMethod.find_all(
                "user_id = ? AND is_default = 1", (request.user_id,)
            )
            for method in existing_defaults:
                method.is_default = False
                method.save()
        payment_method = PaymentMethod(
            id=str(uuid.uuid4()),
            user_id=request.user_id,
            type=data["type"],
            provider=data["provider"],
            external_id=data.get("external_id"),
            details=data["details"],
            is_default=data.get("is_default", False),
            is_active=True,
            is_verified=data.get("is_verified", False),
            verification_status=data.get("verification_status", "pending"),
            expires_at=data.get("expires_at"),
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )
        payment_method.save()
        return (
            jsonify(
                {
                    "message": "Payment method created successfully",
                    "payment_method": payment_method.to_dict(),
                }
            ),
            201,
        )
    except Exception as e:
        return (
            jsonify({"error": "Failed to create payment method", "details": str(e)}),
            500,
        )


@payment_bp.route("/payment-methods/<method_id>", methods=["GET"])
@require_user_id
def get_payment_method(method_id: object) -> object:
    try:
        payment_method = PaymentMethod.find_one(
            "id = ? AND user_id = ?", (method_id, request.user_id)
        )
        if not payment_method:
            return (jsonify({"error": "Payment method not found"}), 404)
        return (jsonify({"payment_method": payment_method.to_dict()}), 200)
    except Exception as e:
        return (
            jsonify({"error": "Failed to get payment method", "details": str(e)}),
            500,
        )


@payment_bp.route("/payment-methods/<method_id>", methods=["PUT"])
@require_user_id
def update_payment_method(method_id: object) -> object:
    try:
        payment_method = PaymentMethod.find_one(
            "id = ? AND user_id = ?", (method_id, request.user_id)
        )
        if not payment_method:
            return (jsonify({"error": "Payment method not found"}), 404)
        data = request.get_json()
        updatable_fields = ["details", "is_default", "is_active", "expires_at"]
        for field in updatable_fields:
            if field in data:
                setattr(payment_method, field, data[field])
        if data.get("is_default"):
            existing_defaults = PaymentMethod.find_all(
                "user_id = ? AND is_default = 1 AND id != ?",
                (request.user_id, method_id),
            )
            for method in existing_defaults:
                method.is_default = False
                method.save()
        payment_method.updated_at = datetime.utcnow().isoformat()
        payment_method.save()
        return (
            jsonify(
                {
                    "message": "Payment method updated successfully",
                    "payment_method": payment_method.to_dict(),
                }
            ),
            200,
        )
    except Exception as e:
        return (
            jsonify({"error": "Failed to update payment method", "details": str(e)}),
            500,
        )


@payment_bp.route("/payment-methods/<method_id>", methods=["DELETE"])
@require_user_id
def delete_payment_method(method_id: object) -> object:
    try:
        payment_method = PaymentMethod.find_one(
            "id = ? AND user_id = ?", (method_id, request.user_id)
        )
        if not payment_method:
            return (jsonify({"error": "Payment method not found"}), 404)
        payment_method.is_active = False
        payment_method.updated_at = datetime.utcnow().isoformat()
        payment_method.save()
        return (jsonify({"message": "Payment method deleted successfully"}), 200)
    except Exception as e:
        return (
            jsonify({"error": "Failed to delete payment method", "details": str(e)}),
            500,
        )


@payment_bp.route("/transactions", methods=["GET"])
@require_user_id
def get_transactions() -> object:
    try:
        status = request.args.get("status")
        transaction_type = request.args.get("type")
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        where_clause = "user_id = ?"
        params = [request.user_id]
        if status:
            where_clause += " AND status = ?"
            params.append(status)
        if transaction_type:
            where_clause += " AND transaction_type = ?"
            params.append(transaction_type)
        if start_date:
            where_clause += " AND created_at >= ?"
            params.append(start_date)
        if end_date:
            where_clause += " AND created_at <= ?"
            params.append(end_date)
        try:
            per_page = max(1, min(int(request.args.get("per_page", 500)), 1000))
            page = max(1, int(request.args.get("page", 1)))
        except ValueError:
            return (jsonify({"error": "page and per_page must be integers"}), 400)
        total = Transaction.count(where_clause, tuple(params))
        transactions = Transaction.find_all(
            where_clause,
            tuple(params),
            order_by="created_at DESC",
            limit=per_page,
            offset=(page - 1) * per_page,
        )
        return (
            jsonify(
                {
                    "transactions": [
                        transaction.to_dict() for transaction in transactions
                    ],
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                }
            ),
            200,
        )
    except Exception as e:
        return (
            jsonify({"error": "Failed to get transactions", "details": str(e)}),
            500,
        )


@payment_bp.route("/transactions", methods=["POST"])
@require_user_id
def create_transaction() -> object:
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return (jsonify({"error": "A JSON object body is required"}), 400)
        required_fields = ["amount", "transaction_type"]
        for field in required_fields:
            if not data.get(field):
                return (jsonify({"error": f"{field} is required"}), 400)
        try:
            amount = Decimal(str(data["amount"]))
        except InvalidOperation:
            return (jsonify({"error": "amount must be a number"}), 400)
        if not amount.is_finite() or amount <= 0:
            return (jsonify({"error": "Amount must be greater than 0"}), 400)
        payment_method = None
        if data.get("payment_method_id"):
            payment_method = PaymentMethod.find_one(
                "id = ? AND user_id = ? AND is_active = 1",
                (data["payment_method_id"], request.user_id),
            )
            if not payment_method:
                return (jsonify({"error": "Invalid payment method"}), 400)
        fees = Decimal("0")
        if payment_method:
            fees = calculate_fees(amount, payment_method.type, payment_method.provider)
        net_amount = amount - fees
        risk = None
        if screening_mode() != "off":
            recent = Transaction.find_all(
                "user_id = ?",
                (request.user_id,),
                order_by="created_at DESC",
                limit=HISTORY_LIMIT,
            )
            risk = screen_transaction(
                request.user_id,
                {
                    "amount": float(amount),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "currency": data.get("currency", "USD"),
                    "merchant": data.get("reference") or data.get("description"),
                    "category": data["transaction_type"],
                },
                history_payload(recent),
            )
            blocked = (
                risk is not None
                and risk.get("available")
                and risk.get("recommended_action") in blocked_actions()
            )
            unavailable = risk is not None and not risk.get("available")
            if screening_mode() == "enforce" and (
                blocked or (unavailable and fail_closed())
            ):
                return (
                    jsonify(
                        {
                            "error": "Transaction declined by fraud screening",
                            "risk": risk,
                        }
                    ),
                    403,
                )
        metadata = data.get("metadata")
        if risk is not None:
            metadata = {
                **(metadata if isinstance(metadata, dict) else {}),
                "risk": risk,
            }
        transaction = Transaction(
            id=str(uuid.uuid4()),
            user_id=request.user_id,
            payment_method_id=data.get("payment_method_id"),
            transaction_type=data["transaction_type"],
            amount=float(amount),
            currency=data.get("currency", "USD"),
            description=data.get("description"),
            reference=data.get("reference"),
            status="pending",
            fees=float(fees),
            net_amount=float(net_amount),
            metadata=metadata,
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )
        if data["transaction_type"] == "payment":
            transaction.status = "completed"
            transaction.external_transaction_id = f"ext_{uuid.uuid4().hex[:12]}"
            transaction.processed_at = datetime.utcnow().isoformat()
            transaction.settled_at = datetime.utcnow().isoformat()
            wallet = create_or_update_wallet(request.user_id, transaction.currency)
            update_wallet_balance(
                wallet,
                net_amount,
                "credit",
                f"Payment received: {transaction.description}",
                transaction.id,
            )
        elif data["transaction_type"] == "withdrawal":
            wallet = create_or_update_wallet(request.user_id, transaction.currency)
            if wallet.available_balance < float(amount):
                return (jsonify({"error": "Insufficient balance"}), 400)
            transaction.status = "completed"
            transaction.external_transaction_id = f"ext_{uuid.uuid4().hex[:12]}"
            transaction.processed_at = datetime.utcnow().isoformat()
            transaction.settled_at = datetime.utcnow().isoformat()
            update_wallet_balance(
                wallet,
                amount,
                "debit",
                f"Withdrawal: {transaction.description}",
                transaction.id,
            )
        else:
            pass
        if payment_method:
            payment_method.last_used_at = datetime.utcnow().isoformat()
            payment_method.save()
        transaction.save()
        return (
            jsonify(
                {
                    "message": "Transaction created successfully",
                    "transaction": transaction.to_dict(),
                }
            ),
            201,
        )
    except Exception as e:
        return (
            jsonify({"error": "Failed to create transaction", "details": str(e)}),
            500,
        )


@payment_bp.route("/transactions/<transaction_id>", methods=["GET"])
@require_user_id
def get_transaction(transaction_id: object) -> object:
    try:
        transaction = Transaction.find_one(
            "id = ? AND user_id = ?", (transaction_id, request.user_id)
        )
        if not transaction:
            return (jsonify({"error": "Transaction not found"}), 404)
        return (jsonify({"transaction": transaction.to_dict()}), 200)
    except Exception as e:
        return (jsonify({"error": "Failed to get transaction", "details": str(e)}), 500)


@payment_bp.route("/wallets", methods=["GET"])
@require_user_id
def get_wallets() -> object:
    try:
        wallets = Wallet.find_all("user_id = ? AND is_active = 1", (request.user_id,))
        return (
            jsonify(
                {
                    "wallets": [wallet.to_dict() for wallet in wallets],
                    "total": len(wallets),
                }
            ),
            200,
        )
    except Exception as e:
        return (jsonify({"error": "Failed to get wallets", "details": str(e)}), 500)


@payment_bp.route("/wallets/<currency>", methods=["GET"])
@require_user_id
def get_wallet_by_currency(currency: object) -> object:
    try:
        wallet = Wallet.find_one(
            "user_id = ? AND currency = ? AND is_active = 1",
            (request.user_id, currency.upper()),
        )
        if not wallet:
            wallet = create_or_update_wallet(request.user_id, currency.upper())
        return (jsonify({"wallet": wallet.to_dict()}), 200)
    except Exception as e:
        return (jsonify({"error": "Failed to get wallet", "details": str(e)}), 500)


@payment_bp.route("/wallets/<currency>/history", methods=["GET"])
@require_user_id
def get_wallet_history(currency: object) -> object:
    try:
        wallet = Wallet.find_one(
            "user_id = ? AND currency = ? AND is_active = 1",
            (request.user_id, currency.upper()),
        )
        if not wallet:
            return (jsonify({"error": "Wallet not found"}), 404)
        history = WalletBalanceHistory.find_all(
            "wallet_id = ? ORDER BY created_at DESC", (wallet.id,)
        )
        return (
            jsonify(
                {
                    "wallet": wallet.to_dict(),
                    "history": [record.to_dict() for record in history],
                    "total": len(history),
                }
            ),
            200,
        )
    except Exception as e:
        return (
            jsonify({"error": "Failed to get wallet history", "details": str(e)}),
            500,
        )


@payment_bp.route("/recurring-payments", methods=["GET"])
@require_user_id
def get_recurring_payments() -> object:
    try:
        recurring_payments = RecurringPayment.find_all(
            "user_id = ? ORDER BY next_payment_date", (request.user_id,)
        )
        return (
            jsonify(
                {
                    "recurring_payments": [
                        payment.to_dict() for payment in recurring_payments
                    ],
                    "total": len(recurring_payments),
                }
            ),
            200,
        )
    except Exception as e:
        return (
            jsonify({"error": "Failed to get recurring payments", "details": str(e)}),
            500,
        )


@payment_bp.route("/recurring-payments", methods=["POST"])
@require_user_id
def create_recurring_payment() -> object:
    try:
        data = request.get_json()
        required_fields = ["payment_method_id", "amount", "frequency", "start_date"]
        for field in required_fields:
            if not data.get(field):
                return (jsonify({"error": f"{field} is required"}), 400)
        payment_method = PaymentMethod.find_one(
            "id = ? AND user_id = ? AND is_active = 1",
            (data["payment_method_id"], request.user_id),
        )
        if not payment_method:
            return (jsonify({"error": "Invalid payment method"}), 400)
        start_date = data["start_date"]
        next_payment_date = start_date
        recurring_payment = RecurringPayment(
            id=str(uuid.uuid4()),
            user_id=request.user_id,
            payment_method_id=data["payment_method_id"],
            amount=float(data["amount"]),
            currency=data.get("currency", "USD"),
            frequency=data["frequency"],
            description=data.get("description"),
            start_date=start_date,
            end_date=data.get("end_date"),
            next_payment_date=next_payment_date,
            total_payments=data.get("total_payments"),
            payments_made=0,
            status=data.get("status", "active"),
            metadata=data.get("metadata"),
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )
        recurring_payment.save()
        return (
            jsonify(
                {
                    "message": "Recurring payment created successfully",
                    "recurring_payment": recurring_payment.to_dict(),
                }
            ),
            201,
        )
    except Exception as e:
        return (
            jsonify({"error": "Failed to create recurring payment", "details": str(e)}),
            500,
        )


@payment_bp.route("/health", methods=["GET"])
def health_check() -> object:
    return (
        jsonify(
            {
                "status": "healthy",
                "service": "payment-service",
                "timestamp": datetime.utcnow().isoformat(),
            }
        ),
        200,
    )
