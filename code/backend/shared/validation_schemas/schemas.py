"""
Input validation and sanitization for NexaFi
Implements comprehensive validation for financial data
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict

import bleach
from marshmallow import Schema, ValidationError, fields, post_load, pre_load, validate


class FinancialValidators:
    """Custom validators for financial data"""

    @staticmethod
    def validate_currency_code(value: str) -> str:
        """Validate ISO 4217 currency code"""
        if not re.match("^[A-Z]{3}$", value):
            raise ValidationError("Currency code must be a 3-letter ISO 4217 code")
        return value

    @staticmethod
    def validate_amount(value: object) -> Decimal:
        """Validate monetary amount"""
        try:
            amount = Decimal(str(value))
            if amount.as_tuple().exponent < -2:
                raise ValidationError("Amount cannot have more than 2 decimal places")
            if amount < 0:
                raise ValidationError("Amount cannot be negative")
            if amount > Decimal("999999999.99"):
                raise ValidationError("Amount exceeds maximum allowed value")
            return amount
        except (InvalidOperation, TypeError):
            raise ValidationError("Invalid amount format")

    @staticmethod
    def validate_account_number(value: str) -> str:
        """Validate account number format"""
        clean_value = re.sub("[\\s-]", "", value)
        if not re.match("^[A-Z0-9]{8,20}$", clean_value):
            raise ValidationError("Account number must be 8-20 alphanumeric characters")
        return clean_value

    @staticmethod
    def validate_routing_number(value: str) -> str:
        """Validate bank routing number"""
        clean_value = re.sub("[\\s-]", "", value)
        if not re.match("^\\d{9}$", clean_value):
            raise ValidationError("Routing number must be 9 digits")
        return clean_value

    @staticmethod
    def validate_card_number(value: str) -> str:
        """Validate credit card number using Luhn algorithm"""
        clean_value = re.sub("[\\s-]", "", value)
        if not re.match("^\\d{13,19}$", clean_value):
            raise ValidationError("Card number must be 13-19 digits")

        def luhn_check(card_num):

            def digits_of(n):
                return [int(d) for d in str(n)]

            digits = digits_of(card_num)
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]
            checksum = sum(odd_digits)
            for d in even_digits:
                checksum += sum(digits_of(d * 2))
            return checksum % 10 == 0

        if not luhn_check(clean_value):
            raise ValidationError("Invalid card number")
        return clean_value

    @staticmethod
    def validate_email(value: str) -> str:
        """Comprehensive email validation"""
        email_regex = "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
        if not re.match(email_regex, value):
            raise ValidationError("Invalid email format")
        return value.lower()

    @staticmethod
    def validate_phone(value: str) -> str:
        """Validate phone number"""
        clean_value = re.sub("[\\s\\-\\(\\)\\+]", "", value)
        if not re.match("^\\d{10,15}$", clean_value):
            raise ValidationError("Phone number must be 10-15 digits")
        return clean_value


class SanitizationMixin:
    """Mixin for input sanitization"""

    @pre_load
    def sanitize_strings(self, data: object, **kwargs) -> object:
        """Sanitize string inputs"""
        if isinstance(data, dict):
            sanitized: Dict[str, Any] = {}
            for key, value in data.items():
                if isinstance(value, str):
                    sanitized[key] = bleach.clean(value.strip(), tags=[], strip=True)
                else:
                    sanitized[key] = value
            return sanitized
        return data


class UserRegistrationSchema(SanitizationMixin, Schema):
    email = fields.Email(required=True, validate=FinancialValidators.validate_email)
    password = fields.Str(required=True, validate=validate.Length(min=8, max=128))
    first_name = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    last_name = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    phone = fields.Str(required=False, validate=FinancialValidators.validate_phone)
    company_name = fields.Str(required=False, validate=validate.Length(max=100))


class UserLoginSchema(SanitizationMixin, Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True)


class UserUpdateSchema(SanitizationMixin, Schema):
    first_name = fields.Str(required=False, validate=validate.Length(min=1, max=50))
    last_name = fields.Str(required=False, validate=validate.Length(min=1, max=50))
    phone = fields.Str(required=False, validate=FinancialValidators.validate_phone)
    company_name = fields.Str(required=False, validate=validate.Length(max=100))


class AccountSchema(SanitizationMixin, Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    account_type = fields.Str(
        required=True,
        validate=validate.OneOf(["asset", "liability", "equity", "revenue", "expense"]),
    )
    account_number = fields.Str(
        required=False, validate=FinancialValidators.validate_account_number
    )
    description = fields.Str(required=False, validate=validate.Length(max=500))
    parent_account_id = fields.Int(required=False)


class TransactionSchema(SanitizationMixin, Schema):
    amount = fields.Raw(required=True, validate=FinancialValidators.validate_amount)
    currency = fields.Str(
        required=True, validate=FinancialValidators.validate_currency_code
    )
    description = fields.Str(required=True, validate=validate.Length(min=1, max=500))
    reference_number = fields.Str(required=False, validate=validate.Length(max=50))

    @post_load
    def convert_amount(self, data: object, **kwargs) -> object:
        data["amount"] = Decimal(str(data["amount"]))
        return data


class JournalEntrySchema(SanitizationMixin, Schema):
    description = fields.Str(required=True, validate=validate.Length(min=1, max=500))
    reference_number = fields.Str(required=False, validate=validate.Length(max=50))
    entry_date = fields.DateTime(required=False)


class JournalEntryLineSchema(SanitizationMixin, Schema):
    account_id = fields.Int(required=True)
    debit_amount = fields.Raw(
        required=False, validate=FinancialValidators.validate_amount
    )
    credit_amount = fields.Raw(
        required=False, validate=FinancialValidators.validate_amount
    )
    description = fields.Str(required=False, validate=validate.Length(max=500))

    @post_load
    def convert_amounts(self, data: object, **kwargs) -> object:
        if "debit_amount" in data and data["debit_amount"] is not None:
            data["debit_amount"] = Decimal(str(data["debit_amount"]))
        if "credit_amount" in data and data["credit_amount"] is not None:
            data["credit_amount"] = Decimal(str(data["credit_amount"]))
        return data


class PaymentMethodSchema(SanitizationMixin, Schema):
    method_type = fields.Str(
        required=True,
        validate=validate.OneOf(
            ["credit_card", "debit_card", "bank_account", "digital_wallet"]
        ),
    )
    is_default = fields.Bool(required=False, load_default=False)


class CreditCardSchema(PaymentMethodSchema):
    card_number = fields.Str(
        required=True, validate=FinancialValidators.validate_card_number
    )
    expiry_month = fields.Int(required=True, validate=validate.Range(min=1, max=12))
    expiry_year = fields.Int(required=True, validate=validate.Range(min=2024, max=2050))
    cardholder_name = fields.Str(
        required=True, validate=validate.Length(min=1, max=100)
    )
    cvv = fields.Str(required=True, validate=validate.Regexp("^\\d{3,4}$"))


class BankAccountSchema(PaymentMethodSchema):
    account_number = fields.Str(
        required=True, validate=FinancialValidators.validate_account_number
    )
    routing_number = fields.Str(
        required=True, validate=FinancialValidators.validate_routing_number
    )
    account_holder_name = fields.Str(
        required=True, validate=validate.Length(min=1, max=100)
    )
    account_type = fields.Str(
        required=True, validate=validate.OneOf(["checking", "savings"])
    )


class PredictionRequestSchema(SanitizationMixin, Schema):
    model_type = fields.Str(
        required=True,
        validate=validate.OneOf(
            ["cash_flow", "credit_score", "fraud_detection", "market_analysis"]
        ),
    )
    input_data = fields.Dict(required=True)
    prediction_horizon = fields.Int(
        required=False, validate=validate.Range(min=1, max=365)
    )


def validate_request_data(schema_class: type, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate request data using specified schema"""
    schema = schema_class()
    try:
        return schema.load(data)
    except ValidationError as e:
        raise ValidationError(f"Validation failed: {e.messages}")


def validate_json_request(schema_class: object) -> object:
    """Decorator for validating JSON request data"""

    def decorator(f):
        from functools import wraps

        from flask import jsonify, request

        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                if not request.is_json:
                    return (
                        jsonify({"error": "Content-Type must be application/json"}),
                        400,
                    )
                data = request.get_json()
                if data is None:
                    return (jsonify({"error": "Invalid JSON data"}), 400)
                validated_data = validate_request_data(schema_class, data)
                request.validated_data = validated_data
                return f(*args, **kwargs)
            except ValidationError as e:
                return (jsonify({"error": "Validation failed", "details": str(e)}), 400)
            except Exception:
                return (jsonify({"error": "Internal validation error"}), 500)

        return decorated_function

    return decorator
