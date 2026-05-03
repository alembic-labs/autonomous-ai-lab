// Hermetic glyphs used sparingly across the lab.
// ☿ Mercury, 🜍 Sulfur, 🜔 Earth, 🜂 Fire, 🜄 Water, 🜔 Salt of the Earth.
//
// We map agent roles to symbols inspired by classical alchemy.

import type { AgentName } from "@/lib/types";

export const AGENT_GLYPH: Record<AgentName, string> = {
  RESEARCHER: "☿",
  LITERATURE: "🜍",
  STRUCTURAL: "🜔",
  CLINICAL: "🜂",
  COMMUNICATOR: "🜄",
};

interface HermeticSymbolProps {
  glyph?: string;
  agent?: AgentName;
  className?: string;
  muted?: boolean;
}

export function HermeticSymbol({
  glyph,
  agent,
  className = "",
  muted = true,
}: HermeticSymbolProps) {
  const value = glyph ?? (agent ? AGENT_GLYPH[agent] : "☿");
  const colorClass = muted ? "text-brand-deep/70" : "text-brand";
  return (
    <span aria-hidden className={`select-none ${colorClass} ${className}`}>
      {value}
    </span>
  );
}
