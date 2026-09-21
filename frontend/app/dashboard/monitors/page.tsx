"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  Clock3,
  ExternalLink,
  Plus,
  RefreshCw,
  ShieldAlert,
  TriangleAlert,
  XCircle,
  Zap,
} from "lucide-react";
import { getMonitors, type Monitor } from "@/lib/api/monitors";
import { DashboardHeader } from "@/components/navigation/DashboardHeader";

type Filter = "all" | "healthy" | "changed" | "failing" | "paused";

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "healthy", label: "Healthy" },
  { value: "changed", label: "Changed" },
  { value: "failing", label: "Failing" },
  { value: "paused", label: "Paused" },
];

export default function MonitorsPage() {
  const [filter, setFilter] = useState<Filter>("all");

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["monitors"],
    queryFn: () => {
      const token = sessionStorage.getItem("apeiro_access");

      if (!token) {
        window.location.href = "/login";
        return Promise.reject(new Error("Authentication required."));
      }

      return getMonitors(token);
    },
  });

  const monitors = data ?? [];

  const filteredMonitors = useMemo(() => {
    if (filter === "all") {
      return monitors;
    }

    return monitors.filter(
      (monitor: Monitor) => monitor.status === filter,
    );
  }, [monitors, filter]);

  const counts = useMemo(() => {
    const result: Record<Filter, number> = {
      all: monitors.length,
      healthy: 0,
      changed: 0,
      failing: 0,
      paused: 0,
    };

    for (const monitor of monitors) {
      if (monitor.status in result) {
        result[monitor.status as Filter] += 1;
      }
    }

    return result;
  }, [monitors]);

  return (
    <div className="relative space-y-6">
      <div
        aria-hidden="true"
        className="absolute -z-10 left-1/2 top-0 h-72 w-72 -translate-x-1/2 bg-indigo-500/10 blur-3xl rounded-full pointer-events-none"
      />

      <div className="apeiro-stagger stagger-1">
        <DashboardHeader title="Monitors">
          <button
            type="button"
            onClick={() => refetch()}
            disabled={isFetching}
            className="apeiro-btn apeiro-btn-outline !min-h-[2.25rem] !py-2 text-[0.8125rem]"
          >
            <RefreshCw
              size={15}
              aria-hidden="true"
              className={isFetching ? "animate-spin" : ""}
            />
            Refresh
          </button>

          <Link
            href="/dashboard/monitors/new"
            className="apeiro-btn apeiro-btn-primary !min-h-[2.25rem] !py-2 text-[0.8125rem]"
          >
            <Plus size={16} aria-hidden="true" />
            Add monitor
          </Link>
        </DashboardHeader>
      </div>

      <p className="apeiro-stagger stagger-2 -mt-3 text-sm text-slate-400">
        Keep important pages under watch without checking them manually.
      </p>

      {!isLoading && !isError && monitors.length > 0 && (
        <div
          className="apeiro-stagger stagger-2 flex flex-wrap items-center gap-2"
          role="group"
          aria-label="Filter monitors by status"
        >
          {FILTERS.map((item) => (
            <button
              key={item.value}
              type="button"
              onClick={() => setFilter(item.value)}
              aria-pressed={filter === item.value}
              className={`apeiro-btn !min-h-0 !py-1.5 text-xs ${
                filter === item.value
                  ? "apeiro-btn-primary"
                  : "apeiro-btn-outline"
              }`}
            >
              {item.label}
              <span
                className={`rounded-full px-1.5 text-[0.7rem] font-bold tabular-nums ${
                  filter === item.value
                    ? "bg-white/20 text-white"
                    : "bg-slate-800/80 text-slate-400"
                }`}
              >
                {counts[item.value]}
              </span>
            </button>
          ))}
        </div>
      )}

      {isLoading && <MonitorSkeleton />}

      {isError && (
        <div className="apeiro-glass apeiro-stagger stagger-3 p-8 text-center">
          <ShieldAlert
            className="mx-auto text-red-400"
            size={28}
            aria-hidden="true"
          />

          <h2 className="mt-3 font-semibold text-slate-100">
            Something went wrong
          </h2>

          <p className="mt-1 text-sm text-slate-400">
            We couldn&apos;t load your monitors.
          </p>

          <button
            type="button"
            onClick={() => refetch()}
            className="apeiro-btn apeiro-btn-primary mt-5"
          >
            Try again
          </button>
        </div>
      )}

      {!isLoading && !isError && monitors.length === 0 && (
        <div className="apeiro-glass apeiro-stagger stagger-3 relative overflow-hidden p-10 text-center sm:p-14">
          <div
            aria-hidden="true"
            className="absolute -z-0 left-1/2 top-0 h-40 w-72 -translate-x-1/2 bg-indigo-500/10 blur-3xl rounded-full pointer-events-none"
          />
          <div className="relative">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl border border-slate-800 bg-slate-900/80 text-slate-300">
              <Zap size={22} aria-hidden="true" />
            </div>

            <h2 className="mt-5 text-lg font-semibold tracking-tight text-slate-100">
              No monitors yet
            </h2>

            <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-400">
              Start monitoring a website to see uptime, changes, and
              alerts here.
            </p>

            <Link
              href="/dashboard/monitors/new"
              className="apeiro-btn apeiro-btn-primary mt-6"
            >
              <Plus size={16} aria-hidden="true" />
              Create monitor
            </Link>
          </div>
        </div>
      )}

      {!isLoading &&
        !isError &&
        monitors.length > 0 &&
        filteredMonitors.length === 0 && (
          <div className="apeiro-glass p-10 text-center">
            <p className="text-sm text-slate-400">
              No monitors match this filter.
            </p>
          </div>
        )}

      {!isLoading &&
        !isError &&
        monitors.length > 0 &&
        filteredMonitors.length > 0 && (
          <div
            className="grid gap-3"
            role="list"
            aria-label="Monitors"
          >
            {filteredMonitors.map((monitor: Monitor, index) => (
              <MonitorCard
                key={monitor.id}
                monitor={monitor}
                index={index}
              />
            ))}
          </div>
        )}
    </div>
  );
}

