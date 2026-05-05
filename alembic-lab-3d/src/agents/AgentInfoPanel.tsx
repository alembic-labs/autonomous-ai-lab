import { useMemo } from "react";
import { SCIENTISTS } from "../scene/labSceneConfig";
import { useAgentLive } from "./agentLive";

const ROLE_LABEL: Record<string, string> = {
  RESEARCHER: "researcher",
  LITERATURE: "literature",
  STRUCTURAL: "structural",
  CLINICAL: "clinical",
  COMMUNICATOR: "communicator",
};

const ROLE_DESCRIPTION: Record<string, string> = {
  RESEARCHER: "proposes peptides and target hypotheses",
  LITERATURE: "mines published evidence and consensus",
  STRUCTURAL: "predicts and scores fold structure",
  CLINICAL: "estimates safety and translational risk",
  COMMUNICATOR: "writes the public report and on-chain log",
};

function formatLastActive(iso: string): string {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "unknown";
  const diff = Date.now() - t;
  const sec = Math.round(diff / 1000);
  if (sec < 5) return "just now";
  if (sec < 60) return `${sec}s ago`;
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 48) return `${hr}h ago`;
  const days = Math.round(hr / 24);
  return `${days}d ago`;
}

export function AgentInfoPanel() {
  const { statuses, selectedSlotId, setSelectedSlotId, fetchError, loaded } =
    useAgentLive();

  const slot = useMemo(
    () => SCIENTISTS.find((s) => s.id === selectedSlotId) ?? null,
    [selectedSlotId]
  );

  if (!slot) return null;

  const status = statuses[slot.agentRole];
  const roleLabel = ROLE_LABEL[slot.agentRole] ?? slot.agentRole.toLowerCase();
  const roleDesc = ROLE_DESCRIPTION[slot.agentRole] ?? "";

  return (
    <div className="agent-panel">
      <button
        type="button"
        className="agent-panel-close"
        onClick={() => setSelectedSlotId(null)}
        aria-label="close"
      >
        ×
      </button>

      <div className="agent-panel-header">
        <span className={`agent-panel-dot agent-panel-dot-${(status?.status ?? "IDLE").toLowerCase()}`} />
        <span className="agent-panel-role">{roleLabel}</span>
        <span className="agent-panel-zone">slot {slot.id} · {slot.zone.replace(/^\d+\s·\s/, "")}</span>
      </div>

      <div className="agent-panel-desc">{roleDesc}</div>

      {!loaded && !fetchError ? (
        <div className="agent-panel-row agent-panel-muted">connecting to lab…</div>
      ) : fetchError ? (
        <div className="agent-panel-row agent-panel-error">
          can't reach backend: {fetchError}
        </div>
      ) : !status ? (
        <div className="agent-panel-row agent-panel-muted">
          no status reported yet
        </div>
      ) : (
        <>
          <div className="agent-panel-row">
            <span className="agent-panel-key">status</span>
            <span className={`agent-panel-status agent-panel-status-${status.status.toLowerCase()}`}>
              {status.status.toLowerCase()}
            </span>
          </div>
          <div className="agent-panel-row">
            <span className="agent-panel-key">task</span>
            <span className="agent-panel-val">
              {status.current_task ?? <em className="agent-panel-muted">idle at station</em>}
            </span>
          </div>
          {status.current_fold_id != null ? (
            <div className="agent-panel-row">
              <span className="agent-panel-key">fold</span>
              <a
                className="agent-panel-link"
                href={`https://alembic.bio/folds/${status.current_fold_id}`}
                target="_blank"
                rel="noreferrer"
              >
                #{status.current_fold_id} ↗
              </a>
            </div>
          ) : null}
          <div className="agent-panel-row">
            <span className="agent-panel-key">last active</span>
            <span className="agent-panel-val">{formatLastActive(status.last_active_at)}</span>
          </div>
        </>
      )}
    </div>
  );
}
