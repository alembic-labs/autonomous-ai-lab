"""/api/stats — aggregated lab statistics."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import AGENT_NAMES, LabStat
from ..db.session import get_db
from .schemas import LabStatsResponse

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _ensure_aware(value: datetime) -> datetime:
    """SQLite drops timezone info on round-trip; coerce to UTC if naive."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


@router.get("", response_model=LabStatsResponse)
@router.get("/", response_model=LabStatsResponse)
async def lab_stats(db: AsyncSession = Depends(get_db)) -> LabStatsResponse:
    """Return cached lab statistics for the home page."""

    row = await db.get(LabStat, 1)
    if row is None:
        raise HTTPException(status_code=503, detail="lab stats not initialised yet")

    started = _ensure_aware(row.lab_started_at)
    days_running = max(
        (datetime.now(timezone.utc) - started).days, 0
    )
    runs = row.total_chai1_runs or 0
    skipped = row.total_chai1_skipped or 0
    eligible = runs + skipped
    # Precompute the ratio so the frontend can render the badge unconditionally
    # without re-implementing divide-by-zero guards.
    ratio = round(runs / eligible, 4) if eligible else None
    # On-chain ratio mirrors the same shape: "X / eligible (Y%)". The
    # eligible denominator is "folds with a publishable verdict" — i.e.
    # total_folds minus pending and failed. A simple proxy is
    # ``refined + promising + discarded``.
    onchain_eligible = (
        (row.refined_count or 0)
        + (row.promising_count or 0)
        + (row.discarded_count or 0)
    )
    onchain_logged = row.total_onchain_logged or 0
    onchain_ratio = (
        round(onchain_logged / onchain_eligible, 4) if onchain_eligible else None
    )
    return LabStatsResponse(
        total_folds=row.total_folds,
        refined_count=row.refined_count,
        promising_count=row.promising_count,
        pending_count=row.pending_count,
        discarded_count=row.discarded_count,
        failed_count=row.failed_count,
        peptides_explored_count=row.peptides_explored_count,
        days_running=days_running,
        agents_active=len(AGENT_NAMES),
        total_tokens_used=row.total_tokens_used,
        total_cost_usd=row.total_cost_usd,
        avg_cycle_seconds=row.avg_cycle_seconds,
        total_chai1_runs=runs,
        total_chai1_skipped=skipped,
        chai1_eligible_folds=eligible,
        chai1_run_ratio=ratio,
        total_onchain_logged=onchain_logged,
        onchain_eligible_folds=onchain_eligible,
        onchain_logged_ratio=onchain_ratio,
        onchain_enabled=settings.solana_ready,
        onchain_network=settings.SOLANA_NETWORK,
    )
