"""Structured logging configuration.

We use ``structlog`` so that each agent run, every API request and every
external HTTP call emits machine-parseable JSON in production — and a
human-readable console renderer in development.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from .config import settings


def _stdlib_level() -> int:
    return getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)


def configure_logging() -> None:
    """Configure both stdlib logging and structlog. Idempotent."""

    logging.basicConfig(
        level=_stdlib_level(),
        format="%(message)s",
        stream=sys.stdout,
        force=True,
    )
    # Reduce noisy third-party loggers.
    for name in ("httpx", "httpcore", "asyncio", "apscheduler"):
        logging.getLogger(name).setLevel(logging.WARNING)

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if settings.is_production:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(_stdlib_level()),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Convenience accessor used across the codebase."""
    return structlog.get_logger(name)  # type: ignore[return-value]
