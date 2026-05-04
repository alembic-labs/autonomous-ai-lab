// ALEMBIC LABS — backend API client.
// Wraps fetch() and adapts backend Pydantic shapes to the frontend's TypeScript
// types so existing UI components keep working without per-component edits.

import type {
  AgentStatus,
  Chai1GatedDecision,
  FoldDetail,
  FoldListItem,
  FoldMetrics,
  FoldsListResponse,
  LabStats,
  PeptideClass,
  FoldStatus,
  AgentName,
  FoldVerdict,
} from "./types";

const RAW_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const API_BASE = RAW_BASE.replace(/\/$/, "");

interface FetchOptions extends RequestInit {
  /** Cache hint — for SSR / static fetches (Next.js `next.revalidate`). */
  revalidate?: number;
}

async function apiFetch<T>(path: string, opts: FetchOptions = {}): Promise<T> {
  const { revalidate, ...rest } = opts;
  const init: RequestInit = {
    headers: { Accept: "application/json", ...(rest.headers ?? {}) },
    ...rest,
  };
  if (typeof revalidate === "number") {
    (init as RequestInit & { next?: { revalidate: number } }).next = {
      revalidate,
    };
  }
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    throw new Error(`API ${res.status} ${res.statusText} on ${path}`);
  }
  return (await res.json()) as T;
}

// ---------- Backend response shapes ----------

interface BackendFoldListItem {
  id: number;
  slug: string | null;
  title: string;
  peptide_name: string | null;
  peptide_class: string | null;
  modification_description: string | null;
  hypothesis: string | null;
  status: string;
  fold_verdict: string | null;
  confidence_plddt: number | null;
  binding_probability: number | null;
  binding_pic50: number | null;
  predicted_binding_change: number | null;
  created_at: string;
}

