"use client";

import { useMemo } from "react";
import {
  ArrowDown,
  ArrowUp,
  DollarSign,
  Minus,
  ScanLine,
} from "lucide-react";

export interface PriceIntelligencePoint {
  id: string;
  price: string;
  currency: string;
  raw_value: string;
  created_at: string;
}

export interface PriceIntelligenceProps {
  points: PriceIntelligencePoint[];
}

function parsePrice(value: string): number | null {
  const normalized = value.replace(/[^0-9.\-]/g, "");

  if (!normalized) return null;

  const parsed = Number.parseFloat(normalized);

  return Number.isNaN(parsed) ? null : parsed;
}

export function PriceIntelligenceCard({ points }: PriceIntelligenceProps) {
  const current = points[0];
  const baseline = points[points.length - 1];

  const computed = useMemo(() => {
    if (!current) return null;

    const currentValue = parsePrice(current.price);

    if (currentValue == null) return null;

    const baselineValue = baseline ? parsePrice(baseline.price) : null;

    let trend: "up" | "down" | "flat" = "flat";
    let delta = 0;
    let deltaPercent = 0;

    if (baselineValue != null && baselineValue !== currentValue) {
      trend = currentValue > baselineValue ? "up" : "down";
      delta = Number((currentValue - baselineValue).toFixed(2));
      deltaPercent = Number(
        ((delta / Math.abs(baselineValue)) * 100).toFixed(2),
      );
    }

    const values = points
      .map((point) => parsePrice(point.price))
      .filter((value): value is number => value != null)
      .reverse();

    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;

    const bars = values.map((value) => ({
      value,
      height: Math.max(12, ((value - min) / range) * 64 + 12),
      current: value === currentValue,
    }));

    return {
      currentValue,
      baselineValue,
      trend,
      delta,
      deltaPercent,
      bars,
    };
  }, [points, baseline, current]);

  if (!current || !computed) {
    return (
      <section className="apeiro-card overflow-hidden">
        <div className="flex items-start justify-between gap-4 p-6">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
              Price intelligence
            </p>

            <h2 className="mt-2 text-lg font-semibold">
              Price Intelligence Tracking
            </h2>

            <p className="mt-1 text-sm text-slate-400">
              No price observations recorded yet. Enable price monitoring
              and run a check to begin tracking.
            </p>
          </div>

          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-secondary text-slate-300">
            <DollarSign size={17} />
          </span>
        </div>
      </section>
    );
  }

  const currency = current.currency || "USD";

  return (
    <section className="apeiro-card overflow-hidden">
      <div className="flex flex-col justify-between gap-4 border-b border-border p-6 sm:flex-row sm:items-center">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
            Price intelligence
          </p>

          <h2 className="mt-2 text-lg font-semibold">
            Price Intelligence Tracking
          </h2>

          <p className="mt-1 text-sm text-slate-400">
            Baseline vs current detected price across {points.length}{" "}
            observations.
          </p>
        </div>

        <span className="inline-flex shrink-0 items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-300">
          <span className="status-dot status-dot--on" aria-hidden="true" />
          Tracking
        </span>
      </div>

      <div className="grid gap-px bg-border sm:grid-cols-2">
        <div className="bg-card p-6">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Baseline price
          </p>

          <p className="mt-2 text-2xl font-semibold tracking-tight tabular-nums text-slate-300">
            {baseline ? baseline.price : "—"}
            <span className="ml-1.5 text-sm font-medium text-slate-500">
              {currency}
            </span>
          </p>
        </div>

        <div className="border-t border-border bg-card p-6 sm:border-l sm:border-t-0">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Current detected price
          </p>

          <div className="mt-2 flex items-baseline gap-2.5">
            <p className="text-3xl font-semibold tracking-tight tabular-nums">
              {current.price}
              <span className="ml-1.5 text-base font-medium text-slate-500">
                {currency}
              </span>
            </p>

            <span
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${
                computed.trend === "up"
                  ? "bg-success-muted text-success"
                  : computed.trend === "down"
                    ? "bg-danger-muted text-danger"
                    : "bg-muted text-slate-400"
              }`}
            >
              {computed.trend === "up" ? (
                <ArrowUp size={12} />
              ) : computed.trend === "down" ? (
                <ArrowDown size={12} />
              ) : (
                <Minus size={12} />
              )}
              {computed.trend === "flat"
                ? "Unchanged"
                : `${computed.delta > 0 ? "+" : ""}${computed.delta} · ${
                    computed.deltaPercent
                  }%`}
            </span>
          </div>
        </div>
      </div>

      <div className="border-t border-border bg-card p-6">
        <div className="flex items-center justify-between gap-2 text-xs font-medium">
          <span className="inline-flex items-center gap-1.5 text-slate-500">
            <ScanLine size={13} />
            Price trend over time
          </span>

          <span className="text-slate-500 tabular-nums">
            {points.length} readings
          </span>
        </div>

        <div className="mt-4 flex h-20 items-end gap-1.5">
          {computed.bars.map((bar, index) => (
            <div
              key={index}
              title={`${bar.value} ${currency}`}
              className={`flex-1 rounded-t-md transition-colors ${
                bar.current
                  ? "bg-accent shadow-[0_0_12px_rgba(200,239,114,0.35)]"
                  : "bg-slate-700/70 hover:bg-slate-600"
              }`}
              style={{ height: `${bar.height}px` }}
            />
          ))}
        </div>

        <div className="mt-3 flex items-center justify-between text-[0.7rem] text-slate-500">
          <span>
            Oldest{" "}
            {baseline
              ? new Date(baseline.created_at).toLocaleDateString()
              : ""}
          </span>
          <span>
            Newest{" "}
            {new Date(current.created_at).toLocaleDateString()}
          </span>
        </div>
      </div>
    </section>
  );
}

export default PriceIntelligenceCard;