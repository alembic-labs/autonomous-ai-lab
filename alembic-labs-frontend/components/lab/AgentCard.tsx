import { HermeticSymbol } from "@/components/ui/HermeticSymbol";
import type { AgentName } from "@/lib/types";

export interface AgentCardData {
  name: AgentName;
  title: string;
  description: string;
  model: string;
  data_sources: string;
  inputs: string;
  outputs: string;
  status: "ACTIVE" | "IDLE";
  last_action: string;
  total_runs: number;
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[120px_1fr] gap-3 text-data">
      <span className="text-text-muted uppercase tracking-wider text-small">
        {label}
      </span>
      <span className="text-text-primary">{value}</span>
    </div>
  );
}

export function AgentCard({ data }: { data: AgentCardData }) {
  const active = data.status === "ACTIVE";
  return (
    <div className="card flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <HermeticSymbol agent={data.name} muted className="text-2xl" />
        <h3 className="text-h2 uppercase tracking-wider font-bold text-text-primary">
          {data.title}
        </h3>
      </div>

      <p className="text-text-secondary text-body leading-relaxed">
        {data.description}
      </p>

      <div className="space-y-1.5 pt-2 border-t border-border-subtle">
        <Row label="model" value={data.model} />
        <Row label="data sources" value={data.data_sources} />
        <Row label="inputs" value={data.inputs} />
        <Row label="outputs" value={data.outputs} />
      </div>

      <div className="space-y-1.5 pt-2 border-t border-border-subtle">
        <div className="grid grid-cols-[120px_1fr] gap-3 text-data items-center">
          <span className="text-text-muted uppercase tracking-wider text-small">
            status
          </span>
          <span className="flex items-center gap-2">
            {active ? (
              <>
                <span className="dot-active" />
                <span className="text-brand uppercase tracking-wider">active</span>
              </>
            ) : (
              <>
                <span className="dot-idle" />
                <span className="text-text-muted uppercase tracking-wider">idle</span>
              </>
            )}
          </span>
        </div>
        <Row label="last action" value={data.last_action} />
        <Row label="total runs" value={String(data.total_runs)} />
      </div>
    </div>
  );
}
