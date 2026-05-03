import { SectionHeader } from "@/components/ui/SectionHeader";
import { AgentCard, type AgentCardData } from "./AgentCard";

const AGENTS: AgentCardData[] = [
  {
    name: "RESEARCHER",
    title: "researcher",
    description:
      "Formulates hypotheses, designs peptide modifications, decides research direction.",
    model: "claude-opus-4-7",
    data_sources: "PubMed, internal peptide DB",
    inputs: "peptide name, recent literature",
    outputs: "hypothesis, modified sequence",
    status: "ACTIVE",
    last_action: "selecting peptide",
    total_runs: 247,
  },
  {
    name: "LITERATURE",
    title: "literature",
    description:
      "Reads scientific literature from PubMed and bioRxiv. Synthesizes relevant findings. Builds research context.",
    model: "claude-sonnet-4-6",
    data_sources: "PubMed, bioRxiv",
    inputs: "peptide name, target protein",
    outputs: "abstract synthesis, key citations",
    status: "IDLE",
    last_action: "12 abstracts retrieved",
    total_runs: 247,
  },
  {
    name: "STRUCTURAL",
    title: "structural",
    description:
      "Runs structure predictions, evaluates fold quality, cross-validates results.",
    model: "claude-opus-4-7 + boltz-2 + chai-1",
    data_sources: "BioLM API",
    inputs: "peptide + target sequences",
    outputs: "PDB, pLDDT, pTM, ipTM, agreement",
    status: "IDLE",
    last_action: "fold completed in 5m 12s",
    total_runs: 246,
  },
  {
    name: "CLINICAL",
    title: "clinical",
    description:
      "Fetches biohacker/clinical context, ChEMBL bioactivity data, known binders, mechanism class.",
    model: "claude-sonnet-4-6",
    data_sources: "ChEMBL, UniProt, biohacker forums",
    inputs: "peptide name, target ID",
    outputs: "binders, mechanism, dosage signal",
    status: "IDLE",
    last_action: "47 ChEMBL entries pulled",
    total_runs: 246,
  },
  {
    name: "COMMUNICATOR",
    title: "communicator",
    description:
      "Synthesizes all agent outputs into the 14-section detailed report: AI analysis, research brief, peptide profile, structural caption, executive summary.",
    model: "claude-sonnet-4-6",
    data_sources: "internal pipeline state",
    inputs: "full distillation context",
    outputs: "markdown report, executive summary",
    status: "IDLE",
    last_action: "report drafted in 27s",
    total_runs: 246,
  },
];

export function AgentsGrid() {
  return (
    <section className="mb-16">
      <SectionHeader index="02" title="agents" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-5">
        {AGENTS.map((a) => (
          <AgentCard key={a.name} data={a} />
        ))}
      </div>
    </section>
  );
}
