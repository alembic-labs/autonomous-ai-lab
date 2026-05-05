"""Helpers for the curated KnownPeptide registry."""

from __future__ import annotations

import random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import KnownPeptide

# Local alias for clarity at the call site; keeps the column expression typed.
func_lower = func.lower


async def get_random_peptide(
    db: AsyncSession,
    exclude_recent_ids: list[int] | None = None,
    blocked_names: list[str] | None = None,
) -> KnownPeptide | None:
    """Pick a random peptide that isn't in the recent-folds exclusion list.

    ``blocked_names`` (case-insensitive, exact match) is the AVOID list
    surfaced by the Researcher's cross-fold memory — peptides with 3+
    consecutive DISCARDED folds and no REFINED. We strip them out at the
    DB level so the random pick never even sees them.
    """

    stmt = select(KnownPeptide)
    if exclude_recent_ids:
        stmt = stmt.where(KnownPeptide.id.notin_(exclude_recent_ids))
    if blocked_names:
        # Case-insensitive exclusion — KnownPeptide.name and the verdict
        # rows on Fold.peptide_name are normally identical strings, but
        # belt-and-braces for the migration window where capitalisation
        # might drift.
        lowered = {n.strip().lower() for n in blocked_names if n}
        if lowered:
            stmt = stmt.where(func_lower(KnownPeptide.name).notin_(list(lowered)))
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
