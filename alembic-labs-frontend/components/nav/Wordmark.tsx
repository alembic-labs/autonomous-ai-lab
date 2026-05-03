import Link from "next/link";

interface WordmarkProps {
  size?: "sm" | "md" | "lg";
  href?: string | null;
  className?: string;
}

const MERCURY = "\u263F";

const SIZES = {
  sm: { glyph: "text-[1.05rem] leading-none", word: "text-small" },
  md: { glyph: "text-[1.25rem] leading-none", word: "text-h2" },
  lg: { glyph: "text-[1.55rem] leading-none", word: "text-h1" },
} as const;

export function Wordmark({ size = "md", href = "/", className = "" }: WordmarkProps) {
  const dim = SIZES[size];
  const inner = (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <span
        className={`${dim.glyph} text-brand select-none shrink-0`}
        aria-hidden
        style={{ fontFamily: "'JetBrains Mono', ui-monospace, monospace" }}
      >
        {MERCURY}
      </span>
      <span
        className={`${dim.word} font-bold uppercase tracking-wider text-text-primary whitespace-nowrap`}
      >
        ALEMBIC LABS
      </span>
    </span>
  );
  if (!href) return inner;
  return (
    <Link href={href} className="inline-flex items-center group">
      {inner}
    </Link>
  );
}
