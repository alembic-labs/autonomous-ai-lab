import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { SectionHeader } from "@/components/ui/SectionHeader";

interface SectionResearchBriefProps {
  markdown: string | null;
  /** Optional: short executive summary string from the Communicator agent. */
  executiveSummary?: string | null;
}

export function SectionResearchBrief({
  markdown,
  executiveSummary,
}: SectionResearchBriefProps) {
  if (!markdown && !executiveSummary) return null;

  return (
    <section className="mb-16">
      <SectionHeader index="04" title="AI research brief" />

      {executiveSummary ? (
        <div className="mb-6 border border-border-accent bg-bg-elevated p-5">
          <div className="flex items-baseline gap-3 mb-2">
            <span className="text-brand text-[10px] uppercase tracking-wider font-bold">
              ●
            </span>
            <span className="text-text-muted text-[10px] uppercase tracking-wider">
              executive summary
            </span>
          </div>
          <p className="text-text-primary text-body leading-relaxed whitespace-pre-line">
            {executiveSummary}
          </p>
        </div>
      ) : null}

      {markdown ? (
        <div className="border border-border-subtle bg-bg-surface/40 p-5 sm:p-8">
          <article className="prose-mono max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
          </article>
        </div>
      ) : null}
    </section>
  );
}
