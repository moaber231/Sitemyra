"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowUpRight,
  Camera,
  CheckCircle2,
  Clock3,
  DollarSign,
  FileDiff,
  Loader2,
  RefreshCw,
} from "lucide-react";

import {
  getMonitorDiffs,
  getMonitorPrices,
  type ChangeDiff,
  type PricePoint,
} from "@/lib/api/advanced";

import { PriceIntelligenceCard } from "@/components/observability/price-intelligence";

interface AdvancedMonitoringSectionProps {
  monitorId: string;
}

function formatDate(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }

  return date.toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function DiffIcon({ type }: { type: ChangeDiff["type"] }) {
  if (type === "screenshot") {
    return <Camera size={16} />;
  }

  if (type === "price") {
    return <DollarSign size={16} />;
  }

  return <FileDiff size={16} />;
}

function DiffBadge({ type }: { type: ChangeDiff["type"] }) {
  const meta = {
    dom: {
      label: "DOM change",
      icon: FileDiff,
      className: "bg-warning-muted text-warning",
    },
    screenshot: {
      label: "Visual change",
      icon: Camera,
      className: "bg-secondary text-secondary-foreground",
    },
    price: {
      label: "Price change",
      icon: DollarSign,
      className: "bg-success-muted text-success",
    },
  }[type];

  const Icon = meta.icon;

  return (
    <span className={`apeiro-badge text-xs ${meta.className}`}>
      <Icon size={12} />
      {meta.label}
    </span>
  );
}

export function AdvancedMonitoringSection({
  monitorId,
}: AdvancedMonitoringSectionProps) {
  const [token, setToken] = useState<string | null>(null);
  const [diffs, setDiffs] = useState<ChangeDiff[]>([]);
  const [prices, setPrices] = useState<PricePoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const accessToken = sessionStorage.getItem("apeiro_access");

    if (!accessToken) {
      window.location.href = "/login";
      return;
    }

    setToken(accessToken);
  }, []);

  async function loadHistory(showSpinner = true) {
    const accessToken = sessionStorage.getItem("apeiro_access");

    if (!accessToken) {
      window.location.href = "/login";
      return;
    }

    try {
      if (showSpinner) {
        setRefreshing(true);
      }

      setError("");

      const [diffData, priceData] = await Promise.all([
        getMonitorDiffs(accessToken, monitorId),
        getMonitorPrices(accessToken, monitorId),
      ]);

      setDiffs(diffData);
      setPrices(priceData);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load advanced history.",
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    if (token) {
      loadHistory(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, monitorId]);

  return (
    <div className="animate-apeiro-fade-up space-y-6">
      <PriceIntelligenceCard points={prices} />

      <section className="apeiro-card overflow-hidden">
        <div className="flex flex-col justify-between gap-4 border-b border-border p-6 sm:flex-row sm:items-center">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
              Change history
            </p>

            <h2 className="mt-2 text-lg font-semibold">
              Advanced detection events
            </h2>

            <p className="mt-1 text-sm text-slate-400">
              DOM, visual, and price changes detected by advanced
              monitoring. Open an event to inspect its diff.
            </p>
          </div>

          <button
            type="button"
            onClick={() => loadHistory(true)}
            disabled={refreshing}
            className="apeiro-btn apeiro-btn-outline"
          >
            {refreshing ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <RefreshCw size={15} />
            )}
            Refresh
          </button>
        </div>

        {error && (
          <div className="m-6 flex items-start gap-3 rounded-lg border border-danger/30 bg-danger-muted p-4 text-sm text-danger">
            <AlertTriangle size={17} className="mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {loading ? (
          <div className="space-y-3 p-6">
            {[1, 2, 3].map((item) => (
              <div key={item} className="apeiro-skeleton h-16" />
            ))}
          </div>
        ) : diffs.length === 0 ? (
          <div className="p-8 text-center">
            <CheckCircle2 size={22} className="mx-auto text-success" />

            <p className="mt-3 text-sm font-medium">
              No advanced changes detected yet.
            </p>

            <p className="mt-1 text-sm text-slate-400">
              Run an advanced check after configuring DOM, screenshot, or
              price monitoring.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {diffs.map((diff) => {
              const changeTone =
                diff.type === "price"
                  ? "bg-success-muted text-success"
                  : diff.type === "screenshot"
                    ? "bg-secondary text-secondary-foreground"
                    : "bg-warning-muted text-warning";

              return (
                <Link
                  key={diff.id}
                  href={`/dashboard/monitors/${monitorId}/diffs/${diff.id}`}
                  className="group flex flex-col gap-3 p-5 transition-colors hover:bg-muted/40 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="flex min-w-0 items-start gap-3.5">
                    <div
                      className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${changeTone}`}
                    >
                      <DiffIcon type={diff.type} />
                    </div>

                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate text-sm font-medium">
                          {diff.summary || "Change detected"}
                        </p>

                        <DiffBadge type={diff.type} />
                      </div>

                      <p className="mt-1.5 inline-flex items-center gap-1.5 text-xs text-slate-400">
                        <Clock3 size={12} />
                        {formatDate(diff.created_at)}
                      </p>
                    </div>
                  </div>

                  <div className="flex shrink-0 items-center gap-3 self-start sm:self-center">
                    {diff.diff_percentage != null && (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-xs font-semibold tabular-nums text-slate-300">
                        <span
                          className="h-1.5 w-1.5 rounded-full bg-warning"
                          aria-hidden="true"
                        />
                        {diff.diff_percentage.toFixed(2)}%
                      </span>
                    )}

                    <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 transition-colors group-hover:text-slate-300">
                      View diff
                      <ArrowUpRight
                        size={14}
                        className="transition-transform duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
                      />
                    </span>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}

export default AdvancedMonitoringSection;