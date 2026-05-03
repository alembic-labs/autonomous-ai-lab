"""/api/agents — live agent status."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import AGENT_NAMES, AgentStatus
from ..db.session import get_db
from .schemas import AgentStatusResponse

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("/status", response_model=list[AgentStatusResponse])
async def agents_status(
    db: AsyncSession = Depends(get_db),
) -> list[AgentStatusResponse]:
    """Return a stable, ordered status row for each of the five agents."""

    stmt = select(AgentStatus)
    rows = {row.agent_name: row for row in (await db.execute(stmt)).scalars().all()}
    return [
        AgentStatusResponse.model_validate(rows[name])
        for name in AGENT_NAMES
        if name in rows
    ]
