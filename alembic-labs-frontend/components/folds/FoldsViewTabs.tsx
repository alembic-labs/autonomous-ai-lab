"use client";

import Link from "next/link";

interface FoldsViewTabsProps {
  view: "featured" | "all";
  /** Stats for the count badges. ``featuredCount`` = REFINED + PROMISING. */
  featuredCount: number;
  totalCount: number;
}

/**
 * Default landing on /folds is now ``featured`` — REFINED + PROMISING
 * only, ranked REFINED-first by confidence. The full archive (including
 * DISCARDED) stays one click away on the ``all`` tab. This recalibrates
 * the catalog so visitors see actual discoveries first, while keeping
 * the lab's transparency posture intact (everything is still browsable).
 */
export function FoldsViewTabs({
  view,
  featuredCount,
  totalCount,
}: FoldsViewTabsProps) {
  return (
    <div className="flex items-end justify-between gap-3 border-b border-border-subtle pb-3 mb-6">
      <div className="flex items-end gap-1">
        <Tab
          href="/folds"
          label="featured"
          count={featuredCount}
          active={view === "featured"}
          tooltip="REFINED + PROMISING — the lab's actual discoveries, ranked by confidence."
        />
        <Tab
          href="/folds?view=all"
          label="all"
          count={totalCount}
          active={view === "all"}
          tooltip="Full archive including DISCARDED and FAILED folds — for transparency and audit."
        />
      </div>
      {view === "featured" ? (
        <span className="text-text-muted text-small italic hidden sm:inline">
          curated · DISCARDED hidden
        </span>
      ) : (
        <span className="text-text-muted text-small italic hidden sm:inline">
          full archive · {totalCount - featuredCount} non-featured included
        </span>
      )}
    </div>
  );
}

function Tab({
  href,
  label,
  count,
  active,
  tooltip,
}: {
  href: string;
  label: string;
  count: number;
  active: boolean;
  tooltip: string;
}) {
  return (
    <Link
      href={href}
      title={tooltip}
      className={`px-3 sm:px-4 py-2 text-small uppercase tracking-wider border-b-2 -mb-[1px] transition-colors ${
        active
          ? "border-brand text-text-primary"
          : "border-transparent text-text-muted hover:text-text-secondary"
      }`}
    >
      <span>{label}</span>
      <span
        className={`ml-2 tabular-nums text-[10px] ${
          active ? "text-brand" : "text-text-muted"
        }`}
      >
        {count}
      </span>
    </Link>
  );
}