interface BackendFoldsListResponse {
  items: BackendFoldListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

interface BackendAgentTraceItem {
  agent_name: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  model_used: string;
  summary: string | null;
  duration_seconds: number | null;
}

interface BackendFoldDetail extends BackendFoldListItem {
  peptide_sequence: string | null;
  modified_sequence: string | null;
  target_protein: string | null;
  target_uniprot_id: string | null;
  target_chembl_id: string | null;
  target_gene_symbol: string | null;
  rationale: string | null;
  predicted_outcome: string | null;
  ai_analysis_tldr: string | null;
  ai_analysis_detailed: string | null;
  known_activity: Record<string, unknown> | null;
  biohacker_use: string | Record<string, unknown> | null;
  mechanism_class: string | null;
  research_brief_markdown: string | null;
  confidence_ptm: number | null;
  confidence_iptm: number | null;
  chai_agreement: number | null;
  chai1_gated_decision: string | null;
  domain_annotations: Record<string, unknown> | null;
  structural_caption: string | null;
  aggregation_propensity: number | null;
  stability_score: number | null;
  bbb_penetration_score: number | null;
  half_life_estimate: string | null;
  known_binders: Record<string, unknown>[] | null;
  candidate_variants: Record<string, unknown>[] | null;
  agent_trace: BackendAgentTraceItem[];
  literature_context: Record<string, unknown> | null;
  key_findings_summary: string | null;
  caveats: string[] | null;
  has_pdb: boolean;
  onchain_hash: string | null;
  onchain_signature: string | null;
  onchain_data_hash: string | null;
  onchain_logged_at: string | null;
  onchain_explorer_url: string | null;
  ipfs_hash: string | null;
  works_cited: Record<string, unknown>[] | null;
  executive_summary: string | null;
  tweet_draft: string | null;
  updated_at: string;
}

interface BackendAgentStatus {
  agent_name: string;
  status: string;
  current_task: string | null;
  current_fold_id: number | null;
  last_active_at: string;
}

interface BackendLabStats {
  total_folds: number;
  refined_count: number;
  promising_count: number;
  pending_count: number;
  discarded_count: number;
  failed_count: number;
  peptides_explored_count: number;
  days_running: number;
  agents_active: number;
  total_tokens_used: number;
  total_cost_usd: number;
  avg_cycle_seconds: number;
  total_chai1_runs?: number;
  total_chai1_skipped?: number;
  chai1_eligible_folds?: number;
  chai1_run_ratio?: number | null;
  total_onchain_logged?: number;
  onchain_eligible_folds?: number;
  onchain_logged_ratio?: number | null;
  onchain_enabled?: boolean;
  onchain_network?: string;
}

// ---------- Adapters: backend → frontend types ----------

function toPeptideClass(value: string | null | undefined): PeptideClass {
  const allowed: PeptideClass[] = [
    "PERFORMANCE",
    "LONGEVITY",
    "METABOLIC",
    "COGNITIVE",
    "REGENERATIVE",
  ];
  const v = (value ?? "").toUpperCase() as PeptideClass;
  return allowed.includes(v) ? v : "PERFORMANCE";
}

function toFoldStatus(status: string, verdict: string | null): FoldStatus {
  const upper = (verdict ?? status ?? "").toUpperCase();
  if (upper === "REFINED") return "REFINED";
  if (upper === "PROMISING") return "PROMISING";
  if (upper === "DISCARDED") return "DISCARDED";
  if (upper === "FAILED") return "FAILED";
  return "PENDING";
}

function toFoldVerdict(value: string | null): FoldVerdict | null {
  const upper = (value ?? "").toUpperCase();
  if (
    upper === "REFINED" ||
    upper === "PROMISING" ||
    upper === "DISCARDED" ||
    upper === "FAILED"
  ) {
    return upper;
  }
  return null;
}

function toChai1Decision(
  value: string | null | undefined,
): Chai1GatedDecision | null {
  const upper = (value ?? "").toUpperCase();
  if (
    upper === "RAN_BORDERLINE" ||
    upper === "SKIPPED_HIGH_CONFIDENCE" ||
    upper === "SKIPPED_LOW_CONFIDENCE" ||
    upper === "RAN_FORCED" ||
    upper === "DISABLED"
  ) {
    return upper;
  }
  return null;
}

function adaptListItem(b: BackendFoldListItem): FoldListItem {
  return {
    id: b.id,
    slug: b.slug ?? null,
    title: b.title || `Fold #${b.id}`,
    peptide_name: b.peptide_name || "—",
    peptide_class: toPeptideClass(b.peptide_class),
    modification_description: b.modification_description || "—",
    hypothesis: b.hypothesis || "",
    status: toFoldStatus(b.status, b.fold_verdict),
    fold_verdict: toFoldVerdict(b.fold_verdict),
    predicted_binding_change: b.predicted_binding_change,
    confidence_plddt: b.confidence_plddt,
    binding_probability: b.binding_probability ?? null,
    binding_pic50: b.binding_pic50 ?? null,
    created_at: b.created_at,
  };
}

function adaptDetail(b: BackendFoldDetail): FoldDetail {
  const base = adaptListItem(b);

  const knownBinders = Array.isArray(b.known_binders)
    ? (b.known_binders as Array<Record<string, unknown>>).map((kb) => ({
        chembl_id: String(kb.chembl_id ?? kb.id ?? ""),
        kd_nM: Number(kb.kd_nM ?? kb.kd_nm ?? kb.kd ?? 0),
        pchembl: Number(kb.pchembl ?? kb.pChEMBL ?? 0),
      }))
    : null;

  const candidateVariants = Array.isArray(b.candidate_variants)
    ? (b.candidate_variants as Array<Record<string, unknown>>).map((v, i) => ({
        id: String(v.id ?? `CV-${i + 1}`),
        modification: String(v.modification ?? ""),
        aggregation: Number(v.aggregation ?? 0),
        stability: (v.stability as "low" | "medium" | "high") ?? "medium",
        toxicity: (v.toxicity as "low" | "medium" | "high") ?? "low",
        best_iptm: Number(v.best_iptm ?? 0),
      }))
    : null;

  const worksCited = Array.isArray(b.works_cited)
    ? (b.works_cited as Array<Record<string, unknown>>).map((w) => ({
        pmid: String(w.pmid ?? ""),
        title: String(w.title ?? ""),
        authors: Array.isArray(w.authors) ? (w.authors as string[]) : [],
        year: typeof w.year === "number" ? w.year : 0,
        journal: String(w.journal ?? ""),
        abstract:
          typeof w.abstract === "string" ? (w.abstract as string) : undefined,
      }))
    : null;

  return {
    ...base,
    peptide_sequence: b.peptide_sequence ?? "",
    modified_sequence: b.modified_sequence,
    target_protein: b.target_protein,
    target_uniprot_id: b.target_uniprot_id,
    target_chembl_id: b.target_chembl_id ?? null,
    target_gene_symbol: b.target_gene_symbol ?? null,
    rationale: b.rationale,
    predicted_outcome: b.predicted_outcome,

    tldr: b.ai_analysis_tldr,
    detailed_analysis: b.ai_analysis_detailed,

    known_activity: (b.known_activity as Record<string, unknown> | null) ?? null,
    biohacker_use:
      typeof b.biohacker_use === "string"
        ? b.biohacker_use
        : b.biohacker_use === null || b.biohacker_use === undefined
          ? null
          : JSON.stringify(b.biohacker_use),
    mechanism_class: b.mechanism_class ?? null,

    research_brief_markdown: b.research_brief_markdown,

    confidence_ptm: b.confidence_ptm,
    confidence_iptm: b.confidence_iptm,
    agreement_score: b.chai_agreement,
    chai1_gated_decision: toChai1Decision(b.chai1_gated_decision),

    domain_annotations:
      (b.domain_annotations as Record<string, unknown> | null) ?? null,
    structural_caption: b.structural_caption,

    aggregation_propensity: b.aggregation_propensity,
    stability_score: b.stability_score,
    bbb_penetration_score: b.bbb_penetration_score,
    half_life_estimate: b.half_life_estimate,

    known_binders: knownBinders,
    candidate_variants: candidateVariants,

    agent_trace: (b.agent_trace ?? []).map((t) => ({
      agent_name: (t.agent_name as AgentName) ?? "RESEARCHER",
      started_at: t.started_at,
      finished_at: t.finished_at,
      status: (t.status as "RUNNING" | "COMPLETED" | "FAILED") ?? "COMPLETED",
      model_used: t.model_used,
      summary: t.summary,
      duration_seconds: t.duration_seconds,
    })),
    literature_context: b.literature_context ?? null,
    key_findings_summary: b.key_findings_summary,

    caveats: b.caveats,
    has_pdb: b.has_pdb,
    onchain_hash: b.onchain_hash,
    onchain_signature: b.onchain_signature ?? null,
    onchain_data_hash: b.onchain_data_hash ?? null,
    onchain_logged_at: b.onchain_logged_at ?? null,
    onchain_explorer_url: b.onchain_explorer_url ?? null,
    ipfs_hash: b.ipfs_hash,
    works_cited: worksCited,

    // Backend now exposes ``executive_summary`` as a first-class field. We
    // fall back to ``tweet_draft`` for old folds that pre-date the rename.
    executive_summary: b.executive_summary ?? b.tweet_draft ?? null,

    status: toFoldStatus(b.status, b.fold_verdict),
    fold_verdict: toFoldVerdict(b.fold_verdict),
    predicted_binding_change: b.predicted_binding_change,
    updated_at: b.updated_at,
  };
}

function adaptAgentStatus(b: BackendAgentStatus): AgentStatus {
  return {
    agent_name: (b.agent_name as AgentName) ?? "RESEARCHER",
    status:
      b.status === "ACTIVE"
        ? "ACTIVE"
        : b.status === "ERROR"
          ? "ERROR"
          : "IDLE",
    current_task: b.current_task,
    current_fold_id: b.current_fold_id,
    last_active_at: b.last_active_at,
  };
}

function formatUptime(days: number): string {
  if (days <= 0) return "<1d";
  return `${days}d`;
}

function adaptLabStats(b: BackendLabStats): LabStats {
  return {
    total_folds: b.total_folds,
    refined_count: b.refined_count,
    promising_count: b.promising_count ?? 0,
    pending_count: b.pending_count,
    discarded_count: b.discarded_count,
    failed_count: b.failed_count ?? 0,
    peptides_explored_count: b.peptides_explored_count,
    days_running: b.days_running,
    uptime_human: formatUptime(b.days_running),
    agents_active: b.agents_active,
    agents_total: 5,
    cycles_completed: b.total_folds,
    total_tokens: b.total_tokens_used,
    total_cost_usd: b.total_cost_usd ?? 0,
    avg_cycle_seconds: Math.round(b.avg_cycle_seconds),
    avg_tokens_per_cycle:
      b.total_folds > 0
        ? Math.round((b.total_tokens_used ?? 0) / b.total_folds)
        : 0,
    total_chai1_runs: b.total_chai1_runs ?? 0,
    total_chai1_skipped: b.total_chai1_skipped ?? 0,
    chai1_eligible_folds: b.chai1_eligible_folds ?? 0,
    chai1_run_ratio: b.chai1_run_ratio ?? null,
    total_onchain_logged: b.total_onchain_logged ?? 0,
    onchain_eligible_folds: b.onchain_eligible_folds ?? 0,
    onchain_logged_ratio: b.onchain_logged_ratio ?? null,
    onchain_enabled: b.onchain_enabled ?? false,
    onchain_network: b.onchain_network ?? "mainnet",
  };
}

// ---------- Public API ----------

export interface FoldsQuery {
  peptide_class?: string;
  status?: string;
  search?: string;
  min_confidence?: number;
  sort?: "newest" | "oldest" | "highest_confidence" | "lowest_confidence";
  page?: number;
  page_size?: number;
}

export async function listFolds(query: FoldsQuery = {}): Promise<FoldsListResponse> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    params.set(key, String(value));
  }
  const qs = params.toString();
  const raw = await apiFetch<BackendFoldsListResponse>(
    `/api/folds${qs ? `?${qs}` : ""}`,
    { revalidate: 30 },
  );
  return {
    items: raw.items.map(adaptListItem),
    total: raw.total,
    page: raw.page,
    page_size: raw.page_size,
    total_pages: raw.total_pages,
  };
}

