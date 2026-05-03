import { SectionHeader } from "@/components/ui/SectionHeader";
import { formatNumber } from "@/lib/format";
import { getLabStats } from "@/lib/api";
import type { LabStats } from "@/lib/types";

export const dynamic = "force-dynamic";

interface CellProps {
  label: string;
  value: string;
  /** Optional small footer surfacing extra context (e.g. "adaptive gating"). */
  hint?: string;
}

function Cell({ label, value, hint }: CellProps) {
  return (
    <div>
      <div className="text-text-muted text-small uppercase tracking-wider">
        {label}
      </div>
      <div className="mt-2 text-h1 sm:text-[1.75rem] leading-none font-bold text-brand tabular-nums">
        {value}
      </div>
      {hint ? (
        <div className="mt-1 text-text-muted text-[11px]">{hint}</div>
      ) : null}
    </div>
  );
}

function formatDuration(seconds: number | undefined): string {
  if (!seconds) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${String(s).padStart(2, "0")}s`;
}

function formatCost(usd: number | undefined): string {
  if (usd === undefined || usd === null || Number.isNaN(usd)) return "—";
  if (usd === 0) return "$0.00";
  if (usd < 1) return `$${usd.toFixed(2)}`;
  return `$${usd.toFixed(2)}`;
}

/**
 * Format the adaptive Chai-1 gating ratio for the transparency cell.
 *
 * Returns ``"—"`` until at least one fold has hit the gate. The "Y" denominator
 * is ``runs + skipped`` (eligible folds), NOT total folds — DISABLED folds
 * (no creds, no target sequence) shouldn't pollute the ratio.
 */
function formatChai1Ratio(s: LabStats): string {
  const runs = s.total_chai1_runs ?? 0;
  const eligible = s.chai1_eligible_folds ?? 0;
  if (eligible === 0) return "—";
  const pct = Math.round((s.chai1_run_ratio ?? runs / eligible) * 100);
  return `${runs} / ${eligible} (${pct}%)`;
}

/**
 * Format the on-chain logging ratio for the transparency cell.
 *
 * Eligibility excludes PENDING / FAILED folds — only folds that reached a
 * publishable verdict (REFINED / PROMISING / DISCARDED) qualify. A fold with
 * a publishable verdict that hasn't been committed yet drags the ratio down,
 * which is exactly the signal we want to surface.
 */
function formatOnchainRatio(s: LabStats): string {
  const logged = s.total_onchain_logged ?? 0;
  const eligible = s.onchain_eligible_folds ?? 0;
  if (eligible === 0) return "—";
  const pct = Math.round((s.onchain_logged_ratio ?? logged / eligible) * 100);
  return `${logged} / ${eligible} (${pct}%)`;
}

const FALLBACK_STATS: LabStats = {
  total_folds: 0,
  refined_count: 0,
  promising_count: 0,
  pending_count: 0,
  discarded_count: 0,
  failed_count: 0,
  peptides_explored_count: 0,
  days_running: 0,
  uptime_human: "<1d",
  agents_active: 0,
  agents_total: 5,
  total_chai1_runs: 0,
  total_chai1_skipped: 0,
  chai1_eligible_folds: 0,
  chai1_run_ratio: null,
  total_onchain_logged: 0,
  onchain_eligible_folds: 0,
  onchain_logged_ratio: null,
  onchain_enabled: false,
  onchain_network: "mainnet",
};

export async function LiveMetrics() {
  let s: LabStats = FALLBACK_STATS;
  try {
    s = await getLabStats();
  } catch {
    /* keep fallback */
  }
  return (
    <section className="mb-16">
      <SectionHeader index="04" title="live metrics" />
      <div className="grid grid-cols-2 md:grid-cols-3 gap-y-8 gap-x-6 sm:gap-x-12">
        <Cell
          label="cycles completed"
          value={formatNumber(s.cycles_completed ?? 0)}
        />
        <Cell
          label="total tokens used"
          value={formatNumber(s.total_tokens ?? 0)}
        />
        <Cell label="folds generated" value={formatNumber(s.total_folds)} />
        <Cell label="avg cycle time" value={formatDuration(s.avg_cycle_seconds)} />
        <Cell
          label="avg tokens / cycle"
          value={formatNumber(s.avg_tokens_per_cycle ?? 0)}
        />
        <Cell label="lab uptime" value={s.uptime_human} />
        <Cell label="lab spend" value={formatCost(s.total_cost_usd)} />
        <Cell
          label="chai-1 runs"
          value={formatChai1Ratio(s)}
          hint={
            (s.chai1_eligible_folds ?? 0) === 0
              ? "adaptive gating — awaiting first eligible fold"
              : "adaptive gating active — runs only on borderline pLDDT"
          }
        />
        <Cell
          label="on-chain folds"
          value={formatOnchainRatio(s)}
          hint={
            !s.onchain_enabled
              ? "solana commit disabled — set SOLANA_ONCHAIN_ENABLED=true on the host"
              : (s.onchain_eligible_folds ?? 0) === 0
                ? `awaiting first publishable fold · ${s.onchain_network ?? "mainnet"}`
                : `SHA-256 of fold core data · solana ${s.onchain_network ?? "mainnet"}`
          }
        />
      </div>
    </section>
  );
}
