import Link from "next/link";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { FoldCard } from "@/components/folds/FoldCard";
import { listFolds } from "@/lib/api";

export const dynamic = "force-dynamic";

export async function RecentFolds() {
  let folds: Awaited<ReturnType<typeof listFolds>>["items"] = [];
  try {
    const res = await listFolds({ page: 1, page_size: 6, sort: "newest" });
    folds = res.items;
  } catch {
    folds = [];
  }
  return (
    <section className="mb-16">
      <SectionHeader
        index="03"
        title="recent folds"
        trailing={
          <Link
            href="/folds"
            className="text-brand hover:text-brand-glow text-small uppercase tracking-wider"
          >
            [ view all → ]
          </Link>
        }
      />
      {folds.length === 0 ? (
        <p className="text-text-muted text-small italic">
          {`// no folds yet — the lab is distilling. cycles run continuously.`}
        </p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5">
          {folds.map((fold) => (
            <FoldCard key={fold.id} fold={fold} />
          ))}
        </div>
      )}
    </section>
  );
}
