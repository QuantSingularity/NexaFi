"""
Circuit breaker pattern implementation for NexaFi services
"""

import threading
import time
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional

# Support both package-relative import (when used inside the backend package)
# and direct/standalone import (e.g. when the shared/ directory is on sys.path).
try:
    from ..config.infrastructure import InfrastructureConfig
except ImportError:
    try:
        from config.infrastructure import InfrastructureConfig
    except ImportError:
        # Fallback: define minimal defaults so the module is always importable
        class InfrastructureConfig:  # type: ignore[no-redef]
            CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
            CIRCUIT_BREAKER_RECOVERY_TIMEOUT = 60


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker implementation"""

    def __init__(
        self,
        failure_threshold: Optional[int] = None,
        recovery_timeout: Optional[int] = None,
    ) -> None:
        self.failure_threshold = (
            failure_threshold or InfrastructureConfig.CIRCUIT_BREAKER_FAILURE_THRESHOLD
        )
        self.recovery_timeout = (
            recovery_timeout or InfrastructureConfig.CIRCUIT_BREAKER_RECOVERY_TIMEOUT
        )
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self.lock = threading.Lock()

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        with self.lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                else:
                    raise Exception("Circuit breaker is OPEN")
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except Exception as e:
                self._on_failure()
                raise e

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout

    def _on_success(self) -> Any:
        """Handle successful call"""
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def _on_failure(self) -> Any:
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN


def circuit_breaker(
    failure_threshold: Optional[int] = None, recovery_timeout: Optional[int] = None
) -> Any:
    """Decorator for circuit breaker protection"""

    def decorator(func):
        breaker = CircuitBreaker(failure_threshold, recovery_timeout)

        @wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)

        return wrapper

    return decorator
