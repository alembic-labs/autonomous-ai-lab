import { SectionHeader } from "@/components/ui/SectionHeader";

interface SectionAIAnalysisProps {
  tldr?: string | null;
  detailed?: string | null;
  /**
   * Set when the orchestrator's predictability gate refused the fold
   * BEFORE Structural ran (lipid target, missing UniProt, sub-resolution
   * peptide length, etc.). When present we surface it as a callout above
   * the TLDR so the reader instantly understands that DISCARDED here
   * means "tool-limit failure", not "biological invalidation".
   */
  discardReason?: string | null;
}

export function SectionAIAnalysis({
  tldr,
  detailed,
  discardReason,
}: SectionAIAnalysisProps) {
  return (
    <section className="mb-16">
      <SectionHeader index="02" title="AI analysis" />

      <div className="space-y-6">
        {discardReason ? (
          <div className="border-l-2 border-brand bg-brand/[0.06] pl-4 py-3">
            <div className="text-brand text-[11px] uppercase tracking-wider font-bold mb-1">
              discarded by predictability gate
            </div>
            <p className="text-text-primary text-body leading-relaxed">
              {discardReason}
            </p>
            <p className="mt-2 text-text-muted text-small leading-relaxed">
              The structure-prediction pipeline (Boltz-2 + Chai-1) cannot
              adjudicate this fold — this is a tool limitation, not a
              biological refutation of the hypothesis.
            </p>
          </div>
        ) : null}

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
