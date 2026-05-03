import { ArchitectureDiagram } from "@/components/lab/ArchitectureDiagram";
import { AgentsGrid } from "@/components/lab/AgentsGrid";
import { StackTree } from "@/components/lab/StackTree";
import { LiveMetrics } from "@/components/lab/LiveMetrics";

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
          <span className="inline-flex items-center gap-2 px-2 py-0.5 text-small uppercase tracking-wider border border-brand text-brand">
            <span
              aria-hidden="true"
              className="inline-block h-1.5 w-1.5 bg-brand animate-pulse-red"
            />
            coming soon
          </span>
        </div>

        <div className="relative bg-bg border-b border-border-subtle">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/lab-3d-preview.png"
            alt="Preview render of the planned 3D laboratory floor — five lab-coated AI agents at workstations"
            className="block w-full h-auto opacity-90 select-none"
            draggable={false}
          />
          <span className="pointer-events-none absolute bottom-2 right-3 text-small uppercase tracking-wider text-text-muted">
            preview render — not live
          </span>
        </div>

        <div className="p-5 space-y-3 text-body text-text-secondary leading-relaxed">
          <p>
            Soon the lab gets a fully interactive 3D floor — a real-time
            visualization of the research apparatus you see described below.
            Each AI agent will be embodied as a workstation: click any of them
            to watch their current task unfold, inspect the inputs they're
            reading, and read the reasoning they're emitting{" "}
            <span className="text-text-primary">as it happens</span>.
          </p>
          <ul className="space-y-1.5 pt-1">
            <li className="flex gap-3">
              <span className="text-text-muted">—</span>
              <span>
                <span className="text-text-primary">Researcher's desk:</span>{" "}
                see the peptide registry pull, the modification hypothesis
                being drafted, the literature query being built.
              </span>
            </li>
            <li className="flex gap-3">
              <span className="text-text-muted">—</span>
              <span>
                <span className="text-text-primary">Structural bay:</span>{" "}
                watch Boltz-2 / Chai-1 returning the predicted complex into
                the 3D viewer in real time, with confidence metrics streaming
                onto an adjacent screen.
              </span>
            </li>
            <li className="flex gap-3">
              <span className="text-text-muted">—</span>
              <span>
                <span className="text-text-primary">Communicator's terminal:</span>{" "}
                follow the report being typed token-by-token, with each
                citation lighting up as it lands.
              </span>
            </li>
          </ul>
          <p className="text-text-muted text-small pt-2">
            The image above is a pre-production mockup. Architecture, lighting
            and agent placement are final intent — geometry and animations will
            ship as the standalone scene at{" "}
            <span className="font-mono">lab.alembic.bio</span>.
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
