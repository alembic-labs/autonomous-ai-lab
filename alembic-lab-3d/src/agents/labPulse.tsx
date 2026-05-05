import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

// Polling interval for the corner HUD widget. Stats and the most-recent
// fold both move on the order of minutes, so 45s is plenty without
// hammering the backend (the agent-status endpoint already polls at 10s).
const POLL_INTERVAL_MS = 45_000;

export type LabStats = {
  total_folds: number;
  refined_count: number;
  promising_count: number;
  discarded_count: number;
  failed_count: number;
  pending_count: number;
  peptides_explored_count: number;
  days_running: number;
  total_cost_usd: number | null;
};

export type LatestFold = {
  id: number;
  slug: string | null;
  peptide_name: string | null;
  target_protein: string | null;
  status: string;
  fold_verdict: string | null;
  modification_description: string | null;
  created_at: string;
};

type Ctx = {
  stats: LabStats | null;
  latestFold: LatestFold | null;
  loaded: boolean;
  fetchError: string | null;
};

const LabPulseContext = createContext<Ctx | null>(null);

type RawStats = {
  total_folds?: number;
  refined_count?: number;
  promising_count?: number;
  discarded_count?: number;
  failed_count?: number;
  pending_count?: number;
  peptides_explored_count?: number;
  days_running?: number;
  total_cost_usd?: number | null;
};

type RawFoldItem = {
  id: number;
  slug?: string | null;
  peptide_name?: string | null;
  target_protein?: string | null;
  status?: string;
  fold_verdict?: string | null;
  modification_description?: string | null;
  created_at: string;
};

type RawFoldList = { items: RawFoldItem[] };

function adaptStats(raw: RawStats): LabStats {
  return {
    total_folds: raw.total_folds ?? 0,
    refined_count: raw.refined_count ?? 0,
    promising_count: raw.promising_count ?? 0,
    discarded_count: raw.discarded_count ?? 0,
    failed_count: raw.failed_count ?? 0,
    pending_count: raw.pending_count ?? 0,
    peptides_explored_count: raw.peptides_explored_count ?? 0,
    days_running: raw.days_running ?? 0,
    total_cost_usd:
      typeof raw.total_cost_usd === "number" ? raw.total_cost_usd : null,
  };
}

function adaptFold(raw: RawFoldItem): LatestFold {
  return {
    id: raw.id,
    slug: raw.slug ?? null,
    peptide_name: raw.peptide_name ?? null,
    target_protein: raw.target_protein ?? null,
    status: raw.status ?? "PENDING",
    fold_verdict: raw.fold_verdict ?? null,
    modification_description: raw.modification_description ?? null,
    created_at: raw.created_at,
  };
}

export function LabPulseProvider({ children }: { children: ReactNode }) {
  const [stats, setStats] = useState<LabStats | null>(null);
  const [latestFold, setLatestFold] = useState<LatestFold | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const inflightRef = useRef<AbortController | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchOnce = async () => {
      inflightRef.current?.abort();
      const ctrl = new AbortController();
      inflightRef.current = ctrl;
      try {
        const [statsRes, foldsRes] = await Promise.all([
          fetch("/api/stats", { signal: ctrl.signal, cache: "no-store" }),
          fetch("/api/folds?page=1&page_size=1&sort=newest", {
            signal: ctrl.signal,
            cache: "no-store",
          }),
        ]);
        if (!statsRes.ok) throw new Error(`stats HTTP ${statsRes.status}`);
        if (!foldsRes.ok) throw new Error(`folds HTTP ${foldsRes.status}`);
        const rawStats = (await statsRes.json()) as RawStats;
        const rawFolds = (await foldsRes.json()) as RawFoldList;
        if (cancelled) return;
        setStats(adaptStats(rawStats));
        setLatestFold(rawFolds.items?.[0] ? adaptFold(rawFolds.items[0]) : null);
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

  const value = useMemo<Ctx>(
    () => ({ stats, latestFold, loaded, fetchError }),
    [stats, latestFold, loaded, fetchError]
  );

  return (
    <LabPulseContext.Provider value={value}>
      {children}
    </LabPulseContext.Provider>
  );
}

export function useLabPulse(): Ctx {
  const v = useContext(LabPulseContext);
  if (!v) throw new Error("useLabPulse: wrap App in LabPulseProvider");
  return v;
}
