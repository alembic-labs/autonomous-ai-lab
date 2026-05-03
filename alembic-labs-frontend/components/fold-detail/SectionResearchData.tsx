import { SectionHeader } from "@/components/ui/SectionHeader";
import type { KnownActivity } from "@/lib/types";

interface SectionResearchDataProps {
  knownActivity: KnownActivity | null;
  biohackerUse: string | null;
  mechanismClass: string | null;
}

interface CardProps {
  label: string;
  index: string;
  children: React.ReactNode;
}

function Card({ label, index, children }: CardProps) {
  return (
    <div className="border border-border-subtle bg-bg-surface p-5 sm:p-6 relative">
      <div className="flex items-baseline gap-3 mb-3">
        <span className="text-text-muted text-[11px] uppercase tracking-wider">
          {index}
        </span>
        <h3 className="text-text-primary text-[13px] uppercase tracking-wider font-bold">
          {label}
        </h3>
      </div>
      <div className="text-body text-text-primary leading-relaxed space-y-2">
        {children}
      </div>
    </div>
  );
}

function Empty() {
  return (
    <p className="text-text-muted italic text-small">
      {`// not yet provided by clinical agent`}
    </p>
  );
}

function KnownActivityBody({ data }: { data: KnownActivity }) {
  const target = (data.primary_target as string | undefined) ?? null;
  const kd = data.affinity_kd_nm ?? data.kd_nm ?? null;
  const pchembl = data.pchembl ?? null;
  const summary = (data.potency_summary as string | undefined) ?? null;
  const receptor = (data.receptor_class as string | undefined) ?? null;
  const source = (data.source as string | undefined) ?? null;
  const notes = (data.notes as string | undefined) ?? null;

  return (
    <div className="space-y-2">
      {target ? (
        <Row label="primary target" value={target} />
      ) : null}
      {receptor ? <Row label="receptor class" value={receptor} /> : null}
      {kd !== null && kd !== undefined ? (
        <Row label="Kd (nM)" value={String(kd)} mono />
      ) : null}
      {pchembl !== null && pchembl !== undefined ? (
        <Row label="pChEMBL" value={String(pchembl)} mono />
      ) : null}
      {summary ? <p className="text-text-secondary">{summary}</p> : null}
      {notes ? <p className="text-text-muted text-small">{notes}</p> : null}
      {source ? (
        <p className="text-text-muted text-[11px] uppercase tracking-wider">
          source · {source}
        </p>
      ) : null}
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-4 border-b border-border-subtle/60 pb-1">
      <span className="text-text-muted text-small uppercase tracking-wider">
        {label}
      </span>
      <span
        className={`text-text-primary text-small ${mono ? "tabular-nums" : ""}`}
      >
        {value}
      </span>
    </div>
  );
}

export function SectionResearchData({
  knownActivity,
  biohackerUse,
  mechanismClass,
}: SectionResearchDataProps) {
  return (
    <section className="mb-16">
      <SectionHeader index="03" title="research data" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card label="known activity" index="A">
          {knownActivity ? <KnownActivityBody data={knownActivity} /> : <Empty />}
        </Card>
        <Card label="biohacker use" index="B">
          {biohackerUse ? (
            <div className="space-y-2 whitespace-pre-line text-text-secondary">
              {biohackerUse}
            </div>
          ) : (
            <Empty />
          )}
        </Card>
        <Card label="mechanism class" index="C">
          {mechanismClass ? (
            <div className="text-text-primary text-[15px] font-bold uppercase tracking-wider">
              {mechanismClass}
            </div>
          ) : (
            <Empty />
          )}
        </Card>
      </div>
    </section>
  );
}
