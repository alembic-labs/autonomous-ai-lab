// ALEMBIC LABS — shared TypeScript interfaces.
// Mirrors the backend API contract documented in CURSOR_PACK_FRONTEND.md §6.

export type FoldStatus =
  | "REFINED"
  | "PROMISING"
  | "PENDING"
  | "DISCARDED"
  | "FAILED";

export type FoldVerdict = "REFINED" | "PROMISING" | "DISCARDED" | "FAILED";

// Adaptive Chai-1 cross-validation gating decision per fold. NULL on legacy
// folds that pre-date the gate; the UI treats NULL as "no caption".
export type Chai1GatedDecision =
  | "RAN_BORDERLINE"
  | "SKIPPED_HIGH_CONFIDENCE"
  | "SKIPPED_LOW_CONFIDENCE"
  | "RAN_FORCED"
  | "DISABLED";

export type PeptideClass =
  | "PERFORMANCE"
  | "LONGEVITY"
  | "METABOLIC"
  | "COGNITIVE"
  | "REGENERATIVE";

export type AgentName =
  | "RESEARCHER"
  | "LITERATURE"
  | "STRUCTURAL"
  | "CLINICAL"
  | "COMMUNICATOR";

export type AgentRunStatus = "IDLE" | "ACTIVE" | "ERROR";

export interface FoldListItem {
  id: number;
  slug: string | null;
  title: string;
  peptide_name: string;
  peptide_class: PeptideClass;
  modification_description: string;
  hypothesis: string;
  status: FoldStatus;
  fold_verdict: FoldVerdict | null;
  predicted_binding_change: number | null;
  confidence_plddt: number | null;
  binding_probability: number | null;
  binding_pic50: number | null;
  created_at: string; // ISO 8601
}

export interface FoldsListResponse {
  items: FoldListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface AgentTraceItem {
  agent_name: AgentName;
  started_at: string;
  finished_at: string | null;
  status: "RUNNING" | "COMPLETED" | "FAILED";
  model_used: string;
  summary: string | null;
  duration_seconds: number | null;
}

export interface ResearchPaper {
  pmid: string;
  title: string;
  authors: string[];
  year: number;
  journal: string;
  abstract?: string;
}

export interface DomainAnnotation {
  type: string;
  residues: string; // e.g. "1–16"
  description: string;
}

export interface KnownBinder {
  chembl_id: string;
  kd_nM: number;
  pchembl: number;
}

export interface CandidateVariant {
  id: string;
  modification: string;
  aggregation: number;
  stability: "low" | "medium" | "high";
  toxicity: "low" | "medium" | "high";
  best_iptm: number;
}

export interface AgentFinding {
  agent: AgentName;
  finding: string;
  timestamp: string;
}

export interface KnownActivity {
  primary_target?: string;
  affinity_kd_nm?: number | null;
  pchembl?: number | null;
  potency_summary?: string;
  receptor_class?: string;
  source?: string;
  notes?: string;
  [key: string]: unknown;
}

export interface DomainAnnotations {
  domains?: DomainAnnotation[];
  binding_sites?: { residues: string; description: string }[];
  binding_partners?: { name: string; experiments?: number; uniprot?: string }[];
  gene_ontology?: string[];
  go_terms?: string[];
  [key: string]: unknown;
}

export interface FoldDetail extends FoldListItem {
  peptide_sequence: string;
  modified_sequence: string | null;
  target_protein: string | null;
  target_uniprot_id: string | null;
  target_chembl_id: string | null;
  target_gene_symbol: string | null;
  rationale: string | null;
  predicted_outcome: string | null;

  // Section 02: AI analysis
  tldr: string | null; // backend: ai_analysis_tldr
  detailed_analysis: string | null; // backend: ai_analysis_detailed

  // Section 03: research data
  known_activity: KnownActivity | null;
  biohacker_use: string | null;
  mechanism_class: string | null;

  // Section 04: long markdown report
  research_brief_markdown: string | null;

  // Section 05: folding metrics
  confidence_ptm: number | null;
  confidence_iptm: number | null;
  agreement_score: number | null; // backend: chai_agreement
  // Adaptive Chai-1 cross-validation gating decision (drives the small
  // caption next to the agreement number). NULL = legacy fold.
  chai1_gated_decision: Chai1GatedDecision | null;

