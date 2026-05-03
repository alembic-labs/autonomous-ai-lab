"use client";

import { useEffect, useState } from "react";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { getAgentsStatus } from "@/lib/api";
import { formatUtcTime } from "@/lib/format";
import type { AgentStatus } from "@/lib/types";

const AGENT_LABELS: Record<string, string> = {
  RESEARCHER: "RESEARCHER ",
  LITERATURE: "LITERATURE ",
  STRUCTURAL: "STRUCTURAL ",
  CLINICAL: "CLINICAL   ",
  COMMUNICATOR: "COMMUNICATR",
};

const ORDER = ["RESEARCHER", "LITERATURE", "STRUCTURAL", "CLINICAL", "COMMUNICATOR"];

interface LiveStatusProps {
  /** Auto-refresh interval (ms). 5s by default. Set to 0 to disable. */
  refreshIntervalMs?: number;
}

function sortAgents(items: AgentStatus[]): AgentStatus[] {
  return [...items].sort(
    (a, b) => ORDER.indexOf(a.agent_name) - ORDER.indexOf(b.agent_name),
  );
}

export function LiveStatus({ refreshIntervalMs = 5000 }: LiveStatusProps) {
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [now, setNow] = useState<string>(formatUtcTime(new Date().toISOString()));

  useEffect(() => {
    const tick = () => setNow(formatUtcTime(new Date().toISOString()));
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const data = await getAgentsStatus();
        if (alive) setAgents(sortAgents(data));
      } catch {
        /* network blip — keep previous frame */
      }
    };
    load();
    if (refreshIntervalMs <= 0) return () => {
      alive = false;
    };
    const id = window.setInterval(load, refreshIntervalMs);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, [refreshIntervalMs]);

  const active = agents.find((a) => a.status === "ACTIVE");
  const activeFoldId = active?.current_fold_id ?? null;

  return (
    <section className="mb-16">
      <SectionHeader
        index="01"
        title="currently distilling"
        trailing={
          <span className="flex items-center gap-2">
            {activeFoldId !== null ? (
              <span className="text-text-secondary">fold №{activeFoldId}</span>
            ) : (
              <span className="text-text-muted">idle</span>
            )}
            <span className="inline-flex items-center gap-1.5 text-brand">
              <span className={active ? "dot-active" : "dot-idle"} />
              {active ? "live" : "—"}
            </span>
            <span className="text-text-muted hidden sm:inline">{now}</span>
          </span>
        }
      />

      <div className="bg-bg-surface border border-border-subtle p-4 sm:p-6">
        <ul className="space-y-2 font-mono text-data">
          {(agents.length > 0
            ? agents
            : ORDER.map<AgentStatus>((name) => ({
                agent_name: name as AgentStatus["agent_name"],
                status: "IDLE",
                current_task: null,
                current_fold_id: null,
                last_active_at: new Date().toISOString(),
              }))
          ).map((a) => {
            const label = AGENT_LABELS[a.agent_name] ?? a.agent_name;
            const isActive = a.status === "ACTIVE";
            return (
              <li
                key={a.agent_name}
                className="flex items-center gap-3 sm:gap-5"
              >
                <span className="text-text-muted whitespace-pre">[</span>
                <span
                  className={`whitespace-pre uppercase tracking-wider ${
                    isActive ? "text-brand" : "text-text-secondary"
                  }`}
                >
                  {label}
                </span>
                <span className="text-text-muted whitespace-pre">]</span>
                <span className="flex items-center gap-2 w-24 sm:w-28 shrink-0">
                  {isActive ? (
                    <>
                      <span className="dot-active" />
                      <span className="text-brand text-small uppercase tracking-wider">
                        active
                      </span>
                    </>
                  ) : (
                    <>
                      <span className="dot-idle" />
                      <span className="text-text-muted text-small uppercase tracking-wider">
                        idle
                      </span>
                    </>
                  )}
                </span>
                <span
                  className={`text-small truncate ${
                    isActive ? "text-text-primary" : "text-text-muted"
                  }`}
                >
                  {a.current_task ?? "—"}
                </span>
              </li>
            );
          })}
        </ul>

        <div className="mt-5 pt-4 border-t border-border-subtle grid grid-cols-1 sm:grid-cols-2 gap-2 text-data">
          <div className="flex gap-3">
            <span className="text-text-muted uppercase tracking-wider w-32 shrink-0">
              latest action
            </span>
            <span className="text-text-secondary">
              {active?.current_task ?? "—"}
            </span>
          </div>
          <div className="flex gap-3 sm:justify-end">
            <span className="text-text-muted uppercase tracking-wider sm:hidden w-32 shrink-0">
              at
            </span>
            <span className="text-text-muted">{now}</span>
          </div>
          <div className="flex gap-3">
            <span className="text-text-muted uppercase tracking-wider w-32 shrink-0">
              current fold
            </span>
            <span className="text-text-primary">
              {activeFoldId !== null ? `№${activeFoldId}` : "—"}
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
