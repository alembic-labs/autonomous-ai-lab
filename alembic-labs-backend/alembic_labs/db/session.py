"""Async SQLAlchemy engine and session management."""

from __future__ import annotations

from typing import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..config import settings
from ..logging_setup import get_logger
from .models import Base

log = get_logger(__name__)


def _build_engine() -> AsyncEngine:
    """Build the engine with sensible defaults.

    NOTE: ``echo`` only in dev; production logs queries via structlog event hooks
    if needed. ``pool_pre_ping`` survives stale-connection drops on long-running
    workers, which is exactly our case (24/7 distillation loop).
    """

    url = settings.DATABASE_URL
    is_sqlite = url.startswith("sqlite")
    return create_async_engine(
        url,
        echo=False,
        pool_pre_ping=not is_sqlite,
        # SQLite (used in tests / offline dev) doesn't support pool tuning.
        future=True,
    )


engine: AsyncEngine = _build_engine()

# ``expire_on_commit=False`` lets us keep using ORM objects after commit, which
# matches the orchestrator's pattern of mutating the same Fold across agents.
SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# --- Lightweight ad-hoc migrations -------------------------------------------------
# We don't run Alembic yet; ``create_all`` adds new tables but cannot add new
# columns to existing tables. The list below holds idempotent ``ALTER TABLE``
# statements for each schema change shipped after the initial deploy. Each
# statement is wrapped so a missing-column error becomes a no-op on a fresh DB.
#
# Add new entries (NOT modify existing ones) whenever the model gains a new
# column on a pre-existing table. Postgres-specific syntax used because that's
# the production DB; SQLite (tests) still works because we recreate from
# ``create_all`` on each run.
_AD_HOC_MIGRATIONS: tuple[tuple[str, str], ...] = (
    # Researcher target IDs.
    ("folds", "ALTER TABLE folds ADD COLUMN IF NOT EXISTS target_chembl_id VARCHAR(20)"),
    (
        "folds",
        "ALTER TABLE folds ADD COLUMN IF NOT EXISTS target_gene_symbol VARCHAR(40)",
    ),
    # Boltz-2 affinity module.
    (
        "folds",
        "ALTER TABLE folds ADD COLUMN IF NOT EXISTS binding_probability FLOAT",
    ),
    ("folds", "ALTER TABLE folds ADD COLUMN IF NOT EXISTS binding_pic50 FLOAT"),
    # Communicator separation: keep tweet_draft, add executive_summary.
    ("folds", "ALTER TABLE folds ADD COLUMN IF NOT EXISTS executive_summary TEXT"),
    # Slug for SEO-friendly URLs.
    ("folds", "ALTER TABLE folds ADD COLUMN IF NOT EXISTS slug VARCHAR(180)"),
    (
        "folds",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_folds_slug ON folds (slug)",
    ),
    # KnownPeptide canonical_targets.
    (
        "known_peptides",
        "ALTER TABLE known_peptides ADD COLUMN IF NOT EXISTS canonical_targets TEXT NOT NULL DEFAULT '[]'",
    ),
    # Agent run tags (researcher memory / cross-fold metadata).
    ("agent_runs", "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS tags TEXT"),
    # LabStat: new verdict tiers + cost.
    (
        "lab_stats",
        "ALTER TABLE lab_stats ADD COLUMN IF NOT EXISTS promising_count INTEGER NOT NULL DEFAULT 0",
    ),
    (
        "lab_stats",
        "ALTER TABLE lab_stats ADD COLUMN IF NOT EXISTS failed_count INTEGER NOT NULL DEFAULT 0",
    ),
    (
        "lab_stats",
        "ALTER TABLE lab_stats ADD COLUMN IF NOT EXISTS total_cost_usd FLOAT NOT NULL DEFAULT 0.0",
    ),
    # Adaptive Chai-1 cross-validation gating (default NULL on existing rows
    # — backfill is optional, the UI treats NULL as "legacy fold").
    (
        "folds",
        "ALTER TABLE folds ADD COLUMN IF NOT EXISTS chai1_gated_decision VARCHAR(50)",
    ),
    (
        "lab_stats",
        "ALTER TABLE lab_stats ADD COLUMN IF NOT EXISTS total_chai1_runs INTEGER NOT NULL DEFAULT 0",
    ),
    (
        "lab_stats",
        "ALTER TABLE lab_stats ADD COLUMN IF NOT EXISTS total_chai1_skipped INTEGER NOT NULL DEFAULT 0",
    ),
    # Solana on-chain logging (SPL Memo) — explicit triple alongside the
    # legacy ``onchain_hash`` column. NULL on existing rows; populated only
    # after the Communicator finishes for new folds.
    (
        "folds",
        "ALTER TABLE folds ADD COLUMN IF NOT EXISTS onchain_signature VARCHAR(150)",
    ),
    (
        "folds",
        "ALTER TABLE folds ADD COLUMN IF NOT EXISTS onchain_data_hash VARCHAR(70)",
    ),
    (
        "folds",
        "ALTER TABLE folds ADD COLUMN IF NOT EXISTS onchain_logged_at TIMESTAMPTZ",
    ),
    (
        "lab_stats",
        "ALTER TABLE lab_stats ADD COLUMN IF NOT EXISTS total_onchain_logged INTEGER NOT NULL DEFAULT 0",
    ),
)


async def _apply_ad_hoc_migrations() -> None:
    """Run the idempotent ``ALTER TABLE`` list for the current schema version.

    Postgres only — SQLite (used in tests) skips because all columns come
    from ``create_all`` on the in-memory DB. Each statement is independent so
    a partial failure won't block the rest of startup.
    """
    if settings.DATABASE_URL.startswith("sqlite"):
        return
    async with engine.begin() as conn:
        for table, sql in _AD_HOC_MIGRATIONS:
            try:
                await conn.execute(text(sql))
            except Exception as err:  # noqa: BLE001 — migrations are best-effort
                log.warning(
                    "alembic.db.migration_skipped",
                    table=table,
                    error=str(err)[:240],
                )


async def init_db() -> None:
    """Create tables if they don't exist + apply ad-hoc migrations.

    For real production deployments we'd use Alembic migrations — but for the
    MVP a ``create_all`` plus a small idempotent ALTER list keeps the schema
    moving forward without dragging in a migration framework.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _apply_ad_hoc_migrations()
    log.info("alembic.db.init_db.done", url=_redact_url(settings.DATABASE_URL))


async def dispose_engine() -> None:
    """Close all pooled connections (called on shutdown)."""
    await engine.dispose()
    log.info("alembic.db.engine.disposed")


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding an ``AsyncSession``.

    Use as ``db: AsyncSession = Depends(get_db)``. Commit semantics are the
    caller's responsibility — read-only routes don't need to commit.
    """

    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


def _redact_url(url: str) -> str:
    """Hide credentials when echoing the DB URL into logs."""
    if "@" not in url:
        return url
    scheme, rest = url.split("://", 1)
    if "@" not in rest:
        return url
    creds, host = rest.split("@", 1)
    return f"{scheme}://***@{host}"
