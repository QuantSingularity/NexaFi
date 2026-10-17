import math
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from ai_models.core.errors import ValidationError


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def require_dict(value: Any, name: str) -> Dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationError(f"{name} must be an object")
    return value


def as_float(
    value: Any,
    name: str,
    low: Optional[float] = None,
    high: Optional[float] = None,
    default: Optional[float] = None,
) -> Optional[float]:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        raise ValidationError(f"{name} must be a number")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{name} must be a number")
    if not math.isfinite(number):
        raise ValidationError(f"{name} must be finite")
    if low is not None and number < low:
        raise ValidationError(f"{name} must be at least {low}")
    if high is not None and number > high:
        raise ValidationError(f"{name} must be at most {high}")
    return number


def as_int(
    value: Any,
    name: str,
    low: Optional[int] = None,
    high: Optional[int] = None,
    default: Optional[int] = None,
) -> Optional[int]:
    number = as_float(
        value, name, low, high, None if default is None else float(default)
    )
    return None if number is None else int(number)


def as_float_list(value: Any, name: str, max_length: int = 5000) -> List[float]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise ValidationError(f"{name} must be a list of numbers")
    if len(value) > max_length:
        raise ValidationError(f"{name} may contain at most {max_length} values")
    return [as_float(item, f"{name}[{i}]") for i, item in enumerate(value)]


def parse_timestamp(value: Any, name: str = "timestamp") -> datetime:
    if isinstance(value, datetime):
        stamp = value
    elif isinstance(value, date):
        stamp = datetime(value.year, value.month, value.day)
    elif isinstance(value, str) and value.strip():
        try:
            stamp = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            raise ValidationError(f"{name} must be an ISO 8601 timestamp")
    else:
        raise ValidationError(f"{name} must be an ISO 8601 timestamp")
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def try_parse_timestamp(value: Any) -> Optional[datetime]:
    try:
        return parse_timestamp(value)
    except ValidationError:
        return None