export async function getFold(id: number | string): Promise<FoldDetail> {
  // No cache — folds are written incrementally by the orchestrator
  // (Communicator can finish minutes after the page is first hit), so we
  // always read fresh state and let the page itself stay ``force-dynamic``.
  const raw = await apiFetch<BackendFoldDetail>(`/api/folds/${id}`, {
    cache: "no-store",
  });
  return adaptDetail(raw);
}

export async function getFoldMetrics(id: number | string): Promise<FoldMetrics> {
  interface BackendMetrics {
    plddt_per_residue: number[] | null;
    pae_matrix: number[][] | null;
    sequence_coverage: number[] | null;
    aggregation_window_scores: number[] | null;
    confidence_plddt: number | null;
    confidence_ptm: number | null;
    confidence_iptm: number | null;
    chai_agreement: number | null;
    binding_probability: number | null;
    binding_pic50: number | null;
  }
  const m = await apiFetch<BackendMetrics>(`/api/folds/${id}/metrics`, {
    cache: "no-store",
  });
  const perRes = (m.plddt_per_residue ?? []).map((p, i) => ({
    residue: i + 1,
    plddt: p,
  }));
  const matrices = m.pae_matrix
    ? [{ name: "rank 1", size: m.pae_matrix.length, values: m.pae_matrix }]
    : [];
  // ``id`` may be either a numeric id ("12") or a slug ("12-sermorelin-...").
  // We extract the numeric prefix so the client-side type stays a real number.
  const numericId =
    typeof id === "string"
      ? parseInt(id.split("-")[0] ?? id, 10) || 0
      : id;
  return {
    fold_id: numericId,
    plddt_per_residue: perRes,
    pae_matrices: matrices,
    aggregation_window_scores: m.aggregation_window_scores ?? [],
    plddt_mean: m.confidence_plddt ?? 0,
    ptm: m.confidence_ptm,
    iptm: m.confidence_iptm,
    agreement: m.chai_agreement,
    binding_probability: m.binding_probability ?? null,
    binding_pic50: m.binding_pic50 ?? null,
  };
}

