"""SQLAlchemy 2.0 ORM models.

Conventions:
- Async-friendly (no relationship lazy-loading at attribute access). Anything
  that needs related rows should use ``selectinload`` explicitly.
- Wide ``text`` columns hold JSON blobs serialized via ``json.dumps`` so we
  don't have to deal with Postgres-specific JSONB types in tests with sqlite.
- Timestamps are timezone-aware (UTC) — we never store naive datetimes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Common declarative base."""


class Fold(Base):
    """One research cycle = one fold = one row."""

    __tablename__ = "folds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=_utcnow,
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    peptide_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    peptide_sequence: Mapped[str] = mapped_column(Text, nullable=False, default="")
    peptide_class: Mapped[str] = mapped_column(String(50), nullable=False, default="")

    target_protein: Mapped[str | None] = mapped_column(String(100))
    target_uniprot_id: Mapped[str | None] = mapped_column(String(20))
    target_chembl_id: Mapped[str | None] = mapped_column(String(20))
    target_gene_symbol: Mapped[str | None] = mapped_column(String(40))
    target_sequence: Mapped[str | None] = mapped_column(Text)

    modification_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    modified_sequence: Mapped[str | None] = mapped_column(Text)

    hypothesis: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rationale: Mapped[str | None] = mapped_column(Text)
    predicted_outcome: Mapped[str | None] = mapped_column(Text)

    # --- Literature outputs (JSON-encoded text) ---
    literature_context: Mapped[str | None] = mapped_column(Text)
    works_cited: Mapped[str | None] = mapped_column(Text)
    key_findings_summary: Mapped[str | None] = mapped_column(Text)

    # --- Structural outputs ---
    pdb_file_path: Mapped[str | None] = mapped_column(String(500))
    confidence_plddt: Mapped[float | None] = mapped_column(Float)
    confidence_ptm: Mapped[float | None] = mapped_column(Float)
    confidence_iptm: Mapped[float | None] = mapped_column(Float)
    chai_agreement: Mapped[float | None] = mapped_column(Float)
    # Why Chai-1 cross-validation did or didn't run for this fold. One of:
    #   RAN_BORDERLINE          — Boltz-2 pLDDT inside the gate band, ran Chai-1
    #   SKIPPED_HIGH_CONFIDENCE — pLDDT above gate, skipped (cross-val not informative)
    #   SKIPPED_LOW_CONFIDENCE  — pLDDT below gate, skipped (already too noisy)
    #   RAN_FORCED              — legacy ENABLE_CHAI1=true override
    #   DISABLED                — both legacy + adaptive flags off
    # Surfaces the gating logic on the fold detail page and powers the
    # /api/stats Chai-1 ratio block. NULL for pre-feature folds.
    chai1_gated_decision: Mapped[str | None] = mapped_column(String(50))
    structural_caption: Mapped[str | None] = mapped_column(Text)
    plot_data: Mapped[str | None] = mapped_column(Text)
    fold_verdict: Mapped[str | None] = mapped_column(String(20), index=True)
    # --- Boltz-2 affinity module (the killer feature over plain folding) ---
    binding_probability: Mapped[float | None] = mapped_column(Float)
    binding_pic50: Mapped[float | None] = mapped_column(Float)

    # --- Clinical outputs ---
    known_activity: Mapped[str | None] = mapped_column(Text)
    biohacker_use: Mapped[str | None] = mapped_column(Text)
    mechanism_class: Mapped[str | None] = mapped_column(String(100))
    known_binders: Mapped[str | None] = mapped_column(Text)
    domain_annotations: Mapped[str | None] = mapped_column(Text)

    # --- Computed properties ---
    aggregation_propensity: Mapped[float | None] = mapped_column(Float)
    stability_score: Mapped[float | None] = mapped_column(Float)
    bbb_penetration_score: Mapped[float | None] = mapped_column(Float)
    half_life_estimate: Mapped[str | None] = mapped_column(Text)
    candidate_variants: Mapped[str | None] = mapped_column(Text)

    # --- Communicator outputs ---
    ai_analysis_tldr: Mapped[str | None] = mapped_column(Text)
    ai_analysis_detailed: Mapped[str | None] = mapped_column(Text)
    research_brief_markdown: Mapped[str | None] = mapped_column(Text)
    result_summary: Mapped[str | None] = mapped_column(Text)
    caveats: Mapped[str | None] = mapped_column(Text)
    # ``executive_summary`` is the short, sharable Communicator output that the
    # frontend renders at the top of section 04. Used to be called ``tweet_draft``
    # — the column was renamed for clarity. ``tweet_draft`` is kept as a separate
    # field reserved for the eventual Twitter integration (different format).
    executive_summary: Mapped[str | None] = mapped_column(Text)
    tweet_draft: Mapped[str | None] = mapped_column(Text)

    # --- Status / verdict ---
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING", index=True
    )
    predicted_binding_change: Mapped[float | None] = mapped_column(Float)

    # --- SEO / sharing ---
    slug: Mapped[str | None] = mapped_column(String(180), unique=True, index=True)

    # --- Onchain (Solana SPL Memo) ---
    # ``onchain_hash`` is the legacy column from the original schema. Kept for
    # backwards compatibility; new code reads/writes the explicit triple
    # below. The Communicator orchestrator populates these after the fold
    # reaches a terminal verdict.
    onchain_hash: Mapped[str | None] = mapped_column(String(100))
    # Solana transaction signature returned by ``client.send_transaction``.
    # 64 bytes base58 → up to ~88 chars; column sized 150 for headroom.
    onchain_signature: Mapped[str | None] = mapped_column(String(150))
    # SHA-256 hex digest (64 chars) of the deterministic core fold payload.
    # Column sized 70 to allow a future ``"sha3:"`` algorithm prefix.
    onchain_data_hash: Mapped[str | None] = mapped_column(String(70))
    onchain_logged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ipfs_hash: Mapped[str | None] = mapped_column(String(100))


