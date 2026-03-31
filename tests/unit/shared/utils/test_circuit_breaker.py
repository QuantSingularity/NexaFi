import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from NexaFi.backend.shared.config.infrastructure import InfrastructureConfig


class CircuitBreakerOpenException(Exception):
    """Custom exception raised when attempting a call on an open circuit."""


CircuitState = MagicMock()
CircuitState.CLOSED = "CLOSED"
CircuitState.OPEN = "OPEN"
CircuitState.HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:

    def __init__(
        self, failure_threshold: Any = None, recovery_timeout: Any = None
    ) -> None:
        self.failure_threshold = (
            failure_threshold or InfrastructureConfig.CIRCUIT_BREAKER_FAILURE_THRESHOLD
        )
        self.recovery_timeout = (
            recovery_timeout or InfrastructureConfig.CIRCUIT_BREAKER_RECOVERY_TIMEOUT
        )
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None

    def call(self, func: Any, *args, **kwargs) -> Any:
        if self.state == CircuitState.OPEN:
            if time.time() > self.last_failure_time + self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerOpenException("Circuit breaker is OPEN")
        if self.state == CircuitState.HALF_OPEN:
            try:
                result = func(*args, **kwargs)
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                return result
            except Exception:
                self.state = CircuitState.OPEN
                self.last_failure_time = time.time()
                raise
        try:
            result = func(*args, **kwargs)
            return result
        except Exception:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                self.last_failure_time = time.time()
            raise


def circuit_breaker(failure_threshold: Any, recovery_timeout: Any) -> Any:

    def decorator(func):
        breaker = CircuitBreaker(failure_threshold, recovery_timeout)

        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)

        wrapper.breaker = breaker
        return wrapper

    return decorator


@pytest.fixture
def default_circuit_breaker() -> Any:
    with patch.object(
        InfrastructureConfig, "CIRCUIT_BREAKER_FAILURE_THRESHOLD", 3
    ), patch.object(InfrastructureConfig, "CIRCUIT_BREAKER_RECOVERY_TIMEOUT", 5):
        yield CircuitBreaker()


class TestCircuitBreaker:

    def test_initial_state(self, default_circuit_breaker: Any) -> Any:
        assert default_circuit_breaker.state == CircuitState.CLOSED
        assert default_circuit_breaker.failure_count == 0
        assert default_circuit_breaker.last_failure_time is None

    def test_closed_to_open_transition(self, default_circuit_breaker: Any) -> Any:
        mock_func = MagicMock(side_effect=Exception("Test Exception"))
        for _ in range(default_circuit_breaker.failure_threshold - 1):
            with pytest.raises(Exception):
                default_circuit_breaker.call(mock_func)
            assert default_circuit_breaker.state == CircuitState.CLOSED
        with pytest.raises(Exception):
            default_circuit_breaker.call(mock_func)
        assert default_circuit_breaker.state == CircuitState.OPEN
        assert default_circuit_breaker.last_failure_time is not None

    def test_open_to_half_open_transition(self, default_circuit_breaker: Any) -> Any:
        mock_func = MagicMock(side_effect=Exception("Test Exception"))
        for _ in range(default_circuit_breaker.failure_threshold):
            with pytest.raises(Exception):
                default_circuit_breaker.call(mock_func)
        assert default_circuit_breaker.state == CircuitState.OPEN
        with patch(
            "time.time",
            return_value=time.time() + default_circuit_breaker.recovery_timeout + 1,
        ):
            with pytest.raises(Exception):
                default_circuit_breaker.call(mock_func)
            assert default_circuit_breaker.state == CircuitState.HALF_OPEN

    def test_half_open_to_closed_on_success(self, default_circuit_breaker: Any) -> Any:
        mock_func_fail = MagicMock(side_effect=Exception("Test Exception"))
        mock_func_success = MagicMock(return_value="Success")
        for _ in range(default_circuit_breaker.failure_threshold):
            with pytest.raises(Exception):
                default_circuit_breaker.call(mock_func_fail)
        with patch(
            "time.time",
            return_value=time.time() + default_circuit_breaker.recovery_timeout + 1,
        ):
            result = default_circuit_breaker.call(mock_func_success)
            assert result == "Success"
            assert default_circuit_breaker.state == CircuitState.CLOSED
            assert default_circuit_breaker.failure_count == 0

    def test_half_open_to_open_on_failure(self, default_circuit_breaker: Any) -> Any:
        mock_func_fail = MagicMock(side_effect=Exception("Test Exception"))
        for _ in range(default_circuit_breaker.failure_threshold):
            with pytest.raises(Exception):
                default_circuit_breaker.call(mock_func_fail)
        with patch(
            "time.time",
            return_value=time.time() + default_circuit_breaker.recovery_timeout + 1,
        ):
            with pytest.raises(Exception):
                default_circuit_breaker.call(mock_func_fail)
            assert default_circuit_breaker.state == CircuitState.OPEN

    def test_call_in_open_state_raises_circuit_breaker_exception(
        self, default_circuit_breaker: Any
    ) -> Any:
        mock_func = MagicMock(side_effect=Exception("Test Exception"))
        for _ in range(default_circuit_breaker.failure_threshold):
            with pytest.raises(Exception):
                default_circuit_breaker.call(mock_func)
        with pytest.raises(
            CircuitBreakerOpenException, match="Circuit breaker is OPEN"
        ):
            default_circuit_breaker.call(mock_func)
        mock_func.assert_not_called()


class TestCircuitBreakerDecorator:

    def test_decorator_closed_state(self) -> Any:

        @circuit_breaker(failure_threshold=1, recovery_timeout=1)
        def test_func():
            return "Success"

        result = test_func()
        assert result == "Success"
        assert test_func.breaker.state == CircuitState.CLOSED

    def test_decorator_open_state(self) -> Any:

        @circuit_breaker(failure_threshold=1, recovery_timeout=1)
        def test_func_fail():
            raise Exception("Decorator Test Exception")

        initial_time = time.time()
        with patch("time.time", return_value=initial_time):
            with pytest.raises(Exception):
                test_func_fail()
            assert test_func_fail.breaker.state == CircuitState.OPEN
        with patch("time.time", return_value=initial_time + 0.5):
            with pytest.raises(
                CircuitBreakerOpenException, match="Circuit breaker is OPEN"
            ):
                test_func_fail()

    def test_decorator_half_open_state_and_success(self) -> Any:
        call_tracker = [0]

        @circuit_breaker(failure_threshold=1, recovery_timeout=1)
        def test_func_half_open():
            call_tracker[0] += 1
            if call_tracker[0] <= 1:
                raise Exception("First Fail to Open")
            else:
                return "Success"

        initial_time = time.time()
        with patch("time.time", return_value=initial_time):
            with pytest.raises(Exception):
                test_func_half_open()
            assert test_func_half_open.breaker.state == CircuitState.OPEN
            assert call_tracker[0] == 1
        with patch("time.time", return_value=initial_time + 2):
            result = test_func_half_open()
            assert result == "Success"
            assert test_func_half_open.breaker.state == CircuitState.CLOSED
            assert call_tracker[0] == 2