  // Section 06: domain annotations (free-form JSON from agents)
  domain_annotations: DomainAnnotations | null;

  // Section 07
  structural_caption: string | null;

  // Section 08: peptide profile
  aggregation_propensity: number | null;
  stability_score: number | null;
  bbb_penetration_score: number | null;
  half_life_estimate: string | null;

  // Section 09 / 10
  known_binders: KnownBinder[] | null;
  candidate_variants: CandidateVariant[] | null;

  // Section 11
  agent_trace: AgentTraceItem[];
  literature_context: Record<string, unknown> | null;
  key_findings_summary: string | null;

  // Section 12-14
  caveats: string[] | null;
  has_pdb: boolean;
  // Legacy field — present for older folds before the explicit triple
  // below. New code should prefer ``onchain_signature``.
  onchain_hash: string | null;
  // Solana SPL Memo transaction signature (null until committed on-chain).
  onchain_signature: string | null;
  // SHA-256 hex digest of the deterministic core payload that the chain
  // commits to. Lets users re-derive and verify the hash.
  onchain_data_hash: string | null;
  onchain_logged_at: string | null;
  // Pre-built Solscan URL on the active network (mainnet vs devnet) — the
  // server picks the right cluster suffix so the client doesn't have to.
  onchain_explorer_url: string | null;
  ipfs_hash: string | null;
  works_cited: ResearchPaper[] | null;

  // Communicator final summary (was "tweet_draft" — kept for download/share)
  executive_summary: string | null;

  status: FoldStatus;
  fold_verdict: FoldVerdict | null;
  predicted_binding_change: number | null;
  // Set by the backend's predictability gate when the fold was DISCARDED
  // *before* Structural ran (lipid target, missing UniProt, sub-resolution
  // peptide length, etc.). NULL for normal folds and for DISCARDED folds
  // that ran the full pipeline. Surfaced as a callout in section 02.
  discard_reason: string | null;
  updated_at: string;
}

export interface FoldMetrics {
  fold_id: number;
  /** pLDDT per residue, length = sequence length. */
  plddt_per_residue: { residue: number; plddt: number }[];
  /** up to 5 PAE matrices (NxN). */
  pae_matrices: { name: string; size: number; values: number[][] }[];
  /** Per-window aggregation propensity. */
  aggregation_window_scores: number[];
  plddt_mean: number;
  ptm: number | null;
  iptm: number | null;
  agreement: number | null;
  /** Boltz-2 affinity module: calibrated binder probability (0..1). */
  binding_probability: number | null;
  /** Boltz-2 affinity module: predicted pIC50 (negative log10 of molar IC50). */
  binding_pic50: number | null;
}

export interface AgentStatus {
  agent_name: AgentName;
  status: AgentRunStatus;
  current_task: string | null;
  current_fold_id: number | null;
  last_active_at: string;
  total_runs?: number;
  model_used?: string;
}

export interface LabStats {
  total_folds: number;
  refined_count: number;
  promising_count: number;
  pending_count: number;
  discarded_count: number;
  failed_count: number;
  peptides_explored_count: number;
  days_running: number;
  uptime_human: string; // e.g. "14d 03h"
  agents_active: number;
  agents_total: number;
  cycles_completed?: number;
  total_tokens?: number;
  total_cost_usd?: number;
  avg_cycle_seconds?: number;
  avg_tokens_per_cycle?: number;
  // Adaptive Chai-1 telemetry — powers the "Chai-1 runs: X / Y folds (Z%)"
  // transparency block on /lab. ``chai1_run_ratio`` is precomputed by the
  // backend (null when no eligible folds yet).
  total_chai1_runs?: number;
  total_chai1_skipped?: number;
  chai1_eligible_folds?: number;
  chai1_run_ratio?: number | null;
  // Solana on-chain logging telemetry — drives the "on-chain folds" cell
  // on /lab. ``onchain_eligible_folds`` excludes PENDING/FAILED.
  total_onchain_logged?: number;
  onchain_eligible_folds?: number;
  onchain_logged_ratio?: number | null;
  onchain_enabled?: boolean;
  onchain_network?: string;
}

// Stack Analyzer chat
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}
