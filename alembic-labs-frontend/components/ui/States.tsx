"use client";

interface LoadingProps {
  label?: string;
  className?: string;
}

export function Loading({ label = "loading", className = "" }: LoadingProps) {
  return (
    <p
      className={`text-text-muted text-small italic blink-cursor ${className}`}
      role="status"
      aria-live="polite"
    >
      {`// ${label}...`}
    </p>
  );
}

interface ErrorStateProps {
  label?: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  label = "connection failed",
  onRetry,
  className = "",
}: ErrorStateProps) {
  return (
    <div className={`flex flex-col gap-3 items-start ${className}`}>
      <p className="text-status-failed text-small italic">{`// ${label}`}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="btn-bracket text-small"
        >
          <span className="text-text-muted">[</span>
          <span>retry</span>
          <span className="text-text-muted">]</span>
        </button>
      ) : null}
    </div>
  );
}

interface EmptyStateProps {
  label?: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}

export function EmptyState({
  label = "no items match these filters",
  actionLabel = "clear filters",
  onAction,
  className = "",
}: EmptyStateProps) {
  return (
    <div className={`flex flex-col gap-3 items-start ${className}`}>
      <p className="text-text-muted text-small italic">{`// ${label}`}</p>
      {onAction ? (
        <button
          type="button"
          onClick={onAction}
          className="btn-bracket text-small"
        >
          <span className="text-text-muted">[</span>
          <span>{actionLabel}</span>
          <span className="text-text-muted">]</span>
        </button>
      ) : null}
    </div>
  );
}
