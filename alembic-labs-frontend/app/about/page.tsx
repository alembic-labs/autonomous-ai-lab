import Link from "next/link";

import { SectionHeader } from "@/components/ui/SectionHeader";

const CYCLE_STEPS = [
  {
    agent: "RESEARCHER",
    body:
      "selects a peptide from the lab's curated registry of performance compounds and formulates a specific, testable modification hypothesis — amino acid substitution, terminal modification, stereochemical inversion.",
  },
  {
    agent: "LITERATURE",
    body:
      "reads relevant PubMed papers and bioRxiv preprints to build the scientific context — what's known, what's contested, what the modification's precedent looks like.",
  },
  {
    agent: "CLINICAL",
    body:
      "pulls bioactivity data from ChEMBL, biohacker use patterns, and known binding partners for the target receptor.",
  },
  {
    agent: "STRUCTURAL",
    body:
      "runs the modified peptide through Boltz-2 structure prediction. In borderline-confidence cases, Chai-1 cross-validates the result. The agent computes aggregation propensity, stability, BBB penetration, and half-life estimates, then evaluates whether the predicted structure supports or contradicts the hypothesis.",
  },
  {
    agent: "COMMUNICATOR",
    body:
      "synthesizes all four agent outputs into a comprehensive research report — TLDR summary, detailed mechanism analysis, structural caption, peptide profile, agent findings log, honest caveats, and full citation list.",
  },
];

const AUDIENCES = [
  {
    keyword: "BIOHACKERS",
    body:
      "People already using performance peptides who want better information about what they're injecting. The Stack Analyzer (chat at /stack) reads your protocol and flags synergies, conflicts, mechanism overlap, and timing optimization grounded in lab research. Not medical advice. Better-than-Reddit informed analysis.",
  },
  {
    keyword: "RESEARCHERS",
    body:
      "Computational biologists, medicinal chemists, and structural biology folks who want a free, growing dataset of peptide modification predictions to compare against their own work. Every fold is downloadable. Every prompt is public. Every prediction is timestamped.",
  },
  {
    keyword: "THE DESCI COMMUNITY",
    body:
      "Researchers, builders, and contributors interested in autonomous AI labs as a model for open scientific infrastructure. The lab's architecture, code, and outputs are all public. Build on top, fork it, use the data — outputs belong to whoever uses them.",
  },
  {
    keyword: "CRYPTO BUILDERS",
    body:
      "Anyone watching the AI × bio narrative who wants to participate in a real working lab rather than another whitepaper. On-chain commitment means the data isn't going anywhere.",
  },
];

const DO_NOT = [
  "synthesize compounds",
  "test in animals",
  "run clinical trials",
  "provide medical advice",
  "endorse use of research peptides",
  "claim our predictions reflect biological reality",
];

const DO_DOES = [
  "generate testable hypotheses at scale",
  "predict structures and binding properties using validated AI models",
  "publish findings open-source and on-chain",
  "flag honest caveats with every prediction",
  "surface negative results alongside positive ones",
];

const CONTACTS = [
  {
    label: "twitter",
    value: "@alembiclabs",
    href: "https://twitter.com/alembiclabs",
  },
  {
    label: "github",
    value: "github.com/alembiclabs",
    href: "https://github.com/alembiclabs",
  },
  {
    label: "email",
    value: "contact@alembic.bio",
    href: "mailto:contact@alembic.bio",
  },
];

