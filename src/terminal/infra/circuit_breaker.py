"""Async circuit breaker for external API resilience.

Three states:
- CLOSED: Normal operation, calls go through.
- OPEN: Too many failures, calls are short-circuited.
- HALF_OPEN: Testing recovery, limited calls allowed.
"""

import asyncio
import logging
import time
from enum import StrEnum
from typing import TypeVar, Callable, Any

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a call is attempted while the circuit is open."""

    def __init__(self, name: str, open_since: float):
        self.name = name
        self.open_since = open_since
        super().__init__(f"Circuit '{name}' is OPEN (since {open_since:.0f}s ago)")


class CircuitBreaker:
    """Async circuit breaker wrapping any awaitable callable.

    Usage::

        breaker = CircuitBreaker("scanner", failure_threshold=5, recovery_timeout=30.0)
        result = await breaker.call(scanner.fetch_ohlcv)
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                return CircuitState.HALF_OPEN
        return self._state

    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> T:
        """Execute ``func`` through the circuit breaker."""
        async with self._lock:
            current_state = self.state

            if current_state == CircuitState.OPEN:
                raise CircuitOpenError(
                    self.name, time.monotonic() - self._last_failure_time
                )

            if current_state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitOpenError(
                        self.name, time.monotonic() - self._last_failure_time
                    )
                self._half_open_calls += 1

        try:
            result = await func(*args, **kwargs)
        except Exception as exc:
            await self._on_failure(exc)
            raise
        else:
            await self._on_success()
            return result

    async def _on_success(self) -> None:
        async with self._lock:
            if self._state in (CircuitState.HALF_OPEN, CircuitState.CLOSED):
                if self._state == CircuitState.HALF_OPEN:
                    logger.info(
                        "Circuit '%s' recovered — transitioning to CLOSED", self.name
                    )
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._half_open_calls = 0

    async def _on_failure(self, exc: Exception) -> None:
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._half_open_calls = 0
                logger.warning(
                    "Circuit '%s' re-opened after half-open failure: %s",
                    self.name,
                    exc,
                )
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit '%s' opened after %d failures: %s",
                    self.name,
                    self._failure_count,
                    exc,
                )


async def retry_with_backoff(
    func: Callable[..., Any],
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    retryable: Callable[[Exception], bool] | None = None,
    **kwargs: Any,
) -> Any:
    """Retry an async callable with exponential backoff.

    Args:
        func: Async callable to retry.
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay cap in seconds.
        retryable: Optional predicate; if it returns False the exception is re-raised immediately.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if retryable and not retryable(exc):
                raise
            if attempt == max_retries:
                raise
            delay = min(base_delay * (2**attempt), max_delay)
            logger.warning(
                "Retry %d/%d after %.1fs for %s: %s",
                attempt + 1,
                max_retries,
                delay,
                func.__qualname__ if hasattr(func, "__qualname__") else str(func),
                exc,
            )
            await asyncio.sleep(delay)

    raise last_exc  # type: ignore[misc]
