import { SectionHeader } from "@/components/ui/SectionHeader";

const DIAGRAM = String.raw`                ┌──────────────────────────────┐
                │   DISTILLATION CYCLE         │
                │   trigger every 45min        │
                └─────────────┬────────────────┘
                              │
    ┌───────────┬─────────────┼─────────────┬───────────┐
    ▼           ▼             ▼             ▼           ▼
┌─────────┐ ┌─────────┐  ┌─────────┐  ┌─────────┐ ┌─────────┐
│RESEARCHR│ │LITERATUR│  │STRUCTRAL│  │CLINICAL │ │COMMUNICR│
│ ● ACTIVE│ │ ◯ idle  │  │ ◯ idle  │  │ ◯ idle  │ │ ◯ idle  │
└────┬────┘ └────┬────┘  └────┬────┘  └────┬────┘ └────┬────┘
     │           │            │            │           │
     ▼           ▼            ▼            ▼           ▼
┌─────────┐ ┌─────────┐  ┌─────────┐  ┌─────────┐ ┌─────────┐
│PEPTIDE  │ │ PUBMED  │  │ BOLTZ-2 │  │ CHEMBL  │ │ POSTGRES│
│   DB    │ │ BIORXIV │  │ CHAI-1  │  │UNIPROT  │ │   API   │
└─────────┘ └─────────┘  └─────────┘  └─────────┘ └─────────┘`;

function colorize(line: string): React.ReactNode {
  // Highlight the active researcher block in plasma red
  if (line.includes("RESEARCHR") || line.includes("● ACTIVE")) {
    return <span className="text-brand">{line}</span>;
  }
  return line;
}

export function ArchitectureDiagram() {
  const lines = DIAGRAM.split("\n");
  return (
    <section className="mb-16">
      <SectionHeader index="01" title="architecture" />
      <div className="bg-bg-surface border border-border-subtle p-3 sm:p-6 overflow-x-auto">
        <pre
          className="text-data leading-tight whitespace-pre"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          {lines.map((line, i) => (
            <span key={i} className="block">
              {colorize(line)}
            </span>
          ))}
        </pre>
      </div>
    </section>
  );
}
