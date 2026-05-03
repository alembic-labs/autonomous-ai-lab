"""Helpers for the curated KnownPeptide registry."""

from __future__ import annotations

import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import KnownPeptide


async def get_random_peptide(
    db: AsyncSession,
    exclude_recent_ids: list[int] | None = None,
) -> KnownPeptide | None:
    """Pick a random peptide that isn't in the recent-folds exclusion list."""

    stmt = select(KnownPeptide)
    if exclude_recent_ids:
        stmt = stmt.where(KnownPeptide.id.notin_(exclude_recent_ids))
    rows = (await db.execute(stmt)).scalars().all()
    if not rows:
        # Fall back to all peptides if the exclusion list eliminates everything.
        rows = (await db.execute(select(KnownPeptide))).scalars().all()
    if not rows:
        return None
    return random.choice(rows)


async def get_peptide_by_name(
    db: AsyncSession, name: str
) -> KnownPeptide | None:
    """Lookup by exact or aliased name (case-insensitive)."""

    needle = name.strip()
    if not needle:
        return None
    stmt = select(KnownPeptide).where(KnownPeptide.name.ilike(needle))
    found = (await db.execute(stmt)).scalars().first()
    if found:
        return found
    # Try an aliases LIKE match — aliases is a free-text comma-separated field.
    stmt = select(KnownPeptide).where(KnownPeptide.aliases.ilike(f"%{needle}%"))
    return (await db.execute(stmt)).scalars().first()


async def get_peptides_by_class(
    db: AsyncSession, peptide_class: str
) -> list[KnownPeptide]:
    """All peptides in a given class."""

    stmt = select(KnownPeptide).where(KnownPeptide.peptide_class == peptide_class.upper())
    return list((await db.execute(stmt)).scalars().all())
