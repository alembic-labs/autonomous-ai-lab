"""Pydantic v2 response models — matched 1:1 to the frontend's needs.

Wide-text columns that store JSON in the DB are surfaced here as proper
nested types (``dict``, ``list``) so the frontend doesn't have to double-parse.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FoldListItem(BaseModel):
    """Compact row used by the catalog page."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str | None = None
    title: str
    peptide_name: str
    peptide_class: str
    modification_description: str
    hypothesis: str = Field(..., description="Truncated to 200 chars on the server.")
    status: str
    fold_verdict: str | None = None
    confidence_plddt: float | None = None
    binding_probability: float | None = None
    binding_pic50: float | None = None
    predicted_binding_change: float | None = None
    created_at: datetime


class AgentTraceItem(BaseModel):
    agent_name: str
    started_at: datetime
    finished_at: datetime | None = None
    status: str
    model_used: str
    summary: str | None = None
    duration_seconds: float | None = None


class FoldDetail(BaseModel):
    """Full fold data for the detail page."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str | None = None
    title: str
    peptide_name: str
    peptide_sequence: str
    peptide_class: str
    modification_description: str
    modified_sequence: str | None = None
    target_protein: str | None = None
    target_uniprot_id: str | None = None
    target_chembl_id: str | None = None
    target_gene_symbol: str | None = None
    hypothesis: str
    rationale: str | None = None
    predicted_outcome: str | None = None

    # Section 2: AI Analysis
    ai_analysis_tldr: str | None = None
    ai_analysis_detailed: str | None = None

    # Section 3: Research Data
    known_activity: dict[str, Any] | None = None
    biohacker_use: str | None = None
    mechanism_class: str | None = None

    # Section 4: AI Research Brief
    research_brief_markdown: str | None = None

    # Section 5: Folding Metrics
    confidence_plddt: float | None = None
    confidence_ptm: float | None = None
    confidence_iptm: float | None = None
    chai_agreement: float | None = None
    # Adaptive Chai-1 cross-validation gating decision. One of
    # RAN_BORDERLINE / SKIPPED_HIGH_CONFIDENCE / SKIPPED_LOW_CONFIDENCE /
    # RAN_FORCED / DISABLED. NULL on legacy folds — the frontend treats
    # NULL the same as "no caption needed".
    chai1_gated_decision: str | None = None
    # Boltz-2 affinity module — calibrated binder probability + predicted pIC50.
    binding_probability: float | None = None
    binding_pic50: float | None = None

    # Section 6: Domain Annotations
    domain_annotations: dict[str, Any] | None = None

    # Section 7: Structural Caption
    structural_caption: str | None = None

    # Section 8: Peptide Profile
    aggregation_propensity: float | None = None
    stability_score: float | None = None
    bbb_penetration_score: float | None = None
    half_life_estimate: str | None = None

    # Section 9: Known Binders
    known_binders: list[dict[str, Any]] | None = None

    # Section 10: Candidate Variants
    candidate_variants: list[dict[str, Any]] | None = None

    # Section 11: Agent Findings
    agent_trace: list[AgentTraceItem] = Field(default_factory=list)
    literature_context: dict[str, Any] | None = None
    key_findings_summary: str | None = None

    # Section 12: Caveats
    caveats: list[str] | None = None

    # Section 13: Data
    has_pdb: bool = False
    # Legacy field — kept for backwards compatibility with older API
    # consumers. New clients should prefer ``onchain_signature``.
    onchain_hash: str | None = None
    # Solana SPL Memo transaction signature (present once the fold has been
    # committed to chain; null until then).
    onchain_signature: str | None = None
    # SHA-256 hex digest of the deterministic core payload — what the chain
    # commits to. Lets verifiers re-derive the hash and compare.
    onchain_data_hash: str | None = None
    onchain_logged_at: datetime | None = None
    # Pre-built Solscan URL for ``onchain_signature`` on the active network.
    # Server computes this so the client doesn't have to know the cluster.
    onchain_explorer_url: str | None = None
    ipfs_hash: str | None = None

    # Section 14: Works Cited
    works_cited: list[dict[str, Any]] | None = None

    # Status
    status: str
    fold_verdict: str | None = None
    predicted_binding_change: float | None = None
    # ``executive_summary`` is the short, sharable summary rendered at the top
    # of section 04. ``tweet_draft`` is reserved for the Twitter integration
    # (different format, max 280 chars).
    executive_summary: str | None = None
    tweet_draft: str | None = None
    created_at: datetime
    updated_at: datetime


class FoldMetricsResponse(BaseModel):
    plddt_per_residue: list[float] | None = None
    pae_matrix: list[list[float]] | None = None
    sequence_coverage: list[float] | None = None
    aggregation_window_scores: list[float] | None = None
    confidence_plddt: float | None = None
    confidence_ptm: float | None = None
    confidence_iptm: float | None = None
    chai_agreement: float | None = None
    binding_probability: float | None = None
    binding_pic50: float | None = None


class AgentStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent_name: str
    status: str
    current_task: str | None = None
    current_fold_id: int | None = None
    last_active_at: datetime


class LabStatsResponse(BaseModel):
    total_folds: int
    refined_count: int
    promising_count: int = 0
    pending_count: int
    discarded_count: int
    failed_count: int = 0
    peptides_explored_count: int
    days_running: int
    agents_active: int
    total_tokens_used: int
    total_cost_usd: float = 0.0
    avg_cycle_seconds: float
    # Adaptive Chai-1 telemetry — surfaced on /lab as a transparency block.
    # ``chai1_eligible`` = runs + skipped (excludes DISABLED folds where the
    # adaptive logic doesn't apply). ``chai1_run_ratio`` is precomputed for
    # the frontend so the UI doesn't have to guard against divide-by-zero.
    total_chai1_runs: int = 0
    total_chai1_skipped: int = 0
    chai1_eligible_folds: int = 0
    chai1_run_ratio: float | None = None
    # Solana on-chain logging telemetry. ``onchain_eligible_folds`` counts
    # only folds whose verdict warrants commitment (REFINED/PROMISING/
    # DISCARDED — FAILED and PENDING are excluded).
    total_onchain_logged: int = 0
    onchain_eligible_folds: int = 0
    onchain_logged_ratio: float | None = None
    onchain_enabled: bool = False
    onchain_network: str = "mainnet"


class FoldsListResponse(BaseModel):
    items: list[FoldListItem]
    total: int
    page: int
    page_size: int
    total_pages: int
