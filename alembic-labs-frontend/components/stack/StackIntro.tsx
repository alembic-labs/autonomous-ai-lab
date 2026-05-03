"use client";

import { SectionHeader } from "@/components/ui/SectionHeader";
import { Button } from "@/components/ui/Button";
import { EXAMPLE_STACK } from "@/lib/prompts";

interface StackIntroProps {
  onTryExample: () => void;
  onStartFresh: () => void;
}

const POINTS = [
  "mechanism overlap and synergies",
  "potential conflicts and risk flags",
  "timing optimization",
  "comparison to research from our lab",
  "honest caveats",
];

export function StackIntro({ onTryExample, onStartFresh }: StackIntroProps) {
  return (
    <div>
      <section className="mb-12">
        <SectionHeader index="01" title="how to use" />
        <p className="text-text-secondary text-body leading-relaxed">
          describe your stack — peptides, dosages, timing.
          <br />
          the analyzer will check for:
        </p>
        <ul className="mt-4 space-y-2 text-text-primary text-body">
          {POINTS.map((p) => (
            <li key={p} className="flex gap-3">
              <span className="text-text-muted">─</span>
              <span>{p}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="mb-12">
        <SectionHeader index="02" title="example stack" />
        <div className="bg-bg-surface border border-border-subtle p-4 sm:p-6">
          <pre className="text-data text-text-primary whitespace-pre overflow-x-auto">
{EXAMPLE_STACK}
          </pre>
        </div>
        <div className="mt-5 flex flex-wrap gap-3">
          <Button type="button" onClick={onTryExample}>
            try example
          </Button>
          <Button type="button" onClick={onStartFresh}>
            start fresh
          </Button>
        </div>
      </section>
    </div>
  );
}
