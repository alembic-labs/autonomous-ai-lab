import { ArchitectureDiagram } from "@/components/lab/ArchitectureDiagram";
import { AgentsGrid } from "@/components/lab/AgentsGrid";
import { StackTree } from "@/components/lab/StackTree";
import { LiveMetrics } from "@/components/lab/LiveMetrics";

const LAB_3D_URL =
  process.env.NEXT_PUBLIC_LAB_3D_URL || "https://lab.alembic.bio";

export default function LabPage() {
  return (
    <div>
      <h1 className="text-h1 sm:text-display font-bold uppercase tracking-wider">
        the lab
      </h1>
      <p className="mt-3 text-text-secondary text-body max-w-2xl leading-relaxed">
        real-time view of the autonomous research apparatus. five AI agents
        work continuously, validated by Boltz-2 and Chai-1.
      </p>

      <section className="mt-8 border border-border-subtle bg-bg-surface overflow-hidden">
        <div className="flex items-center justify-between border-b border-border-subtle px-4 py-2">
          <span className="text-small uppercase tracking-wider text-text-secondary">
            3d floor
          </span>
          <a
            href={LAB_3D_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 px-2 py-0.5 text-small uppercase tracking-wider border border-brand text-brand hover:bg-brand hover:text-bg transition-colors"
          >
            <span
              aria-hidden="true"
              className="inline-block h-1.5 w-1.5 bg-brand animate-pulse-red"
            />
            open fullscreen ↗
          </a>
        </div>

        <div className="relative bg-bg border-b border-border-subtle">
          {/*
            Live embed of the standalone 3D lab. Cross-origin iframe is
            fine here — lab.alembic.bio sets no X-Frame-Options (nginx
            default) so the embed loads, and the lab's /api/* calls go
            same-origin via the Caddy proxy on lab.alembic.bio so we
            don't need to relax CORS just for the iframe.
          */}
          <div className="relative w-full" style={{ aspectRatio: "16 / 9" }}>
            <iframe
              src={LAB_3D_URL}
              title="Alembic 3D laboratory — live floor"
              className="absolute inset-0 w-full h-full block bg-bg"
              allow="fullscreen; accelerometer; gyroscope"
              loading="lazy"
              referrerPolicy="no-referrer-when-downgrade"
            />
          </div>
          <span className="pointer-events-none absolute bottom-2 right-3 text-small uppercase tracking-wider text-text-muted bg-bg/70 px-2 py-0.5">
            live · click an agent
          </span>
        </div>

        <div className="p-5 space-y-3 text-body text-text-secondary leading-relaxed">
          <p>
            What you see above is the live 3D floor — a real-time visualization
            of the research apparatus described below. Each AI agent is embodied
            as a station: click any of them to read what they're doing{" "}
            <span className="text-text-primary">right now</span>.
          </p>
          <ul className="space-y-1.5 pt-1">
            <li className="flex gap-3">
              <span className="text-text-muted">—</span>
              <span>
                <span className="text-text-primary">Researcher's desk:</span>{" "}
                pulls a peptide from the registry and drafts the modification
                hypothesis the rest of the cycle is built around.
              </span>
            </li>
            <li className="flex gap-3">
              <span className="text-text-muted">—</span>
              <span>
                <span className="text-text-primary">Structural bay:</span>{" "}
                runs Boltz-2 (and adaptively Chai-1) to score the predicted
                complex, then assigns the verdict — REFINED, PROMISING or
                DISCARDED — based on the structural metrics alone.
              </span>
            </li>
            <li className="flex gap-3">
              <span className="text-text-muted">—</span>
              <span>
                <span className="text-text-primary">Communicator's terminal:</span>{" "}
                writes the public report and commits the on-chain hash so the
                full provenance is verifiable on Solana.
              </span>
            </li>
          </ul>
          <p className="text-text-muted text-small pt-2">
            Standalone fullscreen view at{" "}
            <a
              href={LAB_3D_URL}
              target="_blank"
              rel="noreferrer"
              className="font-mono text-brand hover:underline"
            >
              lab.alembic.bio ↗
            </a>
            . The iframe above polls the same backend every 10 seconds.
          </p>
        </div>
      </section>

      <div className="mt-12">
        <ArchitectureDiagram />
        <AgentsGrid />
        <StackTree />
        <LiveMetrics />
      </div>
    </div>
  );
}
