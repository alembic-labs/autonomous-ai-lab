import { SectionHeader } from "@/components/ui/SectionHeader";
import { FoldsFilter } from "@/components/folds/FoldsFilter";
import { FoldsCatalog } from "@/components/folds/FoldsCatalog";
import { FoldsViewTabs } from "@/components/folds/FoldsViewTabs";
import { Pagination } from "@/components/folds/Pagination";
import { listFolds, type FoldsQuery } from "@/lib/api";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 12;

interface FoldsPageProps {
  searchParams: {
    search?: string;
    peptide_class?: string;
    status?: string;
    min_confidence?: string;
    sort?: string;
    view?: string;
    page?: string;
  };
}

const ALLOWED_SORTS = new Set([
  "newest",
  "oldest",
  "highest_confidence",
  "lowest_confidence",
]);

function normalizeSort(value: string | undefined): FoldsQuery["sort"] {
  if (value && ALLOWED_SORTS.has(value)) return value as FoldsQuery["sort"];
  // map legacy ui values
  if (value === "confidence_desc") return "highest_confidence";
  if (value === "confidence_asc") return "lowest_confidence";
  return "newest";
}

function normalizeView(value: string | undefined): "featured" | "all" {
  if (value === "all") return "all";
  // Default — including unset, "featured", or anything unknown — is the
  // curated front page. The audit established that DISCARDED ≠ disproved
  // but visually they shouldn't sit next to genuine discoveries.
  return "featured";
}

export default async function FoldsPage({ searchParams }: FoldsPageProps) {
  const view = normalizeView(searchParams.view);
  const page = Math.max(1, parseInt(searchParams.page ?? "1", 10) || 1);
  const minConfidence = searchParams.min_confidence
    ? Math.max(0, Math.min(1, parseFloat(searchParams.min_confidence)))
    : undefined;

  const buildQuery = (override?: Partial<FoldsQuery>): FoldsQuery => ({
    peptide_class: searchParams.peptide_class,
    // Featured implicitly fixes status — explicit status filter is for "all".
    status: view === "all" ? searchParams.status : undefined,
    search: searchParams.search?.trim() || undefined,
    min_confidence: Number.isFinite(minConfidence) ? minConfidence : undefined,
    sort: view === "featured" ? undefined : normalizeSort(searchParams.sort),
    view,
    page,
    page_size: PAGE_SIZE,
    ...override,
  });

  let response;
  try {
    response = await listFolds(buildQuery());
  } catch {
    response = {
      items: [],
      total: 0,
      page: 1,
      page_size: PAGE_SIZE,
      total_pages: 1,
    };
  }

  // Tab counts — fetch a 1-row page in each view just to read the
  // ``total`` header. Cheap (the backend pages anyway) and keeps the
  // counts always-fresh on every visit.
  let featuredTotal = view === "featured" ? response.total : 0;
  let archiveTotal = view === "all" ? response.total : 0;
  try {
    if (view !== "featured") {
      const r = await listFolds({ view: "featured", page: 1, page_size: 1 });
      featuredTotal = r.total;
    }
    if (view !== "all") {
      const r = await listFolds({ view: "all", page: 1, page_size: 1 });
      archiveTotal = r.total;
    }
  } catch {
    // Counts are best-effort — UI degrades gracefully if either lookup fails.
  }

  const visible = response.items;
  const total = response.total;
  const totalPages = Math.max(1, response.total_pages);
  const start = (page - 1) * PAGE_SIZE;

  const heading =
    view === "featured" ? "featured folds" : "all folds";
  const sub =
    view === "featured"
      ? "the lab's actual discoveries — REFINED first, then PROMISING, ranked by confidence. tool-limit failures are filed under all/."
      : "full archive — including DISCARDED and FAILED. transparency posture: every cycle the lab ran is browsable here.";

  return (
    <div>
      <h1 className="text-h1 sm:text-display font-bold uppercase tracking-wider">
        {heading}
      </h1>
      <p className="mt-3 text-text-secondary text-body max-w-2xl leading-relaxed">
        {sub}
      </p>

      <div className="mt-10">
        <FoldsViewTabs
          view={view}
          featuredCount={featuredTotal}
          totalCount={archiveTotal}
        />

        {view === "all" ? (
          <div className="mb-10">
            <SectionHeader index="01" title="filter" />
            <FoldsFilter />
          </div>
        ) : null}

        <SectionHeader
          index={view === "all" ? "02" : "01"}
          title="catalog"
          trailing={
            total === 0
              ? "no matches"
              : `showing ${start + 1}–${Math.min(start + PAGE_SIZE, total)} of ${total}`
          }
        />
        {total === 0 ? (
          <p className="text-text-muted text-small italic">
            {view === "featured"
              ? "// no featured folds yet — refined and promising results will appear here as cycles complete."
              : "// no folds yet — the lab is distilling. cycles run continuously."}
          </p>
        ) : (
          <>
            <FoldsCatalog folds={visible} />
            <div className="mt-10">
              <Pagination
                page={page}
                totalPages={totalPages}
                basePath="/folds"
                // Only carry ?view= in the URL for the non-default tab —
                // featured pagination stays on bare /folds?page=N which
                // matches the canonical landing URL.
                query={{
                  ...searchParams,
                  view: view === "all" ? "all" : undefined,
                }}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
