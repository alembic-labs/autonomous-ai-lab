import { FoldCard } from "./FoldCard";
import type { FoldListItem } from "@/lib/types";

interface FoldsCatalogProps {
  folds: FoldListItem[];
}

export function FoldsCatalog({ folds }: FoldsCatalogProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5">
      {folds.map((fold) => (
        <FoldCard key={fold.id} fold={fold} showHypothesis />
      ))}
    </div>
  );
}
