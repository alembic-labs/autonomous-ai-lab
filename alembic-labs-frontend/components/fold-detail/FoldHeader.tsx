import Link from "next/link";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatConfidence, formatDate, formatPercent } from "@/lib/format";
import type { FoldDetail } from "@/lib/types";

interface FoldHeaderProps {
  fold: FoldDetail;
  pmid?: string;
}

export function FoldHeader({ fold, pmid }: FoldHeaderProps) {
  return (
    <header className="mb-12">
      <Link
        href="/folds"
        className="text-text-muted text-small uppercase tracking-wider hover:text-brand"
      >
        ← back to folds
      </Link>

      <div className="mt-4 flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div>
          <p className="text-text-muted text-small uppercase tracking-wider">
            distillation №{fold.id}
          </p>
          <h1 className="mt-1 text-h1 sm:text-display font-bold uppercase tracking-wider leading-tight">
            {fold.peptide_name}
            <span className="text-text-muted"> — </span>
            <span className="text-text-secondary">
              {fold.modification_description}
            </span>
          </h1>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="badge text-text-secondary border-border-accent">
              {fold.modification_description.toUpperCase()}
            </span>
            <span className="badge text-text-secondary border-border-accent">
              {fold.peptide_class}
            </span>
            {pmid ? (
              <span className="badge text-text-secondary border-border-accent">
                PMID {pmid}
              </span>
            ) : null}
            <span className="text-text-muted text-small">
              {formatDate(fold.created_at, { weekday: undefined })}
            </span>
            <StatusBadge status={fold.status} />
          </div>
        </div>

        <a
          href={`/api/folds/${fold.id}/report`}
          download
          className="btn-bracket text-small self-start"
          aria-label="Download report"
        >
          <span className="text-text-muted">[</span>
          <span>↓ download report</span>
          <span className="text-text-muted">]</span>
        </a>
      </div>

      <div className="mt-8 border border-border-accent bg-bg-surface p-5 sm:p-6 flex flex-wrap items-center justify-between gap-6">
        <div>
          <div className="text-text-muted text-small uppercase tracking-wider">
            average confidence
          </div>
          <div className="mt-2 text-[2.5rem] leading-none font-bold text-brand tabular-nums">
            {formatConfidence(fold.confidence_plddt)}
          </div>
          {fold.onchain_signature ? (
            // On-chain commitment — bind the published numbers to a public,
            // tamper-evident timestamp. Uses the server-built explorer URL
            // so the cluster (mainnet vs devnet) is correct automatically.
            <div className="mt-3 text-text-muted text-[11px] uppercase tracking-wider">
              <span aria-hidden="true">⛓ </span>
              logged on-chain ·{" "}
              <a
                href={fold.onchain_explorer_url ?? `https://solscan.io/tx/${fold.onchain_signature}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-brand hover:underline"
              >
                verify on solscan ↗
              </a>
            </div>
          ) : null}
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-8 gap-y-3 text-data">
          <div>
            <div className="text-text-muted text-small uppercase tracking-wider">
              pTM
            </div>
            <div className="text-text-primary tabular-nums">
              {fold.confidence_ptm ?? "—"}
            </div>
          </div>
          <div>
            <div className="text-text-muted text-small uppercase tracking-wider">
              ipTM
            </div>
            <div className="text-text-primary tabular-nums">
              {fold.confidence_iptm ?? "—"}
            </div>
          </div>
          <div>
            <div className="text-text-muted text-small uppercase tracking-wider">
              binding Δ
            </div>
            <div className="text-text-primary tabular-nums">
              {formatPercent(fold.predicted_binding_change)}
            </div>
          </div>
          <div>
            <div className="text-text-muted text-small uppercase tracking-wider">
              agreement
            </div>
            <div className="text-text-primary tabular-nums">
              {fold.agreement_score ?? "—"}
            </div>
          </div>
          <div>
            <div className="text-text-muted text-small uppercase tracking-wider">
              target
            </div>
            <div className="text-text-primary">{fold.target_protein ?? "—"}</div>
          </div>
          <div>
            <div className="text-text-muted text-small uppercase tracking-wider">
              uniprot
            </div>
            <div className="text-text-primary">
              {fold.target_uniprot_id ?? "—"}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
