"""Idempotent database seeding.

Runs at startup. Inserts ``KnownPeptide`` rows from ``data/peptides_seed.json``
when the table is empty, ensures one ``LabStat`` row exists, and creates the
five ``AgentStatus`` rows in ``IDLE`` state if they don't already exist.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..logging_setup import get_logger
from .models import AGENT_NAMES, AgentStatus, KnownPeptide, LabStat
from .session import SessionLocal

log = get_logger(__name__)

SEED_FILE = Path(__file__).resolve().parent.parent / "data" / "peptides_seed.json"


async def _seed_peptides(session: AsyncSession) -> int:
    """Insert KnownPeptide rows when the table is empty."""

    existing = (await session.execute(select(KnownPeptide.id).limit(1))).first()
    if existing is not None:
        return 0

    if not SEED_FILE.exists():
        log.warning("alembic.seed.peptides.missing_file", path=str(SEED_FILE))
        return 0

    try:
        raw = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:  # pragma: no cover - defensive
        log.error("alembic.seed.peptides.bad_json", error=str(err))
        return 0

    inserted = 0
    for entry in raw:
        peptide = KnownPeptide(
            name=entry["name"],
            aliases=entry.get("aliases"),
            sequence=entry["sequence"],
            length=int(entry.get("length") or len(entry["sequence"])),
            peptide_class=entry["peptide_class"],
            known_targets=json.dumps(entry.get("known_targets", [])),
            canonical_targets=json.dumps(entry.get("canonical_targets", [])),
            mechanism_brief=entry.get("mechanism_brief", ""),
            biohacker_use=entry.get("biohacker_use", ""),
            references=json.dumps(entry.get("references", [])),
        )
        session.add(peptide)
        inserted += 1
    return inserted


async def _refresh_canonical_targets(session: AsyncSession) -> int:
    """Update canonical_targets on existing peptides where it's still empty.

    Lets us roll out the structured-target field to a DB that was seeded
    before the feature existed (e.g. existing prod) without nuking history.
    """

    if not SEED_FILE.exists():
        return 0
    try:
        raw = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:  # pragma: no cover - defensive
        return 0

    updated = 0
    for entry in raw:
        targets = entry.get("canonical_targets")
        if not targets:
            continue
        existing = (
            await session.execute(
                select(KnownPeptide).where(KnownPeptide.name == entry["name"])
            )
        ).scalars().first()
        if existing is None:
            continue
        try:
            current = json.loads(existing.canonical_targets or "[]")
        except json.JSONDecodeError:
            current = []
        if current:
            continue  # don't overwrite manual edits
        existing.canonical_targets = json.dumps(targets)
        updated += 1
    return updated


async def _seed_agent_status(session: AsyncSession) -> int:
    """Ensure five AgentStatus rows exist (one per agent)."""

    existing = {
        row[0]
        for row in (await session.execute(select(AgentStatus.agent_name))).all()
    }
    inserted = 0
    for name in AGENT_NAMES:
        if name in existing:
            continue
        session.add(AgentStatus(agent_name=name, status="IDLE"))
        inserted += 1
    return inserted


async def _seed_lab_stats(session: AsyncSession) -> bool:
    """Ensure the singleton LabStat row (id=1) exists."""

    found = await session.get(LabStat, 1)
    if found is not None:
        return False
    session.add(LabStat(id=1))
    return True


async def run_seed() -> None:
    """Seed the database. Safe to run repeatedly."""

    async with SessionLocal() as session:
        peptides_added = await _seed_peptides(session)
        canonical_updated = await _refresh_canonical_targets(session)
        agents_added = await _seed_agent_status(session)
        lab_added = await _seed_lab_stats(session)
        await session.commit()

    log.info(
        "alembic.seed.done",
        peptides_added=peptides_added,
        canonical_targets_updated=canonical_updated,
        agents_added=agents_added,
        lab_stats_created=lab_added,
    )
