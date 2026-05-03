import { SectionHeader } from "@/components/ui/SectionHeader";
import { formatNumber } from "@/lib/format";
import { getLabStats } from "@/lib/api";
import type { LabStats as LabStatsType } from "@/lib/types";

export const dynamic = "force-dynamic";

interface StatBlockProps {
  value: string;
  label: string;
  sublabel?: string;
}

function StatBlock({ value, label, sublabel }: StatBlockProps) {
  return (
    <div>
      <div className="text-[2.25rem] sm:text-[2.75rem] leading-none font-bold text-brand tabular-nums">
        {value}
      </div>
      <div className="mt-3 text-text-muted text-small uppercase tracking-wider">
        {label}
      </div>
      {sublabel ? (
        <div className="text-text-muted text-small uppercase tracking-wider">
          {sublabel}
        </div>
      ) : null}
    </div>
  );
}

const FALLBACK_STATS: LabStatsType = {
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
};

export async function LabStats() {
  let s: LabStatsType = FALLBACK_STATS;
  try {
    s = await getLabStats();
  } catch {
    /* keep fallback */
  }
  return (
    <section className="mb-16">
      <SectionHeader index="02" title="lab status" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-8 sm:gap-10">
        <StatBlock value={formatNumber(s.total_folds)} label="total folds" />
        <StatBlock value={s.uptime_human} label="uptime" />
        <StatBlock
          value={formatNumber(s.peptides_explored_count)}
          label="peptides"
          sublabel="explored"
        />
        <StatBlock
          value={`${s.agents_active}/${s.agents_total}`}
          label="agents"
          sublabel="active"
        />
      </div>
    </section>
  );
}