function MonitorCard({
  monitor,
  index,
}: {
  monitor: Monitor;
  index: number;
}) {
  const status = monitor.status ?? "never_checked";

  const healthy = status === "healthy";
  const changed = status === "changed";
  const failing = status === "failing";
  const paused = status === "paused";

  const statusClasses = {
    healthy: "bg-emerald-500/10 text-emerald-300 border border-emerald-500/20",
    changed: "bg-amber-500/10 text-amber-300 border border-amber-500/20",
    failing: "bg-red-500/10 text-red-300 border border-red-500/25",
    paused: "bg-slate-800/80 text-slate-400 border border-slate-800",
    never_checked:
      "bg-slate-800/80 text-slate-300 border border-slate-800",
  }[status] ?? "bg-slate-800/80 text-slate-400 border border-slate-800";

  const statusDot = healthy
    ? "status-dot--on-pulse"
    : failing
      ? "status-dot--danger"
      : changed
        ? "status-dot--warning"
        : paused
          ? "status-dot--off"
          : "status-dot--info";

  const statusLabel =
    status === "never_checked"
      ? "Not checked"
      : status.replace("_", " ");

  const stagger = `stagger-${Math.min(3 + index, 8)}`;

  return (
    <Link
      href={`/dashboard/monitors/${monitor.id}`}
      role="listitem"
      aria-label={`${monitor.name}, status ${statusLabel}`}
      style={{ animationDelay: `${Math.min(index * 0.04, 0.24)}s` }}
      className={`monitor-card apeiro-stagger ${stagger} group block p-5`}
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-start gap-3.5">
          <span
            className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border ${
              healthy
                ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
                : changed
                  ? "border-amber-500/20 bg-amber-500/10 text-amber-300"
                  : failing
                    ? "border-red-500/25 bg-red-500/10 text-red-300"
                    : "border-slate-800 bg-slate-800/60 text-slate-400"
            }`}
            aria-hidden="true"
          >
            {healthy ? (
              <CheckCircle2 size={17} />
            ) : changed ? (
              <TriangleAlert size={17} />
            ) : failing ? (
              <XCircle size={17} />
            ) : (
              <Clock3 size={17} />
            )}
          </span>

          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="max-w-full truncate font-semibold tracking-tight text-slate-100">
                {monitor.name}
              </h2>

              <span className={`apeiro-badge ${statusClasses}`}>
                <span
                  className={`status-dot ${statusDot}`}
                  aria-hidden="true"
                />
                <span className="capitalize">{statusLabel}</span>
              </span>
            </div>

            <p className="mt-1.5 flex items-center gap-1.5 truncate text-sm text-slate-400">
              <ExternalLink
                size={13}
                className="shrink-0"
                aria-hidden="true"
              />
              <span className="truncate">{monitor.url}</span>
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-5 sm:flex-col sm:items-end sm:gap-1 sm:self-center">
          <div className="text-left sm:text-right">
            <p className="text-[0.7rem] font-medium uppercase tracking-wide text-slate-500">
              Interval
            </p>
            <p className="mt-0.5 text-sm font-medium tabular-nums text-slate-200">
              {Math.round(monitor.check_interval / 60)} min
            </p>
          </div>

          {monitor.last_response_time_ms != null && (
            <p className="text-xs tabular-nums text-slate-500 sm:text-right">
              {monitor.last_response_time_ms} ms
            </p>
          )}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-slate-800/60 pt-4 text-xs text-slate-400">
        <span className="inline-flex items-center gap-1.5">
          <Clock3 size={13} aria-hidden="true" />
          {monitor.last_checked_at
            ? `Checked ${new Date(
                monitor.last_checked_at,
              ).toLocaleString()}`
            : "Not checked yet"}
        </span>

        {monitor.last_response_time_ms != null && (
          <span className="inline-flex items-center gap-1.5 tabular-nums">
            <Zap size={13} aria-hidden="true" />
            {monitor.last_response_time_ms} ms response
          </span>
        )}

        {monitor.last_status_code != null && (
          <span
            className={`inline-flex items-center rounded-md border px-1.5 py-0.5 font-medium tabular-nums ${
              monitor.last_status_code >= 200 &&
              monitor.last_status_code < 300
                ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
                : "border-red-500/25 bg-red-500/10 text-red-300"
            }`}
          >
            HTTP {monitor.last_status_code}
          </span>
        )}
      </div>
    </Link>
  );
}

function MonitorSkeleton() {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Loading monitors">
      {[1, 2, 3].map((item) => (
        <div key={item} className="apeiro-glass p-5">
          <div className="flex items-center gap-3">
            <div className="apeiro-skeleton h-9 w-9 shrink-0 rounded-xl bg-slate-800/50" />
            <div className="min-w-0 flex-1 space-y-2">
              <div className="apeiro-skeleton h-4 w-40 max-w-full bg-slate-800/50" />
              <div className="apeiro-skeleton h-3 w-64 max-w-full bg-slate-800/50" />
            </div>
            <div className="apeiro-skeleton hidden h-6 w-20 rounded-full bg-slate-800/50 sm:block" />
          </div>

          <div className="mt-4 border-t border-slate-800/60 pt-4">
            <div className="apeiro-skeleton h-3 w-48 max-w-full bg-slate-800/50" />
          </div>
        </div>
      ))}
    </div>
  );
}
