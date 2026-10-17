import threading
import time
from enum import Enum
from functools import wraps
from typing import Callable, Optional

try:
    from ..config.infrastructure import InfrastructureConfig
except ImportError:
    try:
        from config.infrastructure import InfrastructureConfig
    except ImportError:

        class InfrastructureConfig:
            CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
            CIRCUIT_BREAKER_RECOVERY_TIMEOUT = 60


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:

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

    def call(self, func: Callable, *args: object, **kwargs: object) -> object:
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
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout

    def _on_success(self) -> object:
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def _on_failure(self) -> object:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN


def circuit_breaker(
    failure_threshold: Optional[int] = None, recovery_timeout: Optional[int] = None
) -> object:

    def decorator(func):
        breaker = CircuitBreaker(failure_threshold, recovery_timeout)

        @wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)

        return wrapper

    return decorator