export default function AboutPage() {
  return (
    <div>
      <h1 className="text-h1 sm:text-display font-bold uppercase tracking-wider">
        about
      </h1>
      <p className="mt-3 text-text-secondary text-body max-w-2xl leading-relaxed">
        what the lab does, who it serves, why it exists, and how it works.
      </p>

      <div className="mt-16 space-y-20 sm:space-y-28">
        {/* 01 — WHAT IS ALEMBIC LABS */}
        <section>
          <SectionHeader index="01" title="what is alembic labs" />
          <div className="space-y-4 text-text-primary text-body leading-relaxed max-w-3xl">
            <p>
              ALEMBIC LABS is an autonomous AI laboratory that researches
              performance peptides around the clock.
            </p>
            <p>
              Five specialized AI agents work as a research team. They pick a
              peptide, formulate a modification hypothesis, run structure
              prediction, evaluate the result, and publish a research report.
              The lab does not need human direction to operate.
            </p>
            <p>
              Output: an open, growing dataset of computationally tested
              peptide modifications — the kind of work that traditionally
              requires a 30-person research lab and months of effort, now
              running continuously and transparently.
            </p>
            <p>
              The lab focuses on performance peptides specifically — BPC-157,
              MOTS-c, GLP-1 analogs, semax, ipamorelin, sermorelin, and similar
              molecules used by biohackers for regeneration, longevity,
              cognition, and metabolic optimization. Not disease research. Not
              wet-lab drug discovery. A specific gap in the bio research
              landscape.
            </p>
          </div>
        </section>

        {/* 02 — WHY THIS EXISTS */}
        <section>
          <SectionHeader index="02" title="why this exists" />
          <div className="space-y-4 text-text-primary text-body leading-relaxed max-w-3xl">
            <p>
              The cost of computational biology collapsed in the last two
              years.
            </p>
            <p>
              Tools that required pharma-scale infrastructure now run through
              API calls. Boltz-2 predicts protein structures and binding
              affinities in 20 seconds. Chai-1 cross-validates results.
              Frontier reasoning models read literature, generate hypotheses,
              synthesize findings. What cost billions five years ago costs
              cents per inference today.
            </p>
            <p>
              But this capability is mostly being deployed where the funding
              is — disease research, drug discovery, traditional pharma
              targets. The molecules that millions of people actually use for
              performance, recovery, and longevity remain academically
              underexplored and structurally opaque.
            </p>
            <p>
              ALEMBIC LABS exists to fill that specific gap. To run the same
              machinery that pharma uses, but pointed at the molecules
              biohackers care about, with full transparency about what works,
              what doesn't, and what's still uncertain.
            </p>
          </div>
        </section>

        {/* 03 — WHAT THE LAB DOES */}
        <section>
          <SectionHeader index="03" title="what the lab does" />
          <p className="text-text-secondary text-body leading-relaxed max-w-3xl">
            Every distillation cycle:
          </p>
          <ol className="mt-6 space-y-6 max-w-3xl">
            {CYCLE_STEPS.map((step, idx) => (
              <li key={step.agent} className="grid grid-cols-[2.5rem_1fr] gap-4">
                <span className="text-text-muted text-data tabular-nums pt-0.5">
                  {String(idx + 1).padStart(2, "0")}/
                </span>
                <div>
                  <span className="text-brand font-bold uppercase tracking-wider text-data">
                    {step.agent}
                  </span>{" "}
                  <span className="text-text-primary text-body leading-relaxed">
                    {step.body}
                  </span>
                </div>
              </li>
            ))}
          </ol>
          <p className="mt-8 text-text-secondary text-body leading-relaxed max-w-3xl">
            The fold is then marked{" "}
            <span className="text-text-primary">REFINED</span>,{" "}
            <span className="text-text-primary">DISCARDED</span>, or{" "}
            <span className="text-text-primary">FAILED</span>. Hash logged
            on-chain. Report published.
          </p>
        </section>

        {/* 04 — WHO IT'S FOR */}
        <section>
          <SectionHeader index="04" title="who it's for" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 sm:gap-10">
            {AUDIENCES.map((a) => (
              <div
                key={a.keyword}
                className="border-l-2 border-border-accent pl-5"
              >
                <h3 className="text-h2 text-brand font-bold uppercase tracking-wider">
                  &gt; {a.keyword}
                </h3>
                <hr className="my-3 border-border-subtle" />
                <p className="text-text-secondary text-body leading-relaxed">
                  {a.body}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* 05 — HONEST DISCLAIMERS */}
        <section>
          <SectionHeader index="05" title="honest disclaimers" />
          <div className="space-y-6 text-text-primary text-body leading-relaxed max-w-3xl">
            <p>ALEMBIC LABS conducts in silico research only.</p>

            <div>
              <p className="text-text-muted text-small uppercase tracking-wider mb-2">
                we do not:
              </p>
              <ul className="space-y-1.5 text-text-secondary">
                {DO_NOT.map((item) => (
                  <li key={item} className="flex gap-3">
                    <span className="text-text-muted">—</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <p className="text-text-muted text-small uppercase tracking-wider mb-2">
                we do:
              </p>
              <ul className="space-y-1.5 text-text-secondary">
                {DO_DOES.map((item) => (
                  <li key={item} className="flex gap-3">
                    <span className="text-text-muted">—</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>

            <p className="italic text-text-secondary">
              All compounds discussed are research chemicals subject to local
              regulations. Predicted properties may not reflect real-world
              biological behavior. Every fold requires wet-lab validation
              before any clinical interpretation. The Stack Analyzer is
              informational, not medical guidance.
            </p>

            <p className="italic text-text-secondary">
              The lab discards more folds than it refines. This is the system
              working correctly. Failed experiments are data, not noise to
              hide.
            </p>
          </div>
        </section>

        {/* 06 — OPEN DATASET */}
        <section>
          <SectionHeader index="06" title="open dataset" />
          <div className="space-y-4 text-text-primary text-body leading-relaxed max-w-3xl">
            <p>
              The lab's output is an open dataset of computationally evaluated
              peptide modifications. It grows with every cycle.
            </p>
            <p>
              Every fold includes the input peptide, the modification, the
              target protein, predicted structure (PDB), confidence metrics
              (pLDDT, pTM, ipTM), peptide profile (aggregation, stability,
              BBB), full research brief, and complete citation trail.
            </p>
          </div>

          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href="/folds"
              className="btn-bracket text-small flex flex-col items-start gap-0 py-3 px-5"
            >
              <span className="flex items-center gap-2">
                <span className="text-text-muted">[</span>
                <span>↗ BROWSE FOLDS</span>
                <span className="text-text-muted">]</span>
              </span>
              <span className="text-text-muted text-small">/folds</span>
            </Link>

            <span
              aria-disabled="true"
              className="flex flex-col items-start gap-0 py-3 px-5 border border-border-subtle text-small text-text-muted cursor-not-allowed select-none"
            >
              <span className="flex items-center gap-2">
                <span>[</span>
                <span>↗ GITHUB</span>
                <span>]</span>
              </span>
              <span>publishing soon</span>
            </span>
          </div>

          <p className="mt-6 text-text-secondary text-body leading-relaxed max-w-3xl">
            CSV exports, full PDB tarballs, and a prompt archive will be
            released as the dataset matures. Every refined and discarded fold
            has its data hash committed to Solana — verifiable, tamper-evident,
            permanent.
          </p>
        </section>

        {/* 07 — CONTACT */}
        <section>
          <SectionHeader index="07" title="contact" />
          <ul className="divide-y divide-border-subtle border-y border-border-subtle">
            {CONTACTS.map((c) => (
              <li
                key={c.label}
                className="grid grid-cols-[120px_1fr_auto] items-center gap-3 py-3 text-data"
              >
                <span className="text-text-muted uppercase tracking-wider text-small">
                  {c.label}
                </span>
                <a
                  href={c.href}
                  target={c.href.startsWith("http") ? "_blank" : undefined}
                  rel={c.href.startsWith("http") ? "noreferrer" : undefined}
                  className="text-text-primary hover:text-brand"
                >
                  {c.value}
                </a>
                <span className="text-text-muted">[ ↗ ]</span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
