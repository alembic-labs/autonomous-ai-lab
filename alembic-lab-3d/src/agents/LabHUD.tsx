import { useMemo } from "react";
import { useAgentLive } from "./agentLive";
import { useLabPulse } from "./labPulse";

const SITE_BASE = "https://alembic.bio";

function formatVerdict(v: string | null | undefined): string {
  if (!v) return "—";
  return v.toLowerCase();
}

function formatCost(cost: number | null): string {
  if (cost == null) return "—";
  if (cost >= 100) return `$${cost.toFixed(0)}`;
  return `$${cost.toFixed(2)}`;
}

/**
 * Top-left ambient widget — "what's the lab doing right now".
 *
 * Shows the most recent fold (active if any agent has a current_fold_id,
 * otherwise the latest published) plus a four-stat strip: total folds,
 * refined count, peptides explored, days running. Auto-refreshes via the
 * polling providers (10s for agent status, 45s for stats).
 *
 * Kept narrow (260px) so it never competes for attention with the agent
 * info panel at the bottom-right; readable but unobtrusive.
 */
export function LabHUD() {
  const { statuses, loaded: liveLoaded } = useAgentLive();
  const { stats, latestFold, loaded: pulseLoaded, fetchError } = useLabPulse();

  // "Active fold" = whatever fold an ACTIVE agent is currently working on.
  // Prefer COMMUNICATOR > STRUCTURAL > LITERATURE > CLINICAL > RESEARCHER
  // because folds move through that order; the furthest-along agent's
  // fold is the most "recent" candidate when several are active.
  const activeFoldId = useMemo(() => {
    const order: Array<keyof typeof statuses> = [
      "COMMUNICATOR",
      "STRUCTURAL",
      "CLINICAL",
      "LITERATURE",
      "RESEARCHER",
    ];
    for (const role of order) {
      const s = statuses[role];
      if (s?.status === "ACTIVE" && s.current_fold_id != null) {
        return { id: s.current_fold_id, role };
      }
    }
    return null;
  }, [statuses]);

  const ready = liveLoaded || pulseLoaded;
  if (!ready && !fetchError) {
    return (
      <div className="lab-hud lab-hud-skeleton">
        <div className="lab-hud-row lab-hud-muted">connecting to lab…</div>
      </div>
    );
  }
  if (!stats && fetchError) {
    return (
      <div className="lab-hud">
        <div className="lab-hud-row lab-hud-error">backend offline · {fetchError}</div>
      </div>
    );
  }
  if (!stats) return null;

  const fold = latestFold;
  const isActive = activeFoldId != null;
  const peptide = fold?.peptide_name ?? "—";
  const target = fold?.target_protein ?? "—";
  const verdict = formatVerdict(fold?.fold_verdict);
  const foldHref = fold ? `${SITE_BASE}/folds/${fold.id}` : SITE_BASE;

  return (
    <div className="lab-hud">
      <div className="lab-hud-header">
        <span className={`lab-hud-pulse ${isActive ? "lab-hud-pulse-on" : ""}`} />
        <span className="lab-hud-title">
          {isActive ? "research in progress" : "lab pulse"}
        </span>
      </div>

      {fold ? (
        <a className="lab-hud-fold" href={foldHref} target="_blank" rel="noreferrer">
          <span className="lab-hud-fold-id">fold #{fold.id}</span>
          <span className="lab-hud-fold-arrow">↗</span>
          <span className="lab-hud-fold-line">
            {peptide} <span className="lab-hud-muted">→ {target}</span>
          </span>
          <span className={`lab-hud-fold-verdict lab-hud-fold-verdict-${verdict}`}>
            {isActive
              ? `${(activeFoldId?.role ?? "").toLowerCase()} working`
              : verdict}
          </span>
        </a>
      ) : null}

      <div className="lab-hud-grid">
        <div>
          <span className="lab-hud-num">{stats.total_folds}</span>
          <span className="lab-hud-key">folds</span>
        </div>
        <div>
          <span className="lab-hud-num">{stats.refined_count}</span>
          <span className="lab-hud-key">refined</span>
        </div>
        <div>
          <span className="lab-hud-num">{stats.peptides_explored_count}</span>
          <span className="lab-hud-key">peptides</span>
        </div>
        <div>
          <span className="lab-hud-num">{stats.days_running}d</span>
          <span className="lab-hud-key">running</span>
        </div>
      </div>

      <div className="lab-hud-footer">
        <span className="lab-hud-muted">spend · {formatCost(stats.total_cost_usd)}</span>
        <a
          className="lab-hud-footer-link"
          href={`${SITE_BASE}/folds`}
          target="_blank"
          rel="noreferrer"
        >
          all folds ↗
        </a>
      </div>
    </div>
  );
}