class AgentRun(Base):
    """One row per agent execution. Useful for tracing and cost analytics."""

    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fold_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("folds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="RUNNING")
    model_used: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    summary: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    # Used by the Researcher memory layer ("recent strategies") and by the
    # Communicator cross-fold context. NULL means "no special signal".
    tags: Mapped[str | None] = mapped_column(Text)


class AgentStatus(Base):
    """Singleton-per-agent table holding live status (5 rows total)."""

    __tablename__ = "agent_status"

    agent_name: Mapped[str] = mapped_column(String(50), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="IDLE")
    current_task: Mapped[str | None] = mapped_column(String(500))
    current_fold_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("folds.id", ondelete="SET NULL")
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )


class LabStat(Base):
    """Singleton stats row (id always = 1)."""

    __tablename__ = "lab_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    total_folds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    refined_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    promising_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discarded_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    peptides_explored_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens_used: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_cycles: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_cycle_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Adaptive Chai-1 gating telemetry — bumped from cycle.py after the
    # structural agent settles. Used by /api/stats to render the
    # "Chai-1 runs: X / Y folds (Z%)" transparency block on /lab.
    total_chai1_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_chai1_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Number of folds successfully committed to Solana (signature received).
    # Surfaced on /lab as a transparency signal: "X / Y folds logged on-chain".
    total_onchain_logged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lab_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )


class KnownPeptide(Base):
    """Curated reference peptide registry (seeded from JSON on startup)."""

    __tablename__ = "known_peptides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    aliases: Mapped[str | None] = mapped_column(Text)
    sequence: Mapped[str] = mapped_column(Text, nullable=False)
    length: Mapped[int] = mapped_column(Integer, nullable=False)
    peptide_class: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # Free-form text list of target names — kept for backward compat / display.
    known_targets: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # Curated structured target list. JSON-serialised list[dict] with
    # ``{name, uniprot_id, chembl_id, gene_symbol, mechanism_role}``. The
    # Researcher agent picks one from this list — guarantees that every fold
    # downstream has resolvable IDs for ChEMBL / UniProt enrichment. Empty
    # list means "no curated target — agent must search UniProt itself".
    canonical_targets: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    mechanism_brief: Mapped[str] = mapped_column(Text, nullable=False, default="")
    biohacker_use: Mapped[str] = mapped_column(Text, nullable=False, default="")
    references: Mapped[str | None] = mapped_column(Text)


# Recognised constants — referenced from other modules.
AGENT_NAMES: tuple[str, ...] = (
    "RESEARCHER",
    "LITERATURE",
    "STRUCTURAL",
    "CLINICAL",
    "COMMUNICATOR",
)

FOLD_STATUSES: tuple[str, ...] = (
    "PENDING",
    "REFINED",
    "PROMISING",
    "DISCARDED",
    "FAILED",
)
FOLD_VERDICTS: tuple[str, ...] = (
    "REFINED",
    "PROMISING",
    "DISCARDED",
    "FAILED",
)
AGENT_STATUSES: tuple[str, ...] = ("IDLE", "ACTIVE", "ERROR")
CHAI1_GATING_DECISIONS: tuple[str, ...] = (
    "RAN_BORDERLINE",
    "SKIPPED_HIGH_CONFIDENCE",
    "SKIPPED_LOW_CONFIDENCE",
    "RAN_FORCED",
    "DISABLED",
)
PEPTIDE_CLASSES: tuple[str, ...] = (
    "PERFORMANCE",
    "LONGEVITY",
    "METABOLIC",
    "COGNITIVE",
    "REGENERATIVE",
)
