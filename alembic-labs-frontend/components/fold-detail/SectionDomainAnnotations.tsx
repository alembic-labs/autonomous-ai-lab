import { SectionHeader } from "@/components/ui/SectionHeader";
import type { DomainAnnotations } from "@/lib/types";

interface SectionDomainAnnotationsProps {
  data: DomainAnnotations | null;
}

interface DomainItem {
  name?: string;
  type?: string;
  start?: number;
  end?: number;
  residues?: string;
  description?: string;
  [key: string]: unknown;
}
interface BindingSite {
  residues?: string;
  description?: string;
  [key: string]: unknown;
}
interface BindingPartner {
  name?: string;
  experiments?: number;
  uniprot?: string;
  [key: string]: unknown;
}

function pickArray<T>(...candidates: unknown[]): T[] {
  for (const c of candidates) if (Array.isArray(c)) return c as T[];
  return [];
}

export function SectionDomainAnnotations({ data }: SectionDomainAnnotationsProps) {
  const domains = pickArray<DomainItem>(
    data?.domains,
    (data as Record<string, unknown> | null)?.["structural_domains"],
    (data as Record<string, unknown> | null)?.["regions"],
  );
  const sites = pickArray<BindingSite>(
    data?.binding_sites,
    (data as Record<string, unknown> | null)?.["functional_sites"],
    (data as Record<string, unknown> | null)?.["active_sites"],
  );
  const partners = pickArray<BindingPartner>(data?.binding_partners);
  const goRaw = pickArray<string | { id?: string; term?: string }>(
    data?.gene_ontology,
    data?.go_terms,
  );
  const go = goRaw.map((g) =>
    typeof g === "string" ? g : (g.term ?? g.id ?? ""),
  ).filter(Boolean);

  const empty =
    domains.length === 0 &&
    sites.length === 0 &&
    partners.length === 0 &&
    go.length === 0;

  return (
    <section className="mb-16">
      <SectionHeader index="06" title="domain annotations" />

      {empty ? (
        <p className="text-text-muted italic text-small">
          {`// not yet annotated by clinical / structural agents`}
        </p>
      ) : (
        <div className="space-y-6">
          {domains.length > 0 ? (
            <div>
              <h4 className="text-text-muted text-[11px] uppercase tracking-wider mb-2">
                structural domains & regions
              </h4>
              <div className="border-t border-border-subtle">
                {domains.map((d, i) => {
                  const range =
                    d.start !== undefined && d.end !== undefined
                      ? `${d.start}–${d.end}`
                      : (d.residues ?? "—");
                  return (
                    <div
                      key={i}
                      className="grid grid-cols-12 gap-3 py-2 border-b border-border-subtle text-data text-text-secondary"
                    >
                      <span className="col-span-2 text-text-muted tabular-nums">
                        {range}
                      </span>
                      <span className="col-span-3 text-text-primary uppercase tracking-wider">
                        {d.type ?? d.name ?? "domain"}
                      </span>
                      <span className="col-span-7 text-text-secondary">
                        {d.description ?? d.name ?? "—"}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : null}

          {sites.length > 0 ? (
            <div>
              <h4 className="text-text-muted text-[11px] uppercase tracking-wider mb-2">
                functional / binding sites
              </h4>
              <div className="border-t border-border-subtle">
                {sites.map((s, i) => (
                  <div
                    key={i}
                    className="grid grid-cols-12 gap-3 py-2 border-b border-border-subtle text-data text-text-secondary"
                  >
                    <span className="col-span-3 text-text-muted tabular-nums">
                      {s.residues ?? "—"}
                    </span>
                    <span className="col-span-9 text-text-primary">
                      {s.description ?? "—"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {partners.length > 0 ? (
            <div>
              <h4 className="text-text-muted text-[11px] uppercase tracking-wider mb-2">
                binding partners
              </h4>
              <div className="border-t border-border-subtle">
                {partners.map((p, i) => (
                  <div
                    key={i}
                    className="grid grid-cols-12 gap-3 py-2 border-b border-border-subtle text-data text-text-secondary"
                  >
                    <span className="col-span-6 text-text-primary">{p.name ?? "—"}</span>
                    <span className="col-span-3 text-text-muted">{p.uniprot ?? ""}</span>
                    <span className="col-span-3 text-right text-text-secondary tabular-nums">
                      {p.experiments !== undefined
                        ? `${p.experiments} exp`
                        : ""}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {go.length > 0 ? (
            <div>
              <h4 className="text-text-muted text-[11px] uppercase tracking-wider mb-2">
                gene ontology
              </h4>
              <div className="flex flex-wrap gap-2">
                {go.map((term, i) => (
                  <span key={i} className="badge text-text-secondary">
                    {term}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}
