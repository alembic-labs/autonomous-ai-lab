import type { FoldStatus } from "@/lib/types";

const STATUS_COLORS: Record<FoldStatus, { dot: string; text: string; border: string }> = {
  REFINED: {
    dot: "bg-status-refined",
    text: "text-status-refined",
    border: "border-status-refined/40",
  },
  PROMISING: {
    dot: "bg-status-promising",
    text: "text-status-promising",
    border: "border-status-promising/40",
  },
  PENDING: {
    dot: "bg-status-pending",
    text: "text-status-pending",
    border: "border-status-pending/40",
  },
  DISCARDED: {
    dot: "bg-status-discarded",
    text: "text-status-discarded",
    border: "border-status-discarded/40",
  },
  FAILED: {
    dot: "bg-status-failed",
    text: "text-status-failed",
    border: "border-status-failed/40",
  },
};

interface StatusBadgeProps {
  status: FoldStatus;
  showDot?: boolean;
  className?: string;
}

export function StatusBadge({ status, showDot = true, className = "" }: StatusBadgeProps) {
  const c = STATUS_COLORS[status];
  return (
    <span className={`badge-status ${c.text} ${c.border} ${className}`}>
      {showDot ? <span className={`inline-block w-2 h-2 ${c.dot}`} /> : null}
      <span>[ {status} ]</span>
    </span>
  );
}
