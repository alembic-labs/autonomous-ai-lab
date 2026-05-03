// Small formatting helpers used across the UI.

export function formatDate(iso: string, opts: Intl.DateTimeFormatOptions = {}): string {
  try {
    const date = new Date(iso);
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      ...opts,
    });
  } catch {
    return iso;
  }
}

export function formatUtcTime(iso: string): string {
  try {
    const date = new Date(iso);
    const hh = String(date.getUTCHours()).padStart(2, "0");
    const mm = String(date.getUTCMinutes()).padStart(2, "0");
    const ss = String(date.getUTCSeconds()).padStart(2, "0");
    return `${hh}:${mm}:${ss} UTC`;
  } catch {
    return iso;
  }
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toFixed(digits)}%`;
}

export function formatConfidence(plddt: number | null | undefined): string {
  if (plddt === null || plddt === undefined) return "—";
  // pLDDT in some backends is 0–1, in others 0–100. Normalize to %.
  const pct = plddt > 1.5 ? plddt : plddt * 100;
  return `${pct.toFixed(1)}%`;
}

export function formatNumber(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString("en-US");
}

export function clamp(text: string, max: number): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1).trimEnd()}…`;
}