export function getStructureUrl(id: number | string): string {
  return `${API_BASE}/api/folds/${id}/structure`;
}

export function getReportHtmlUrl(id: number | string): string {
  return `${API_BASE}/api/folds/${id}/report.html`;
}

export function getReportPdfUrl(id: number | string): string {
  return `${API_BASE}/api/folds/${id}/report.pdf`;
}

export function getReportJsonUrl(id: number | string): string {
  return `${API_BASE}/api/folds/${id}/report.json`;
}

export async function getStructurePdb(id: number | string): Promise<string> {
  const res = await fetch(getStructureUrl(id));
  if (!res.ok) throw new Error(`Structure ${res.status} for fold ${id}`);
  return res.text();
}

export async function getAgentsStatus(): Promise<AgentStatus[]> {
  const raw = await apiFetch<BackendAgentStatus[]>(`/api/agents/status`, {
    cache: "no-store",
  });
  return raw.map(adaptAgentStatus);
}

export async function getLabStats(): Promise<LabStats> {
  const raw = await apiFetch<BackendLabStats>(`/api/stats`, { revalidate: 30 });
  return adaptLabStats(raw);
}

export async function getHealth(): Promise<{ status: string; lab: string }> {
  return apiFetch(`/api/health`, { cache: "no-store" });
}
