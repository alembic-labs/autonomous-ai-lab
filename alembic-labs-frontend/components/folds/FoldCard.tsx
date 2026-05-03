import Link from "next/link";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatConfidence, formatDate, clamp } from "@/lib/format";
import type { FoldListItem } from "@/lib/types";

interface FoldCardProps {
  fold: FoldListItem;
  showHypothesis?: boolean;
  className?: string;
}

const MOD_BADGE_MAX = 18;

export function FoldCard({ fold, showHypothesis = false, className = "" }: FoldCardProps) {
  // Prefer the SEO slug when the backend has generated one — falls back to
  // the numeric id for older folds.
  const ref = fold.slug ?? String(fold.id);
  return (
    <Link
      href={`/folds/${ref}`}
      className={`card card--interactive flex flex-col gap-4 ${className}`}
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-h3 text-text-primary leading-snug uppercase tracking-wide">
          {fold.title}
        </h3>
        <span className="text-text-muted text-small shrink-0">№{fold.id}</span>
      </div>

      <div className="flex flex-wrap gap-1.5">
        <span className="badge text-text-secondary border-border-accent">
          {clamp(fold.modification_description.toUpperCase(), MOD_BADGE_MAX)}
        </span>
        <span className="badge text-text-secondary border-border-accent">
          {fold.peptide_class}
        </span>
      </div>

      <div className="flex items-end justify-between gap-3">
        <div>
          <div className="text-h1 text-brand font-bold tabular-nums leading-none">
            {formatConfidence(fold.confidence_plddt)}
          </div>
          <div className="text-text-muted text-small mt-1 uppercase tracking-wider">
            confidence
          </div>
        </div>
        <div className="text-text-muted text-small text-right">
          {formatDate(fold.created_at)}
        </div>
      </div>

      {showHypothesis ? (
        <p className="text-text-secondary text-small leading-relaxed">
          <span className="text-text-muted">Hypothesis: </span>
          {clamp(fold.hypothesis, 180)}
        </p>
      ) : null}

      <div className="mt-auto pt-2 border-t border-border-subtle">
        <StatusBadge status={fold.status} />
      </div>
    </Link>
  );
}
