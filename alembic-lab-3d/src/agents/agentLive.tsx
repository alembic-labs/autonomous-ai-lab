import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { AgentRole } from "../scene/labSceneConfig";

export type AgentStatusKind = "ACTIVE" | "IDLE" | "ERROR";

export type AgentStatus = {
  agent_name: AgentRole;
  status: AgentStatusKind;
  current_task: string | null;
  current_fold_id: number | null;
  last_active_at: string;
};

type RawAgentStatus = {
  agent_name: string;
  status: string;
  current_task: string | null;
  current_fold_id: number | null;
  last_active_at: string;
};

const KNOWN_ROLES: ReadonlySet<AgentRole> = new Set([
  "RESEARCHER",
  "LITERATURE",
  "STRUCTURAL",
  "CLINICAL",
  "COMMUNICATOR",
]);

const POLL_INTERVAL_MS = 10_000;

type AgentLiveContextValue = {
  /** Map keyed by agent role; missing keys = backend hasn't reported that agent yet. */
  statuses: Partial<Record<AgentRole, AgentStatus>>;
  /** Currently selected slot id (the slot the user clicked) — used for the info panel. */
  selectedSlotId: string | null;
  setSelectedSlotId: (id: string | null) => void;
  /** Last fetch error message, or null when healthy. */
  fetchError: string | null;
  /** True after at least one successful fetch. */
  loaded: boolean;
};

const AgentLiveContext = createContext<AgentLiveContextValue | null>(null);

function adapt(raw: RawAgentStatus): AgentStatus | null {
  if (!KNOWN_ROLES.has(raw.agent_name as AgentRole)) return null;
  const upper = (raw.status || "").toUpperCase();
  const status: AgentStatusKind =
    upper === "ACTIVE" ? "ACTIVE" : upper === "ERROR" ? "ERROR" : "IDLE";
  return {
    agent_name: raw.agent_name as AgentRole,
    status,
    current_task: raw.current_task,
    current_fold_id: raw.current_fold_id,
    last_active_at: raw.last_active_at,
  };
}

export function AgentLiveProvider({ children }: { children: ReactNode }) {
  const [statuses, setStatuses] = useState<
    Partial<Record<AgentRole, AgentStatus>>
  >({});
  const [selectedSlotId, setSelectedSlotIdState] = useState<string | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const inflightRef = useRef<AbortController | null>(null);

  const setSelectedSlotId = useCallback((id: string | null) => {
    setSelectedSlotIdState(id);
  }, []);

  useEffect(() => {
    let cancelled = false;

    const fetchOnce = async () => {
      inflightRef.current?.abort();
      const ctrl = new AbortController();
      inflightRef.current = ctrl;
      try {
        const res = await fetch("/api/agents/status", {
          signal: ctrl.signal,
          // The browser may aggressively cache; explicit no-store keeps it
          // honest. The backend itself is uncached for this endpoint.
          cache: "no-store",
        });
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const raw = (await res.json()) as RawAgentStatus[];
        if (cancelled) return;
        const next: Partial<Record<AgentRole, AgentStatus>> = {};
        for (const r of raw) {
          const adapted = adapt(r);
          if (adapted) next[adapted.agent_name] = adapted;
        }
        setStatuses(next);
        setFetchError(null);
        setLoaded(true);
      } catch (err) {
        if (cancelled || (err as Error).name === "AbortError") return;
        setFetchError((err as Error).message || "fetch failed");
      }
    };

    void fetchOnce();
    const interval = window.setInterval(fetchOnce, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
      inflightRef.current?.abort();
    };
  }, []);

  const value = useMemo<AgentLiveContextValue>(
    () => ({ statuses, selectedSlotId, setSelectedSlotId, fetchError, loaded }),
    [statuses, selectedSlotId, setSelectedSlotId, fetchError, loaded]
  );

  return (
    <AgentLiveContext.Provider value={value}>
      {children}
    </AgentLiveContext.Provider>
  );
}

export function useAgentLive(): AgentLiveContextValue {
  const v = useContext(AgentLiveContext);
  if (!v) throw new Error("useAgentLive: wrap App in AgentLiveProvider");
  return v;
}
