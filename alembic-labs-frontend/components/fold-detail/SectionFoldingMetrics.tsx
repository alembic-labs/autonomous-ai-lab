"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { SectionHeader } from "@/components/ui/SectionHeader";
import type { Chai1GatedDecision, FoldMetrics } from "@/lib/types";

interface SectionFoldingMetricsProps {
  metrics: FoldMetrics | null;
  fallback: {
    plddt: number | null;
    ptm: number | null;
    iptm: number | null;
    agreement: number | null;
  };
  /** Adaptive Chai-1 cross-validation gating decision for this fold. */
  chai1Decision: Chai1GatedDecision | null;
}

const RED = "#ff3344";
const GRID = "#1f1f1f";
const AXIS = "#444444";
const SOFT = "#a8a8a8";

function fmt(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toFixed(digits);
}

function MetricCell({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div>
      <div className="text-text-muted text-[11px] uppercase tracking-wider">
        {label}
      </div>
      <div className="mt-2 text-h2 font-bold text-brand tabular-nums">
        {value}
      </div>
      {hint ? (
        <div className="mt-1 text-text-muted text-[11px]">{hint}</div>
      ) : null}
    </div>
  );
}

interface PlotDatum {
  residue: number;
  plddt: number;
}

function PlddtPlot({ data }: { data: PlotDatum[] }) {
  return (
    <div className="border border-border-subtle bg-bg-surface p-4 sm:p-5">
      <div className="flex items-baseline justify-between mb-3">
        <h4 className="text-text-primary text-[12px] uppercase tracking-wider font-bold">
          pLDDT per residue
        </h4>
        <span className="text-text-muted text-[11px] uppercase tracking-wider">
          {data.length} residues
        </span>
      </div>
      <div style={{ width: "100%", height: 220 }}>
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>
            <CartesianGrid stroke={GRID} strokeDasharray="2 4" vertical={false} />
            <XAxis
              dataKey="residue"
              stroke={AXIS}
              tick={{ fill: SOFT, fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: GRID }}
            />
            <YAxis
              domain={[0, 1]}
              stroke={AXIS}
              tick={{ fill: SOFT, fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: GRID }}
              width={32}
            />
            <Tooltip
              cursor={{ stroke: RED, strokeWidth: 1, strokeDasharray: "2 2" }}
              contentStyle={{
                background: "#0a0a0a",
                border: "1px solid #2a2a2a",
                borderRadius: 0,
                color: "#e8e8e8",
                fontFamily: "JetBrains Mono",
                fontSize: 12,
              }}
              labelStyle={{ color: "#a8a8a8" }}
              formatter={(value) => [
                typeof value === "number" ? value.toFixed(3) : String(value),
                "pLDDT",
              ]}
              labelFormatter={(label) => `residue ${label}`}
            />
            <ReferenceLine
              y={0.7}
              stroke="#44dd88"
              strokeDasharray="3 3"
              label={{
                value: "good ≥ 0.70",
                position: "right",
                fill: "#44dd88",
                fontSize: 10,
              }}
            />
            <ReferenceLine
              y={0.5}
              stroke="#ffcc44"
              strokeDasharray="3 3"
              label={{
                value: "weak < 0.50",
                position: "right",
                fill: "#ffcc44",
                fontSize: 10,
              }}
            />
            <Line
              type="monotone"
              dataKey="plddt"
              stroke={RED}
              strokeWidth={1.6}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function AggregationPlot({ values }: { values: number[] }) {
  if (values.length === 0) return null;
  const data = values.map((v, i) => ({ window: i + 1, score: v }));
  const max = Math.max(...values, 2);
  return (
    <div className="border border-border-subtle bg-bg-surface p-4 sm:p-5">
      <div className="flex items-baseline justify-between mb-3">
        <h4 className="text-text-primary text-[12px] uppercase tracking-wider font-bold">
          aggregation propensity (window)
        </h4>
        <span className="text-text-muted text-[11px] uppercase tracking-wider">
          {values.length} windows
        </span>
      </div>
      <div style={{ width: "100%", height: 180 }}>
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>
            <CartesianGrid stroke={GRID} strokeDasharray="2 4" vertical={false} />
            <XAxis
              dataKey="window"
              stroke={AXIS}
              tick={{ fill: SOFT, fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: GRID }}
            />
            <YAxis
              domain={[0, max < 2 ? 2 : Math.ceil(max)]}
              stroke={AXIS}
              tick={{ fill: SOFT, fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: GRID }}
              width={32}
            />
            <Tooltip
              cursor={{ stroke: RED, strokeWidth: 1, strokeDasharray: "2 2" }}
              contentStyle={{
                background: "#0a0a0a",
                border: "1px solid #2a2a2a",
                borderRadius: 0,
                color: "#e8e8e8",
                fontFamily: "JetBrains Mono",
                fontSize: 12,
              }}
              labelStyle={{ color: "#a8a8a8" }}
              formatter={(value) => [
                typeof value === "number" ? value.toFixed(2) : String(value),
                "score",
              ]}
              labelFormatter={(label) => `window ${label}`}
            />
            <Line
              type="monotone"
              dataKey="score"
              stroke={RED}
              strokeWidth={1.6}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function agreementHint(v: number | null): string | undefined {
  if (v === null) return undefined;
  if (v >= 0.85) return "strong";
  if (v >= 0.65) return "moderate";
  return "weak";
}

/**
 * Caption for the Boltz↔Chai cell that surfaces the adaptive gating decision.
 *
 * - When Chai-1 actually ran (RAN_BORDERLINE), we still want to show the
 *   raw strong/moderate/weak hint AND the "cross-validated" badge — the
 *   user wants to know both that we cross-validated *and* whether the
 *   models agreed.
 * - When Chai-1 was skipped, we replace the agreement hint entirely (the
 *   raw value will be "—" anyway) with a one-liner explaining why.
 * - RAN_FORCED and DISABLED don't show a caption — the former is legacy
 *   behaviour we don't want to advertise, the latter is "feature off".
 */
function chai1Caption(
  decision: Chai1GatedDecision | null,
  agreement: number | null,
): string | undefined {
  switch (decision) {
    case "RAN_BORDERLINE": {
      const base = agreementHint(agreement);
      const cross = "cross-validated (borderline pLDDT)";
      return base ? `${base} · ${cross}` : cross;
    }
    case "SKIPPED_HIGH_CONFIDENCE":
      return "skipped — high Boltz-2 confidence";
    case "SKIPPED_LOW_CONFIDENCE":
      return "skipped — Boltz-2 inconclusive, cross-val would not help";
    case "RAN_FORCED":
    case "DISABLED":
    case null:
    default:
      return agreementHint(agreement);
  }
}

function bindingProbHint(v: number | null): string | undefined {
  if (v === null) return undefined;
  if (v >= 0.7) return "strong binder";
  if (v >= 0.5) return "moderate";
  if (v >= 0.3) return "weak";
  return "non-binder";
}

function pic50ToKdNm(pic50: number | null): string | undefined {
  if (pic50 === null || Number.isNaN(pic50)) return undefined;
  const ic50nm = Math.pow(10, -pic50) * 1e9;
  if (!Number.isFinite(ic50nm)) return undefined;
  if (ic50nm >= 1000) return `~${(ic50nm / 1000).toFixed(1)} μM IC50`;
  return `~${ic50nm.toFixed(0)} nM IC50`;
}

interface AffinityPanelProps {
  probability: number | null;
  pic50: number | null;
}

function AffinityPanel({ probability, pic50 }: AffinityPanelProps) {
  if (probability === null && pic50 === null) return null;
  return (
    <div className="border border-border-accent bg-bg-elevated p-5">
      <div className="flex items-baseline justify-between mb-4">
        <h4 className="text-text-muted text-[11px] uppercase tracking-wider">
          binding prediction (Boltz-2 affinity module)
        </h4>
        <span className="text-text-muted text-[10px] uppercase tracking-widest">
          model output
        </span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-5">
        <MetricCell
          label="binder probability"
          value={fmt(probability, 3)}
          hint={bindingProbHint(probability)}
        />
        <MetricCell
          label="predicted pIC50"
          value={fmt(pic50, 2)}
          hint={pic50ToKdNm(pic50)}
        />
      </div>
      <p className="mt-4 text-text-secondary text-small leading-snug">
        Calibrated binder/non-binder probability and predicted pIC50 from
        Boltz-2&apos;s dedicated affinity head. Treat the IC50 conversion as
        an order-of-magnitude indicator only.
      </p>
    </div>
  );
}

export function SectionFoldingMetrics({
  metrics,
  fallback,
  chai1Decision,
}: SectionFoldingMetricsProps) {
  const plddt = metrics?.plddt_mean ?? fallback.plddt;
  const ptm = metrics?.ptm ?? fallback.ptm;
  const iptm = metrics?.iptm ?? fallback.iptm;
  const agreement = metrics?.agreement ?? fallback.agreement;
  const bindingProbability = metrics?.binding_probability ?? null;
  const bindingPic50 = metrics?.binding_pic50 ?? null;

  const perRes = metrics?.plddt_per_residue ?? [];
  const aggWindows = metrics?.aggregation_window_scores ?? [];

  return (
    <section className="mb-16">
      <SectionHeader index="05" title="folding metrics" />

      <div className="space-y-4">
        {perRes.length > 0 ? (
          <PlddtPlot data={perRes} />
        ) : (
          <div className="border border-border-subtle bg-bg-surface p-4 sm:p-5">
            <p className="text-text-muted text-small italic">
              {`// no per-residue pLDDT trace — Boltz-2 returned summary metrics only`}
            </p>
          </div>
        )}

        <AggregationPlot values={aggWindows} />

        <AffinityPanel
          probability={bindingProbability}
          pic50={bindingPic50}
        />

        <div className="border border-border-accent bg-bg-elevated p-5">
          <h4 className="text-text-muted text-[11px] uppercase tracking-wider mb-4">
            confidence metrics
          </h4>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-5">
            <MetricCell label="pLDDT mean" value={fmt(plddt)} />
            <MetricCell label="pTM" value={fmt(ptm)} />
            <MetricCell label="ipTM" value={fmt(iptm)} />
            <MetricCell
              label="Boltz ↔ Chai"
              value={fmt(agreement)}
              hint={chai1Caption(chai1Decision, agreement)}
            />
          </div>
        </div>
      </div>
    </section>
  );
}
