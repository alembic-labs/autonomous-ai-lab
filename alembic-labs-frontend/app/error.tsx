"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="min-h-[50vh] flex flex-col items-start justify-center gap-6 py-16">
      <div>
        <p className="text-small uppercase tracking-wider text-brand mb-2">
          runtime error
        </p>
        <h1 className="text-h1 font-bold uppercase tracking-wider text-text-primary">
          something broke
        </h1>
        <p className="mt-3 text-text-secondary text-body max-w-xl leading-relaxed">
          {error.message ||
            "An unexpected error occurred. If you were running the dev server, try stopping it, run `npm run dev:clean`, then reload."}
        </p>
      </div>
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => reset()}
          className="px-4 py-2 text-small uppercase tracking-wider border border-brand text-brand hover:bg-brand hover:text-bg transition-colors"
        >
          try again
        </button>
        <a
          href="/"
          className="px-4 py-2 text-small uppercase tracking-wider border border-border-accent text-text-secondary hover:text-text-primary transition-colors"
        >
          home
        </a>
      </div>
      {error.digest ? (
        <p className="text-small text-text-muted font-mono">digest: {error.digest}</p>
      ) : null}
    </div>
  );
}
