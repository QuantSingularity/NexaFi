from typing import Any, Dict, Optional


class MLError(Exception):
    status_code = 500
    code = "ML_ERROR"

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"error": self.message, "code": self.code}
        if self.details:
            payload["details"] = self.details
        return payload


class ValidationError(MLError):
    status_code = 400
    code = "VALIDATION_ERROR"


class AuthenticationError(MLError):
    status_code = 401
    code = "AUTHENTICATION_FAILED"


class NotFoundError(MLError):
    status_code = 404
    code = "NOT_FOUND"


class InsufficientDataError(MLError):
    status_code = 422
    code = "INSUFFICIENT_DATA"


class DependencyError(MLError):
    status_code = 502
    code = "UPSTREAM_ERROR"
