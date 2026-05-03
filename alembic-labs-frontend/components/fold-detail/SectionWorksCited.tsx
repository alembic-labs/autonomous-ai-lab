import { SectionHeader } from "@/components/ui/SectionHeader";
import type { ResearchPaper } from "@/lib/types";

interface SectionWorksCitedProps {
  papers: ResearchPaper[] | undefined;
}

export function SectionWorksCited({ papers }: SectionWorksCitedProps) {
  if (!papers || papers.length === 0) return null;
  return (
    <section className="mb-16">
      <SectionHeader index="14" title="works cited" />
      <ol className="space-y-4">
        {papers.map((p, idx) => (
          <li key={p.pmid} className="flex gap-3 text-data text-text-secondary">
            <span className="text-text-muted shrink-0">[{idx + 1}]</span>
            <div>
              <p className="text-text-primary">
                {p.authors.slice(0, 2).join(", ")}
                {p.authors.length > 2 ? " et al." : ""} ({p.year}).{" "}
                {p.title}
              </p>
              <p className="mt-1 text-text-muted">
                <span className="italic">{p.journal}</span> ·{" "}
                <a
                  href={`https://pubmed.ncbi.nlm.nih.gov/${p.pmid}/`}
                  target="_blank"
                  rel="noreferrer"
                  className="link-red"
                >
                  PubMed PMID {p.pmid} ↗
                </a>
              </p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
