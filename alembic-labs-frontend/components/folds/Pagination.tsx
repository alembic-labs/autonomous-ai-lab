import Link from "next/link";

interface PaginationProps {
  page: number;
  totalPages: number;
  /** Base path WITHOUT trailing query string, e.g. "/folds". */
  basePath: string;
  /** Existing query params to preserve (excluding `page`). */
  query?: Record<string, string | undefined>;
  className?: string;
}

function buildPageList(page: number, total: number): (number | "…")[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }
  const out: (number | "…")[] = [1];
  const left = Math.max(2, page - 1);
  const right = Math.min(total - 1, page + 1);
  if (left > 2) out.push("…");
  for (let i = left; i <= right; i += 1) out.push(i);
  if (right < total - 1) out.push("…");
  out.push(total);
  return out;
}

function buildHref(
  basePath: string,
  query: Record<string, string | undefined> | undefined,
  page: number,
): string {
  const qs = new URLSearchParams();
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (k === "page") continue;
      if (typeof v === "string" && v) qs.set(k, v);
    }
  }
  qs.set("page", String(page));
  return `${basePath}?${qs.toString()}`;
}

export function Pagination({
  page,
  totalPages,
  basePath,
  query,
  className = "",
}: PaginationProps) {
  if (totalPages <= 1) return null;
  const pages = buildPageList(page, totalPages);
  const hasPrev = page > 1;
  const hasNext = page < totalPages;

  const linkBase =
    "px-3 py-1.5 text-small uppercase tracking-wider border border-transparent transition-colors";
  const inactive = "text-text-secondary hover:text-brand";
  const active = "text-brand border-brand";
  const disabled = "text-text-subtle cursor-not-allowed";

  return (
    <nav
      aria-label="Pagination"
      className={`flex flex-wrap items-center gap-1 ${className}`}
    >
      {hasPrev ? (
        <Link
          href={buildHref(basePath, query, page - 1)}
          className={`${linkBase} ${inactive}`}
        >
          [ &lt; prev ]
        </Link>
      ) : (
        <span className={`${linkBase} ${disabled}`}>[ &lt; prev ]</span>
      )}

      {pages.map((p, idx) =>
        p === "…" ? (
          <span
            key={`gap-${idx}`}
            className={`${linkBase} text-text-muted`}
            aria-hidden
          >
            …
          </span>
        ) : p === page ? (
          <span
            key={p}
            className={`${linkBase} ${active}`}
            aria-current="page"
          >
            {String(p).padStart(2, "0")}
          </span>
        ) : (
          <Link
            key={p}
            href={buildHref(basePath, query, p)}
            className={`${linkBase} ${inactive}`}
          >
            {String(p).padStart(2, "0")}
          </Link>
        ),
      )}

      {hasNext ? (
        <Link
          href={buildHref(basePath, query, page + 1)}
          className={`${linkBase} ${inactive}`}
        >
          [ next &gt; ]
        </Link>
      ) : (
        <span className={`${linkBase} ${disabled}`}>[ next &gt; ]</span>
      )}
    </nav>
  );
}
