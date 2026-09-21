"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Camera,
  DollarSign,
  ExternalLink,
  FileDiff,
  Loader2,
  PackageOpen,
  ShieldAlert,
} from "lucide-react";

import { AppShell } from "@/components/layout/app-shell";
import { DashboardHeader } from "@/components/navigation/DashboardHeader";
import {
  DiffViewer,
  priceDiffFromSummary,
} from "@/components/observability/diff-viewer";
import { PriceIntelligenceCard } from "@/components/observability/price-intelligence";
import {
  downloadDiffArtifact,
  getMonitorDiffs,
  getMonitorPrices,
  type ChangeDiff,
  type PricePoint,
} from "@/lib/api/advanced";
import { getMonitor, type Monitor } from "@/lib/api/monitors";
import type { LucideIcon } from "lucide-react";

function formatDate(value: string | null) {
  if (!value) return "Unknown";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }

  return date.toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

const TYPE_META: Record<
  ChangeDiff["type"],
  { label: string; icon: LucideIcon; className: string }
> = {
  dom: {
    label: "DOM & CSS change",
    icon: FileDiff,
    className:
      "bg-amber-500/10 text-amber-300 border border-amber-500/20",
  },
  screenshot: {
    label: "Visual change",
    icon: Camera,
    className: "bg-slate-800/80 text-slate-300 border border-slate-800",
  },
  price: {
    label: "Price change",
    icon: DollarSign,
    className:
      "bg-emerald-500/10 text-emerald-300 border border-emerald-500/20",
  },
};

