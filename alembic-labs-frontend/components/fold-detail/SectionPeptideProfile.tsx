import { SectionHeader } from "@/components/ui/SectionHeader";

interface SectionPeptideProfileProps {
  aggregation: number | null;
  stability: number | null;
  bbb: number | null;
  halfLife: string | null;
}

type Rating = "good" | "moderate" | "concerning" | "neutral";

const RATING_COLOR: Record<Rating, string> = {
  good: "#44dd88",
  moderate: "#ffcc44",
  concerning: "#ff3344",
  neutral: "#a8a8a8",
};

const RATING_LABEL: Record<Rating, string> = {
  good: "good",
  moderate: "moderate",
  concerning: "concerning",
  neutral: "—",
};

interface MetricCardProps {
  label: string;
  description: string;
  value: string;
  rating: Rating;
  scaleHint?: string;
  /**
   * Heuristic source label rendered as a small badge — every metric on this
   * card is a sequence-based estimate, never a wet-lab measurement, so we
   * surface that explicitly so users don't compare numbers as if they were.
   */
  heuristicLabel: string;
}

function MetricCard({
  label,
  description,
  value,
  rating,
  scaleHint,
  heuristicLabel,
}: MetricCardProps) {
  const color = RATING_COLOR[rating];
  return (
    <div
      className="border border-border-subtle bg-bg-surface p-5 relative"
      style={{ borderLeftColor: color, borderLeftWidth: 2 }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="text-text-muted text-[11px] uppercase tracking-wider">
          {label}
        </div>
        <span
          className="shrink-0 border border-border-subtle text-text-muted px-1.5 py-0.5 text-[9px] uppercase tracking-widest"
          title={`Sequence-based heuristic: ${heuristicLabel}`}
        >
          heuristic
        </span>
      </div>
      <div
        className="mt-3 text-h2 sm:text-display font-bold tabular-nums"
        style={{ color }}
      >
        {value}
      </div>
      <div className="mt-1 text-[11px] uppercase tracking-wider" style={{ color }}>
        ● {RATING_LABEL[rating]}
      </div>
      <div className="mt-3 text-text-secondary text-small leading-snug">
        {description}
      </div>
      {scaleHint ? (
        <div className="mt-2 text-text-muted text-[10px] uppercase tracking-wider">
          {scaleHint}
        </div>
      ) : null}
      <div className="mt-1 text-text-muted text-[10px] tracking-wider">
        source: {heuristicLabel}
      </div>
    </div>
  );
}

function rateLowIsGood(
  v: number | null,
  good: number,
  moderate: number,
): Rating {
  if (v === null || v === undefined) return "neutral";
  if (v <= good) return "good";
  if (v <= moderate) return "moderate";
  return "concerning";
}

function rateHighIsGood(
  v: number | null,
  good: number,
  moderate: number,
): Rating {
  if (v === null || v === undefined) return "neutral";
  if (v >= good) return "good";
  if (v >= moderate) return "moderate";
  return "concerning";
}

function fmtNum(v: number | null, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toFixed(digits);
}

export function SectionPeptideProfile({
  aggregation,
  stability,
  bbb,
  halfLife,
}: SectionPeptideProfileProps) {
  const aggRating = rateLowIsGood(aggregation, 0.4, 0.8);
  const stabRating = rateHighIsGood(stability, 0.7, 0.4);
  // BBB is goal-dependent — present neutral colour, only flag concerning at extremes.
  const bbbRating: Rating =
    bbb === null
      ? "neutral"
      : bbb >= 0.5
        ? "good"
        : bbb >= 0.2
          ? "moderate"
          : "neutral";

  return (
    <section className="mb-16">
      <SectionHeader index="08" title="peptide profile" />
      <p className="mb-4 text-text-secondary text-small leading-relaxed max-w-3xl">
        These are <span className="text-text-primary">sequence-based heuristic estimates</span>,
        not wet-lab measurements. Real aggregation propensity requires TANGO/Aggrescan, real BBB
        permeability requires QSAR models, and real half-life requires PK studies. Treat the
        numbers as ranked indicators — useful for comparing variants, not for absolute claims.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="aggregation propensity"
          description="Predicted likelihood of self-aggregation. Lower is better."
          value={fmtNum(aggregation, 3)}
          rating={aggRating}
          scaleHint="≤ 0.40 good · ≤ 0.80 moderate"
          heuristicLabel="Kyte-Doolittle window proxy"
        />
        <MetricCard
          label="stability prediction"
          description="Composite stability score. Higher = more stable in solution."
          value={fmtNum(stability, 2)}
          rating={stabRating}
          scaleHint="≥ 0.70 good · ≥ 0.40 moderate"
          heuristicLabel="charge / proline / length composite"
        />
        <MetricCard
          label="BBB penetration"
          description="Estimated blood-brain barrier permeability. Goal depends on target tissue."
          value={fmtNum(bbb, 3)}
          rating={bbbRating}
          scaleHint="≥ 0.50 high · ≥ 0.20 moderate"
          heuristicLabel="hydrophobic fraction proxy"
        />
        <MetricCard
          label="half-life estimate"
          description="In-silico estimated plasma half-life range."
          value={halfLife ?? "—"}
          rating="neutral"
          scaleHint="text estimate"
          heuristicLabel="length-bucket heuristic"
        />
      </div>
    </section>
  );
}
