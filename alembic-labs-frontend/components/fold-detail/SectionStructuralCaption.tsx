import { SectionHeader } from "@/components/ui/SectionHeader";

interface SectionStructuralCaptionProps {
  caption: string | null;
}

export function SectionStructuralCaption({ caption }: SectionStructuralCaptionProps) {
  if (!caption) return null;
  return (
    <section className="mb-16">
      <SectionHeader index="07" title="structural caption" />
      <div className="border border-border-accent bg-bg-elevated p-5 sm:p-6 border-l-2 border-l-brand">
        <p className="text-text-primary text-body leading-relaxed whitespace-pre-line">
          {caption}
        </p>
      </div>
    </section>
  );
}
