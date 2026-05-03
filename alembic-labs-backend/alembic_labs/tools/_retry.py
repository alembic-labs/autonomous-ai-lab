"""Async retry decorator for transient HTTP failures.

External services (BioLM, ChEMBL, UniProt, PubMed, Europe PMC) all have
intermittent 5xx and timeout patterns. Without retries, a single bad minute
silently degrades the data on a fold. This decorator retries on:

- ``httpx.TimeoutException``        (connection/read/write timeouts)
- ``httpx.HTTPStatusError`` 5xx     (server errors)
- ``httpx.TransportError``          (network/DNS errors)

It deliberately does **not** retry on:

- 4xx                               (a 400 won't get better with another shot)
- ``json.JSONDecodeError``          (the upstream is producing garbage)

Backoff is exponential: ``backoff_base ** attempt`` seconds, capped to keep
agent latency bounded.
"""

from __future__ import annotations

import asyncio
from functools import wraps
from typing import Any, Awaitable, Callable, TypeVar

import httpx

from ..logging_setup import get_logger

T = TypeVar("T")

log = get_logger(__name__)


def _is_5xx(err: BaseException) -> bool:
    if isinstance(err, httpx.HTTPStatusError) and err.response is not None:
        return 500 <= err.response.status_code < 600
    return False


def _retryable(err: BaseException) -> bool:
    if isinstance(err, httpx.TimeoutException):
        return True
    if isinstance(err, httpx.TransportError) and not isinstance(
        err, httpx.HTTPStatusError
    ):
        return True
    if _is_5xx(err):
        return True
    return False


def with_retry(
    *,
    max_attempts: int = 3,
    backoff_base: float = 2.0,
    max_backoff_seconds: float = 8.0,
    name: str | None = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorate an async function so transient HTTP failures get retried."""

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        label = name or func.__qualname__

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exc: BaseException | None = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except (
                    httpx.TimeoutException,
                    httpx.TransportError,
                    httpx.HTTPStatusError,
                ) as err:
                    last_exc = err
                    if not _retryable(err) or attempt == max_attempts - 1:
                        raise
                    delay = min(backoff_base ** attempt, max_backoff_seconds)
                    log.warning(
                        "alembic.retry.transient",
                        target=label,
                        attempt=attempt + 1,
                        max_attempts=max_attempts,
                        delay_seconds=round(delay, 2),
                        error=str(err)[:160],
                    )
                    await asyncio.sleep(delay)
            assert last_exc is not None
            raise last_exc

        return wrapper

    return decorator
