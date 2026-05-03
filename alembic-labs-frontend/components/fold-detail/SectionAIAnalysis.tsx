import { SectionHeader } from "@/components/ui/SectionHeader";

interface SectionAIAnalysisProps {
  tldr?: string | null;
  detailed?: string | null;
}

export function SectionAIAnalysis({ tldr, detailed }: SectionAIAnalysisProps) {
  return (
    <section className="mb-16">
      <SectionHeader index="02" title="AI analysis" />

      <div className="space-y-6">
        <div>
          <h3 className="text-text-muted text-small uppercase tracking-wider mb-2">
            tldr
          </h3>
          <div className="border-l-2 border-brand pl-4 py-1 bg-bg-surface/40">
            <p className="text-text-primary text-body leading-relaxed">
              {tldr ?? "—"}
            </p>
          </div>
        </div>

        <div>
          <h3 className="text-text-muted text-small uppercase tracking-wider mb-2">
            detailed analysis
          </h3>
          <div className="space-y-3 text-text-primary text-body leading-relaxed">
            {(detailed ?? "—").split(/\n\n+/).map((para, i) => (
              <p key={i}>{para}</p>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
