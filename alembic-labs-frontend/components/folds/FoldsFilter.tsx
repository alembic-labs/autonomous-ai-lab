"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";

const CLASS_OPTIONS = ["", "PERFORMANCE", "LONGEVITY", "METABOLIC", "COGNITIVE", "REGENERATIVE"];
const STATUS_OPTIONS = ["", "REFINED", "PENDING", "DISCARDED"];
const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: "newest", label: "Newest first" },
  { value: "oldest", label: "Oldest first" },
  { value: "confidence_desc", label: "Highest confidence" },
  { value: "confidence_asc", label: "Lowest confidence" },
];

export interface FoldsFilterValues {
  search: string;
  peptide_class: string;
  status: string;
  sort: string;
}

const DEFAULTS: FoldsFilterValues = {
  search: "",
  peptide_class: "",
  status: "",
  sort: "newest",
};

export function FoldsFilter() {
  const router = useRouter();
  const params = useSearchParams();

  const [values, setValues] = useState<FoldsFilterValues>({
    search: params.get("search") ?? "",
    peptide_class: params.get("peptide_class") ?? "",
    status: params.get("status") ?? "",
    sort: params.get("sort") ?? "newest",
  });

  useEffect(() => {
    setValues({
      search: params.get("search") ?? "",
      peptide_class: params.get("peptide_class") ?? "",
      status: params.get("status") ?? "",
      sort: params.get("sort") ?? "newest",
    });
  }, [params]);

  const apply = (next: FoldsFilterValues) => {
    const qs = new URLSearchParams();
    if (next.search) qs.set("search", next.search);
    if (next.peptide_class) qs.set("peptide_class", next.peptide_class);
    if (next.status) qs.set("status", next.status);
    if (next.sort && next.sort !== "newest") qs.set("sort", next.sort);
    qs.set("page", "1");
    router.push(`/folds${qs.toString() ? `?${qs}` : ""}`);
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    apply(values);
  };

  const onClear = () => {
    setValues(DEFAULTS);
    router.push("/folds");
  };

  return (
    <form onSubmit={onSubmit} className="bg-bg-surface border border-border-subtle p-4 sm:p-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
        <label className="flex flex-col gap-2">
          <span className="text-text-muted text-small uppercase tracking-wider">
            search
          </span>
          <input
            type="text"
            value={values.search}
            onChange={(e) => setValues((v) => ({ ...v, search: e.target.value }))}
            placeholder="peptide name or target..."
            className="input-mono"
          />
        </label>
        <label className="flex flex-col gap-2">
          <span className="text-text-muted text-small uppercase tracking-wider">
            class
          </span>
          <select
            value={values.peptide_class}
            onChange={(e) => setValues((v) => ({ ...v, peptide_class: e.target.value }))}
            className="input-mono"
          >
            {CLASS_OPTIONS.map((opt) => (
              <option key={opt} value={opt} className="bg-bg-surface">
                {opt || "All classes"}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-2">
          <span className="text-text-muted text-small uppercase tracking-wider">
            status
          </span>
          <select
            value={values.status}
            onChange={(e) => setValues((v) => ({ ...v, status: e.target.value }))}
            className="input-mono"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt} value={opt} className="bg-bg-surface">
                {opt || "All statuses"}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-2">
          <span className="text-text-muted text-small uppercase tracking-wider">
            sort
          </span>
          <select
            value={values.sort}
            onChange={(e) => setValues((v) => ({ ...v, sort: e.target.value }))}
            className="input-mono"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value} className="bg-bg-surface">
                {opt.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-5 flex flex-wrap gap-3">
        <Button type="submit">apply</Button>
        <Button type="button" variant="bracket" onClick={onClear}>
          clear
        </Button>
      </div>
    </form>
  );
}
