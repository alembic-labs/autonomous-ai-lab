import { SectionHeader } from "@/components/ui/SectionHeader";
import type { KnownBinder } from "@/lib/types";

interface SectionKnownBindersProps {
  binders: KnownBinder[] | null;
}

export function SectionKnownBinders({ binders }: SectionKnownBindersProps) {
  return (
    <section className="mb-16">
      <SectionHeader index="09" title="known binders" />

      {!binders || binders.length === 0 ? (
        <p className="text-text-muted italic text-small">
          {`// no ChEMBL binders found for this target`}
        </p>
      ) : (
        <div className="border-t border-border-subtle">
          {binders.map((b, i) => (
            <a
              key={i}
              href={`https://www.ebi.ac.uk/chembl/compound_report_card/${b.chembl_id}/`}
              target="_blank"
              rel="noreferrer"
              className="grid grid-cols-12 gap-3 py-3 px-1 border-b border-border-subtle text-data hover:bg-bg-surface transition-colors group"
            >
              <span className="col-span-12 sm:col-span-4 text-brand group-hover:text-brand-glow tabular-nums uppercase tracking-wider">
                {b.chembl_id} ↗
              </span>
              <span className="col-span-6 sm:col-span-4 text-text-primary tabular-nums">
                Kd:{" "}
                <span className="text-text-muted">
                  {Number.isFinite(b.kd_nM) && b.kd_nM > 0
                    ? `${b.kd_nM.toFixed(2)} nM`
                    : "—"}
                </span>
              </span>
              <span className="col-span-6 sm:col-span-4 text-text-secondary tabular-nums">
                pChEMBL:{" "}
                <span className="text-text-muted">
                  {Number.isFinite(b.pchembl) && b.pchembl > 0
                    ? b.pchembl.toFixed(2)
                    : "—"}
                </span>
              </span>
            </a>
          ))}
        </div>
      )}
    </section>
  );
}
