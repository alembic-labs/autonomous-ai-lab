import { SectionHeader } from "@/components/ui/SectionHeader";

interface TreeGroup {
  title: string;
  items: { key: string; label: string; description: string }[];
}

const GROUPS: TreeGroup[] = [
  {
    title: "reasoning layer",
    items: [
      {
        key: "claude-opus-4-7",
        label: "claude-opus-4-7",
        description: "hypothesis generation, validation reasoning",
      },
      {
        key: "claude-sonnet-4-6",
        label: "claude-sonnet-4-6",
        description: "summarization, communication",
      },
    ],
  },
  {
    title: "structure prediction",
    items: [
      { key: "boltz-2", label: "boltz-2", description: "primary structure prediction" },
      { key: "chai-1", label: "chai-1", description: "cross-validation" },
    ],
  },
  {
    title: "knowledge",
    items: [
      { key: "pubmed", label: "pubmed", description: "primary literature" },
      { key: "biorxiv", label: "biorxiv", description: "preprints" },
      { key: "uniprot", label: "uniprot", description: "target proteins" },
      { key: "chembl", label: "chembl", description: "bioactivity data" },
      {
        key: "internal-db",
        label: "internal peptide db",
        description: "curated performance peptides",
      },
    ],
  },
  {
    title: "infrastructure",
    items: [
      { key: "fastapi", label: "python + fastapi", description: "orchestration" },
      { key: "postgres", label: "postgresql", description: "experiment storage" },
      { key: "replicate", label: "replicate api", description: "ml inference" },
      {
        key: "solana",
        label: "solana (planned)",
        description: "on-chain logging",
      },
    ],
  },
];

export function StackTree() {
  return (
    <section className="mb-16">
      <SectionHeader index="03" title="the stack" />
      <div className="bg-bg-surface border border-border-subtle p-4 sm:p-8">
        <div className="space-y-6 text-data">
          {GROUPS.map((g) => (
            <div key={g.title}>
              <div className="text-text-muted uppercase tracking-wider text-small mb-2">
                {g.title}
              </div>
              <ul className="space-y-1 font-mono">
                {g.items.map((item, i) => {
                  const isLast = i === g.items.length - 1;
                  return (
                    <li key={item.key} className="flex gap-3">
                      <span className="text-text-muted whitespace-pre">
                        {isLast ? "└─" : "├─"}
                      </span>
                      <span className="grid grid-cols-1 sm:grid-cols-[200px_1fr] gap-2 sm:gap-4 flex-1">
                        <span className="text-text-primary">{item.label}</span>
                        <span className="text-text-muted">{item.description}</span>
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
