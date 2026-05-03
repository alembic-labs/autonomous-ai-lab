"""APScheduler wiring for the distillation loop."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..config import settings
from ..logging_setup import get_logger
from .cycle import run_distillation_cycle

log = get_logger(__name__)

JOB_ID = "alembic-distillation"


async def _job_wrapper() -> None:
    """Single safe entry point so APScheduler never sees an unhandled exception."""
    try:
        await run_distillation_cycle()
    except Exception:  # noqa: BLE001
        log.exception("alembic.scheduler.cycle_unhandled")


def start_scheduler() -> AsyncIOScheduler:
    """Create and start the AsyncIOScheduler.

    The first run is delayed by 60 seconds so the API can warm up and respond
    to ``/api/health`` immediately on boot.
    """

    scheduler = AsyncIOScheduler(timezone="UTC")
    interval = max(int(settings.DISTILLATION_INTERVAL_MINUTES), 1)
    first_run = datetime.now(timezone.utc) + timedelta(seconds=60)
    scheduler.add_job(
        _job_wrapper,
        trigger=IntervalTrigger(minutes=interval),
        id=JOB_ID,
        name="distillation",
        next_run_time=first_run,
        misfire_grace_time=60,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    log.info(
        "alembic.scheduler.started",
        interval_minutes=interval,
        first_run=first_run.isoformat(),
    )
    return scheduler


def stop_scheduler(scheduler: AsyncIOScheduler | None) -> None:
    """Stop the scheduler if it's running."""
    if scheduler is None:
        return
    if scheduler.running:
        scheduler.shutdown(wait=False)
        log.info("alembic.scheduler.stopped")
