"""
Tests for shared validation schemas and financial validators
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from marshmallow import ValidationError
from shared.validation_schemas.schemas import (
    FinancialValidators,
    UserLoginSchema,
    UserRegistrationSchema,
    validate_request_data,
)


class TestFinancialValidators(unittest.TestCase):

    def test_valid_currency_code(self):
        self.assertEqual(FinancialValidators.validate_currency_code("USD"), "USD")
        self.assertEqual(FinancialValidators.validate_currency_code("EUR"), "EUR")
        self.assertEqual(FinancialValidators.validate_currency_code("GBP"), "GBP")

    def test_invalid_currency_code(self):
        with self.assertRaises(ValidationError):
            FinancialValidators.validate_currency_code("US")
        with self.assertRaises(ValidationError):
            FinancialValidators.validate_currency_code("USDX")
        with self.assertRaises(ValidationError):
            FinancialValidators.validate_currency_code("123")

    def test_valid_amount(self):
        from decimal import Decimal

        result = FinancialValidators.validate_amount("100.50")
        self.assertEqual(result, Decimal("100.50"))

    def test_negative_amount_raises(self):
        with self.assertRaises(ValidationError):
            FinancialValidators.validate_amount("-10.00")

    def test_too_many_decimal_places(self):
        with self.assertRaises(ValidationError):
            FinancialValidators.validate_amount("10.123")

    def test_valid_email(self):
        self.assertEqual(
            FinancialValidators.validate_email("Test@Example.COM"), "test@example.com"
        )

    def test_invalid_email(self):
        with self.assertRaises(ValidationError):
            FinancialValidators.validate_email("not-an-email")
        with self.assertRaises(ValidationError):
            FinancialValidators.validate_email("missing@domain")

    def test_valid_phone(self):
        result = FinancialValidators.validate_phone("1234567890")
        self.assertEqual(result, "1234567890")

    def test_invalid_phone_too_short(self):
        with self.assertRaises(ValidationError):
            FinancialValidators.validate_phone("123")

    def test_valid_card_number_luhn(self):
        result = FinancialValidators.validate_card_number("4532015112830366")
        self.assertEqual(result, "4532015112830366")

    def test_invalid_card_number_luhn_fail(self):
        with self.assertRaises(ValidationError):
            FinancialValidators.validate_card_number("1234567890123456")

    def test_card_number_with_spaces(self):
        result = FinancialValidators.validate_card_number("4532 0151 1283 0366")
        self.assertEqual(result, "4532015112830366")

    def test_valid_account_number(self):
        result = FinancialValidators.validate_account_number("12345678")
        self.assertEqual(result, "12345678")

    def test_invalid_account_number_too_short(self):
        with self.assertRaises(ValidationError):
            FinancialValidators.validate_account_number("1234")

    def test_valid_routing_number(self):
        result = FinancialValidators.validate_routing_number("123456789")
        self.assertEqual(result, "123456789")

    def test_invalid_routing_number(self):
        with self.assertRaises(ValidationError):
            FinancialValidators.validate_routing_number("12345678")


class TestUserRegistrationSchema(unittest.TestCase):

    def test_valid_registration(self):
        data = {
            "email": "user@example.com",
            "password": "SecurePassword123!",
            "first_name": "John",
            "last_name": "Doe",
        }
        schema = UserRegistrationSchema()
        result = schema.load(data)
        self.assertEqual(result["email"], "user@example.com")

    def test_missing_required_fields(self):
        schema = UserRegistrationSchema()
        with self.assertRaises(Exception):
            schema.load({"email": "user@example.com"})

    def test_invalid_email(self):
        schema = UserRegistrationSchema()
        with self.assertRaises(Exception):
            schema.load(
                {
                    "email": "not-valid",
                    "password": "SecurePass123!",
                    "first_name": "John",
                    "last_name": "Doe",
                }
            )


class TestUserLoginSchema(unittest.TestCase):

    def test_valid_login(self):
        schema = UserLoginSchema()
        result = schema.load({"email": "user@example.com", "password": "pass"})
        self.assertEqual(result["email"], "user@example.com")

    def test_missing_password(self):
        schema = UserLoginSchema()
        with self.assertRaises(Exception):
            schema.load({"email": "user@example.com"})


class TestValidateRequestData(unittest.TestCase):

    def test_valid_data_returns_cleaned(self):
        result = validate_request_data(
            UserLoginSchema,
            {"email": "TEST@EXAMPLE.COM", "password": "mypass"},
        )
        self.assertIn("email", result)

    def test_invalid_data_raises(self):
        with self.assertRaises(Exception):
            validate_request_data(UserLoginSchema, {"email": "bad"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