export default function DiffDetailPage({
  params,
}: {
  params: Promise<{ id: string; diffId: string }>;
}) {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [monitorId, setMonitorId] = useState<string | null>(null);
  const [diffId, setDiffId] = useState<string | null>(null);

  useEffect(() => {
    const token = sessionStorage.getItem("apeiro_access");

    if (!token) {
      window.location.href = "/login";
      return;
    }

    setAccessToken(token);

    params.then(({ id, diffId: routeDiffId }) => {
      setMonitorId(id);
      setDiffId(routeDiffId);
    });
  }, [params]);

  const [diffs, setDiffs] = useState<ChangeDiff[]>([]);
  const [prices, setPrices] = useState<PricePoint[]>([]);
  const [monitor, setMonitor] = useState<Monitor | null>(null);
  const [detailLoading, setDetailLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!accessToken || !monitorId || !diffId) return;

    setDetailLoading(true);
    setError("");

    Promise.all([
      getMonitor(accessToken, monitorId),
      getMonitorDiffs(accessToken, monitorId),
      getMonitorPrices(accessToken, monitorId),
    ])
      .then(([monitorData, diffData, priceData]) => {
        setMonitor(monitorData);
        setDiffs(diffData);
        setPrices(priceData);
      })
      .catch((err) => {
        setError(
          err instanceof Error ? err.message : "Unable to load change.",
        );
      })
      .finally(() => {
        setDetailLoading(false);
      });
  }, [accessToken, monitorId, diffId]);

  const diff = diffs.find((item) => item.id === diffId) ?? null;

  if (!accessToken || !monitorId || !diffId || detailLoading) {
    return (
      <AppShell>
        <div className="mx-auto max-w-6xl px-0 py-2">
          <DashboardHeader
            title="Change detail"
            parentHref={
              monitorId
                ? `/dashboard/monitors/${monitorId}`
                : "/dashboard/monitors"
            }
            parentLabel="Monitor"
          />
          <div
            className="flex min-h-[50vh] items-center justify-center gap-2 text-sm text-slate-400"
            role="status"
            aria-label="Loading change detail"
          >
            <Loader2
              size={17}
              className="animate-spin"
              aria-hidden="true"
            />
            Loading change detail...
          </div>
        </div>
      </AppShell>
    );
  }

  if (error || !diff) {
    return (
      <AppShell>
        <div className="mx-auto max-w-6xl px-0 py-2">
          <DashboardHeader
            title="Change detail"
            parentHref={
              monitorId
                ? `/dashboard/monitors/${monitorId}`
                : "/dashboard/monitors"
            }
            parentLabel="Monitor"
          />

          <div className="apeiro-glass mt-6 p-8 text-center">
            <ShieldAlert
              size={28}
              className="mx-auto text-red-400"
              aria-hidden="true"
            />

            <h1 className="mt-3 font-semibold text-slate-100">
              Something went wrong
            </h1>

            <p className="mt-1 text-sm text-slate-400">
              We couldn&apos;t load this change.
            </p>

            <Link
              href={
                monitorId
                  ? `/dashboard/monitors/${monitorId}`
                  : "/dashboard/monitors"
              }
              className="apeiro-btn apeiro-btn-primary mt-5"
            >
              Back to monitor
            </Link>
          </div>
        </div>
      </AppShell>
    );
  }

  const typeMeta = TYPE_META[diff.type];
  const TypeIcon = typeMeta.icon;

  const priceContext = diff.type === "price"
    ? priceDiffFromSummary(diff.summary)
    : null;

  const diffTitle = `${monitor?.name ?? "Monitor"} — ${typeMeta.label}`;

  return (
    <AppShell>
      <div className="relative mx-auto max-w-6xl px-0 py-2 lg:py-4">
        <div
          aria-hidden="true"
          className="absolute -z-10 left-1/2 top-0 h-72 w-72 -translate-x-1/2 bg-indigo-500/10 blur-3xl rounded-full pointer-events-none"
        />
        <div className="apeiro-stagger stagger-1">
          <DashboardHeader
            title={diff.summary || "Change detected"}
            parentHref={`/dashboard/monitors/${monitorId}`}
            parentLabel={monitor?.name ?? "Monitor"}
          >
            <Link
              href={`/dashboard/monitors/${monitorId}`}
              className="apeiro-btn apeiro-btn-outline !min-h-[2.25rem] !py-2 text-[0.8125rem]"
            >
              <ExternalLink size={15} aria-hidden="true" />
              View monitor
            </Link>
          </DashboardHeader>
        </div>

        <div className="apeiro-stagger stagger-2 mt-6 mb-6 flex flex-col justify-between gap-4">
          <div className="min-w-0">
            <div className="mb-3">
              <span className={`apeiro-badge border ${typeMeta.className}`}>
                <TypeIcon size={13} aria-hidden="true" />
                {typeMeta.label}
              </span>
            </div>

            <p className="mt-2 text-sm text-slate-400">
              {formatDate(diff.created_at)}
              {monitor ? ` · ${monitor.name}` : ""}
            </p>
          </div>
        </div>

        <div className="apeiro-stagger stagger-3 grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
          <div className="space-y-6">
            <DiffViewer
              title={diffTitle}
              diffType={diff.type}
              summary={diff.summary}
              diffPercentage={diff.diff_percentage}
              createdAt={formatDate(diff.created_at)}
              before={priceContext?.before}
              after={priceContext?.after}
            />

            {prices.length > 0 && (
              <PriceIntelligenceCard points={prices} />
            )}
          </div>

          <aside className="space-y-6">
            <section className="apeiro-card overflow-hidden">
              <div className="border-b border-border p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                  Change metadata
                </p>
              </div>

              <dl className="divide-y divide-border text-sm">
                <div className="flex items-center justify-between gap-3 px-5 py-3.5">
                  <dt className="text-slate-500">Type</dt>
                  <dd className="font-medium capitalize text-slate-200">
                    {diff.type}
                  </dd>
                </div>

                <div className="flex items-center justify-between gap-3 px-5 py-3.5">
                  <dt className="text-slate-500">Diff</dt>
                  <dd className="font-medium tabular-nums text-slate-200">
                    {diff.diff_percentage != null
                      ? `${diff.diff_percentage.toFixed(2)}%`
                      : "—"}
                  </dd>
                </div>

                <div className="flex items-center justify-between gap-3 px-5 py-3.5">
                  <dt className="text-slate-500">Detected</dt>
                  <dd className="text-right font-medium text-slate-200">
                    {formatDate(diff.created_at)}
                  </dd>
                </div>
              </dl>
            </section>

            <section className="apeiro-card overflow-hidden">
              <div className="border-b border-border p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                  Check references
                </p>
              </div>

              <dl className="divide-y divide-border text-sm">
                <div className="px-5 py-3.5">
                  <dt className="text-xs text-slate-500">Previous check</dt>
                  <dd className="mt-1 break-all font-mono text-xs text-slate-300">
                    {diff.previous_check_id}
                  </dd>
                </div>

                <div className="px-5 py-3.5">
                  <dt className="text-xs text-slate-500">Current check</dt>
                  <dd className="mt-1 break-all font-mono text-xs text-slate-300">
                    {diff.current_check_id}
                  </dd>
                </div>

                {diff.artifact_available && diff.artifact_download_url && (
                  <div className="flex items-center justify-between gap-2 px-5 py-3.5">
                    <span className="flex items-center gap-2 text-xs text-slate-300">
                      <PackageOpen size={14} className="shrink-0 text-slate-500" />
                      {diff.artifact_type} artifact captured
                    </span>
                    <button
                      onClick={async () => {
                        try {
                          const { blob, filename } =
                            await downloadDiffArtifact(diff.id);
                          const url = URL.createObjectURL(blob);
                          const anchor = document.createElement("a");
                          anchor.href = url;
                          anchor.download =
                            filename ?? `${diff.id}.bin`;
                          document.body.appendChild(anchor);
                          anchor.click();
                          anchor.remove();
                          URL.revokeObjectURL(url);
                        } catch {
                          setError("Artifact download failed.");
                        }
                      }}
                      className="apeiro-btn apeiro-btn-outline !min-h-[2rem] !py-1.5 text-xs"
                    >
                      Download
                    </button>
                  </div>
                )}
              </dl>
            </section>
          </aside>
        </div>
      </div>
    </AppShell>
  );
}