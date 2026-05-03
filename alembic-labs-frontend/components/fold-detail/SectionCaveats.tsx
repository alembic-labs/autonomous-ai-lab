import { SectionHeader } from "@/components/ui/SectionHeader";

interface SectionCaveatsProps {
  caveats: string[] | null | undefined;
}

export function SectionCaveats({ caveats }: SectionCaveatsProps) {
  const items = caveats ?? [
    "in silico prediction only — requires wet lab validation",
    "single-run prediction (not ensembled)",
    "predicted properties may not reflect biological reality",
    "this is research, not medical advice",
    "modified peptides have not been synthesized or tested",
  ];
  return (
    <section className="mb-16">
      <SectionHeader index="12" title="caveats" />
      <ul className="space-y-2 text-text-secondary italic">
        {items.map((c, i) => (
          <li key={i} className="flex gap-3">
            <span className="text-text-muted">─</span>
            <span>{c}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
