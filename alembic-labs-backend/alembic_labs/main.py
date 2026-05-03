"""FastAPI application entry point.

Wired up incrementally as the build pack progresses:

- Prompt 1: minimal app + ``/api/health``.
- Prompt 2: lifespan with ``init_db`` + ``run_seed``.
- Prompt 5: scheduler start/stop in lifespan.
- Prompt 6: routers, CORS, request logging.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncIterator
from uuid import uuid4

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .api.routes_agents import router as agents_router
from .api.routes_folds import router as folds_router
from .api.routes_stats import router as stats_router
from .config import settings
from .db.seed import run_seed
from .db.session import dispose_engine, init_db
from .logging_setup import configure_logging, get_logger
from .orchestrator.scheduler import start_scheduler, stop_scheduler

configure_logging()
log = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Tag each request with a UUID and emit a structured log line.

    We deliberately log after the response so we can include status + duration.
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        request_id = uuid4().hex[:12]
        started = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.monotonic() - started) * 1000, 2)
            log.exception(
                "alembic.request.error",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
            )
            raise
        duration_ms = round((time.monotonic() - started) * 1000, 2)
        # Skip noisy health pings to keep logs readable.
        if request.url.path != "/api/health":
            log.info(
                "alembic.request",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=duration_ms,
            )
        response.headers["X-Request-ID"] = request_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan.

    Order on startup:
    1. ``init_db`` — create tables if missing (idempotent).
    2. ``run_seed`` — peptides registry, lab stats, agent status rows.
    3. ``start_scheduler`` — APScheduler job that runs the distillation cycle.

    On shutdown the scheduler is stopped before the DB pool is closed so that
    in-flight cycles can write a final status row.
    """

    log.info("alembic.startup", env=settings.APP_ENV)
    await init_db()
    await run_seed()
    scheduler: AsyncIOScheduler | None = None
    if settings.ENABLE_SCHEDULER:
        scheduler = start_scheduler()
    try:
        yield
    finally:
        stop_scheduler(scheduler)
        await dispose_engine()
        log.info("alembic.shutdown")


app = FastAPI(
    title="ALEMBIC LABS API",
    version="0.1.0",
    description=(
        "Backend for ALEMBIC LABS — an autonomous AI laboratory researching "
        "performance peptides. In silico hypothesis generation at scale, in the open."
    ),
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS — explicit origin list so browser clients only on the configured
# domains (frontend dev server + production hostname) can call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(folds_router)
app.include_router(agents_router)
app.include_router(stats_router)


@app.get("/api/health", tags=["health"])
async def health() -> dict[str, str]:
    """Liveness probe used by uptime monitors and CI."""
    return {"status": "ok", "lab": "ALEMBIC LABS"}
