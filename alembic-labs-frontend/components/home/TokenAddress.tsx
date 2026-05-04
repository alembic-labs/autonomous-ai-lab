"use client";

import { useState } from "react";

const TOKEN_ADDRESS = "Gh8v3HzbcnW6tTq8A1wFGBuHhy5ooCqGyGv6T2LqU8eh";
const TRUNCATED = `${TOKEN_ADDRESS.slice(0, 6)}…${TOKEN_ADDRESS.slice(-6)}`;

export function TokenAddress() {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(TOKEN_ADDRESS);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      // Older browsers / hardened iframes may not allow clipboard writes.
      // Fail silently — the address is also exposed in the DOM as a title
      // attribute so the user can manually select it from the tooltip.
    }
  }

  return (
    <div className="mt-6 inline-flex items-center gap-3 border border-border-subtle bg-bg-surface/40 px-3 py-2 text-small">
      <span className="text-text-muted uppercase tracking-wider">
        $alembic
      </span>
      <span
        className="font-mono text-text-primary tabular-nums"
        title={TOKEN_ADDRESS}
      >
        {TRUNCATED}
      </span>
      <button
        type="button"
        onClick={handleCopy}
        aria-label="copy token contract address"
        className="text-text-muted hover:text-brand transition-colors uppercase tracking-wider focus:outline-none focus:text-brand"
      >
        {copied ? "copied" : "copy"}
      </button>
    </div>
  );
}
