import { SectionHeader } from "@/components/ui/SectionHeader";
import type { AgentName, AgentTraceItem } from "@/lib/types";

interface SectionAgentFindingsProps {
  trace: AgentTraceItem[];
}

const AGENT_GLYPH: Record<AgentName, string> = {
  RESEARCHER: "☿",
  LITERATURE: "🜍",
  STRUCTURAL: "🜔",
  CLINICAL: "🜂",
  COMMUNICATOR: "🜄",
};

const AGENT_COLOR: Record<AgentName, string> = {
  RESEARCHER: "#ff3344",
  LITERATURE: "#a890ff",
  STRUCTURAL: "#44dd88",
  CLINICAL: "#ffcc44",
  COMMUNICATOR: "#7ec6ff",
};

const STATUS_COLOR: Record<AgentTraceItem["status"], string> = {
  RUNNING: "#ffcc44",
  COMPLETED: "#44dd88",
  FAILED: "#ff3344",
};

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d
    .toISOString()
    .replace("T", " ")
    .replace(/\.\d+Z$/, " UTC");
}

function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds - m * 60);
  return `${m}m ${s}s`;
}

export function SectionAgentFindings({ trace }: SectionAgentFindingsProps) {
  if (!trace || trace.length === 0) {
    return (
      <section className="mb-16">
        <SectionHeader index="11" title="agent findings" />
        <p className="text-text-muted italic text-small">
          {`// no agent runs recorded`}
        </p>
      </section>
    );
  }

  const lastUpdated = trace
    .map((t) => t.finished_at ?? t.started_at)
    .filter((v): v is string => Boolean(v))
    .sort()
    .pop();

  const counts = trace.reduce<Record<string, number>>((acc, t) => {
    acc[t.agent_name] = (acc[t.agent_name] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <section className="mb-16">
      <SectionHeader index="11" title="agent findings" />

      <div className="flex flex-wrap items-center justify-between gap-3 mb-4 text-text-muted text-small">
        <span>{trace.length} findings</span>
        <span>
          last updated:{" "}
          <span className="text-text-secondary">
            {formatDateTime(lastUpdated ?? null)}
          </span>
        </span>
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-2 mb-6 text-[11px] uppercase tracking-wider text-text-muted">
        {Object.entries(counts).map(([name, n]) => {
          const color = AGENT_COLOR[name as AgentName] ?? "#a8a8a8";
          return (
            <span key={name} className="flex items-center gap-2">
              <span
                className="inline-block w-2 h-2"
                style={{ background: color }}
              />
              {name.toLowerCase()}: {n}
            </span>
          );
        })}
      </div>

      <div className="space-y-4">
        {trace.map((t, i) => {
          const color = AGENT_COLOR[t.agent_name] ?? "#a8a8a8";
          const statusColor = STATUS_COLOR[t.status];
          return (
            <div
              key={i}
              className="border border-border-subtle bg-bg-surface relative"
              style={{ borderLeftColor: color, borderLeftWidth: 2 }}
            >
              <div className="flex flex-wrap items-baseline justify-between gap-3 px-5 pt-4 pb-2 border-b border-border-subtle">
                <div className="flex items-baseline gap-3">
                  <span style={{ color }} className="text-[14px] leading-none">
                    {AGENT_GLYPH[t.agent_name] ?? "·"}
                  </span>
                  <span
                    className="text-[12px] uppercase tracking-wider font-bold"
                    style={{ color }}
                  >
                    {t.agent_name} agent
                  </span>
                  <span className="text-text-muted text-[10px] uppercase tracking-wider">
                    {t.model_used}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-[10px] uppercase tracking-wider text-text-muted">
                  <span>{formatDateTime(t.started_at)}</span>
                  <span>· {formatDuration(t.duration_seconds)}</span>
                  <span style={{ color: statusColor }}>● {t.status}</span>
                </div>
              </div>
              <div className="px-5 py-4 text-text-primary text-body leading-relaxed whitespace-pre-line">
                {t.summary ?? (
                  <span className="text-text-muted italic">
                    {`// no summary recorded`}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
