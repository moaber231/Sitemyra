"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  ExternalLink,
  Loader2,
  Plus,
  ShieldCheck,
  TriangleAlert,
  XCircle,
} from "lucide-react";

import { AppShell } from "@/components/layout/app-shell";
import { getMonitors } from "@/lib/api/monitors";

type MonitorStatus =
  | "healthy"
  | "changed"
  | "failing"
  | "paused"
  | "never_checked";

function StatusBadge({ status }: { status: MonitorStatus | string }) {
  const config = {
    healthy: {
      label: "Healthy",
      className: "bg-success-muted text-success",
      dot: "bg-success",
      pulse: true,
    },
    changed: {
      label: "Changed",
      className: "bg-warning-muted text-warning",
      dot: "bg-warning",
      pulse: false,
    },
    failing: {
      label: "Failing",
      className: "bg-danger-muted text-danger",
      dot: "bg-danger",
      pulse: false,
    },
    paused: {
      label: "Paused",
      className: "bg-muted text-muted-foreground",
      dot: "bg-muted-foreground",
      pulse: false,
    },
    never_checked: {
      label: "Not checked",
      className: "bg-secondary text-secondary-foreground",
      dot: "bg-muted-foreground",
      pulse: false,
    },
  }[status as MonitorStatus];

  if (!config) {
    return (
      <span className="apeiro-badge bg-muted text-muted-foreground">
        Unknown
      </span>
    );
  }

  return (
    <span
      className={`apeiro-badge ${config.className}`}
      title={`${config.label} — updated live`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${config.dot} ${
          config.pulse ? "animate-apeiro-pulse" : ""
        }`}
      />
      {config.label}
    </span>
  );
}

export default function DashboardPage() {
  const [accessToken, setAccessToken] = useState<string | null>(null);

  useEffect(() => {
    const token = sessionStorage.getItem("apeiro_access");

    if (!token) {
      window.location.href = "/login";
      return;
    }

    setAccessToken(token);
  }, []);

  const {
    data: monitors = [],
    isLoading: loading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["monitors"],
    queryFn: () => getMonitors(accessToken!),
    enabled: Boolean(accessToken),
    refetchInterval: 30_000,
  });

  const changedCount = monitors.filter(
    (monitor) => monitor.status === "changed",
  ).length;

  const failingCount = monitors.filter(
    (monitor) => monitor.status === "failing",
  ).length;

  const activeCount = monitors.filter(
    (monitor) => monitor.active,
  ).length;

  const recentChanges = monitors
    .filter((monitor) => monitor.last_changed_at)
    .sort(
      (left, right) =>
        new Date(right.last_changed_at!).getTime() -
        new Date(left.last_changed_at!).getTime(),
    )
    .slice(0, 4);
  const latestChanged = recentChanges[0];

  const mostRecentCheck = monitors
    .filter((monitor) => monitor.last_checked_at)
    .sort(
      (left, right) =>
        new Date(right.last_checked_at!).getTime() -
        new Date(left.last_checked_at!).getTime(),
    )[0];

  const attentionCount = changedCount + failingCount;

  if (!accessToken || loading) {
    return (
      <AppShell>
        <div className="flex items-center gap-2 py-16 text-sm text-muted-foreground" aria-busy="true">
          <Loader2 size={16} className="animate-spin" /> Loading your overview…
        </div>
      </AppShell>
    );
  }

  if (isError) {
    return (
      <AppShell>
        <div className="apeiro-card mx-auto mt-8 max-w-2xl p-6" role="alert">
          <h1 className="font-semibold">Your overview could not load.</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {error instanceof Error ? error.message : "Check your connection and try again."}
          </p>
          <button type="button" onClick={() => void refetch()} className="apeiro-btn apeiro-btn-primary mt-4">
            Try again
          </button>
        </div>
      </AppShell>
    );
  }

  if (monitors.length === 0) {
    return (
      <AppShell>
        <div className="mx-auto max-w-3xl py-10">
          <section className="rounded-2xl border border-border bg-card px-6 py-12 text-center sm:px-10">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-primary text-accent">
              <ShieldCheck size={23} />
            </div>
            <h1 className="mt-5 text-2xl font-semibold tracking-tight">
              Monitor your first competitor
            </h1>
            <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-muted-foreground">
              Add a public website. Sitemyra will find pages worth watching and let you choose what to monitor.
            </p>
            <Link
              href="/dashboard/monitors/new"
              className="apeiro-btn apeiro-btn-primary mt-6"
            >
              <Plus size={16} /> Add competitor
            </Link>
          </section>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-7xl px-0 py-6 sm:px-0 lg:py-9">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-muted-foreground">
              {attentionCount === 0
                ? "Your monitors are up to date."
                : `${attentionCount} monitor${attentionCount === 1 ? " needs" : "s need"} attention.`}
            </p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
              Here&apos;s what changed.
            </h1>
          </div>
          <Link href="/dashboard/monitors/new" className="apeiro-btn apeiro-btn-primary">
            <Plus size={16} /> Add competitor
          </Link>
        </header>

        <section className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Active monitors"
            value={String(activeCount)}
            hint={`${monitors.length} total`}
            icon={<ShieldCheck size={18} />}
          />

          <StatCard
            label="Changed"
            value={String(changedCount)}
            hint={
              latestChanged
                ? `Last ${formatRelativeTime(latestChanged.last_changed_at!)}`
                : "No changes"
            }
            icon={<TriangleAlert size={18} />}
            tone="warning"
          />

          <StatCard
            label="Needs attention"
            value={String(attentionCount)}
            hint={`${failingCount} failing · ${changedCount} changed`}
            icon={<XCircle size={18} />}
            tone={attentionCount > 0 ? "danger" : "success"}
          />

          <StatCard
            label="Last checked"
            value={mostRecentCheck ? formatRelativeTime(mostRecentCheck.last_checked_at!) : "Not yet"}
            hint={mostRecentCheck ? mostRecentCheck.name : "No completed checks"}
            icon={<Clock3 size={18} />}
          />
        </section>

        <section className="apeiro-card mt-6 overflow-hidden">
          <div className="flex items-center justify-between gap-4 border-b border-border px-5 py-4 sm:px-6">
            <div>
              <h2 className="font-semibold tracking-tight">Recent changes</h2>
              <p className="mt-0.5 text-sm text-muted-foreground">What changed on the pages you watch</p>
            </div>
            <Link href="/dashboard/feed" className="apeiro-btn apeiro-btn-ghost hidden gap-1.5 sm:inline-flex">
              All changes <ArrowUpRight size={15} />
            </Link>
          </div>
          {recentChanges.length ? (
            <ul className="divide-y divide-border">
              {recentChanges.map((monitor) => (
                <li key={monitor.id}>
                  <Link href={`/dashboard/monitors/${monitor.id}`} className="flex flex-wrap items-center justify-between gap-2 px-5 py-4 hover:bg-muted/40 sm:px-6">
                    <span className="min-w-0 truncate text-sm font-medium">{monitor.name}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      Changed {formatRelativeTime(monitor.last_changed_at!)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-5 py-5 text-sm text-muted-foreground sm:px-6">
              No changes recorded yet. New updates will appear here.
            </p>
          )}
        </section>

        <section className="apeiro-card mt-6 overflow-hidden">
          <div className="flex items-center justify-between gap-4 border-b border-border px-5 py-4 sm:px-6">
            <div>
                <h2 className="font-semibold tracking-tight">Your monitors</h2>

                <p className="mt-0.5 text-sm text-muted-foreground">
                Pages Sitemyra checks for changes
                </p>
            </div>

            <Link
              href="/dashboard/monitors"
              className="apeiro-btn apeiro-btn-ghost hidden gap-1.5 sm:inline-flex"
            >
              View all
              <ArrowUpRight size={15} />
            </Link>
          </div>

          <div className="divide-y divide-border">
              {monitors.map((monitor) => (
                <Link
                  key={monitor.id}
                  href={`/dashboard/monitors/${monitor.id}`}
                  className="apeiro-interactive group flex flex-col gap-4 px-5 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-6"
                >
                  <div className="flex min-w-0 items-center gap-3.5">
                    <span
                      className={`hidden h-9 w-9 shrink-0 items-center justify-center rounded-xl sm:flex ${
                        monitor.status === "healthy"
                          ? "bg-success-muted text-success"
                          : monitor.status === "failing"
                            ? "bg-danger-muted text-danger"
                            : monitor.status === "changed"
                              ? "bg-warning-muted text-warning"
                              : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {monitor.status === "healthy" ? (
                        <CheckCircle2 size={17} />
                      ) : monitor.status === "failing" ? (
                        <XCircle size={17} />
                      ) : monitor.status === "changed" ? (
                        <TriangleAlert size={17} />
                      ) : (
                        <Clock3 size={17} />
                      )}
                    </span>

                    <div className="min-w-0">
                      <h3 className="truncate text-sm font-semibold">
                        {monitor.name}
                      </h3>

                      <div className="mt-1 flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
                        <ExternalLink size={12} className="shrink-0" />
                        <span className="truncate">{monitor.url}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between gap-6 pl-0 sm:justify-end sm:pl-3">
                    <div className="flex items-center gap-2">
                      <StatusBadge status={monitor.status} />

                      <span
                        className="hidden text-xs tabular-nums text-muted-foreground sm:inline"
                        title="Response time"
                      >
                        {monitor.last_response_time_ms !== null &&
                        monitor.last_status_code !== null
                          ? `${monitor.last_response_time_ms} ms · ${monitor.last_status_code}`
                          : "No check yet"}
                      </span>
                    </div>

                    <span className="text-xs text-muted-foreground">
                      {formatLastChecked(monitor.last_checked_at)}
                    </span>

                    <ArrowUpRight
                      size={16}
                      className="hidden text-muted-foreground transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 sm:block"
                    />
                  </div>
                </Link>
              ))}
          </div>
        </section>
      </div>
    </AppShell>
  );
}

function formatRelativeTime(value: string) {
  const timestamp = new Date(value).getTime();

  if (Number.isNaN(timestamp)) {
    return "recently";
  }

  const seconds = Math.max(
    0,
    Math.floor((timestamp - Date.now()) / 1000),
  );

  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h ago`;
  return `${Math.round(seconds / 86400)}d ago`;
}

function formatLastChecked(value: string | null) {
  if (!value) {
    return "Never checked";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }

  const elapsed = Date.now() - date.getTime();

  if (elapsed < 60_000) {
    return "Checked just now";
  }

  if (elapsed < 3_600_000) {
    return `Checked ${Math.round(elapsed / 60_000)}m ago`;
  }

  if (elapsed < 86_400_000) {
    return `Checked ${Math.round(elapsed / 3_600_000)}h ago`;
  }

  return `Checked ${date.toLocaleDateString()}`;
}

function StatCard({
  label,
  value,
  hint,
  icon,
  tone,
}: {
  label: string;
  value: string;
  hint: string;
  icon: React.ReactNode;
  tone?: "success" | "warning" | "danger";
}) {
  const iconClass = {
    success: "bg-success-muted text-success",
    warning: "bg-warning-muted text-warning",
    danger: "bg-danger-muted text-danger",
  }[tone ?? "success"];

  return (
    <div className="apeiro-card animate-apeiro-fade-up p-5">
      <div className="flex items-start justify-between gap-3">
        <div
          className={`flex h-10 w-10 items-center justify-center rounded-xl ${
            tone ? iconClass : "bg-secondary text-foreground"
          }`}
        >
          {icon}
        </div>

        <span className="rounded-full bg-muted px-2 py-0.5 text-[0.7rem] font-medium text-muted-foreground">
          LIVE
        </span>
      </div>

      <p className="mt-5 text-sm font-medium text-muted-foreground">
        {label}
      </p>

      <div className="mt-1 flex items-end justify-between gap-2">
        <p className="text-2xl font-semibold tracking-tight tabular-nums">
          {value}
        </p>

        <span className="max-w-[10rem] truncate pb-0.5 text-xs text-muted-foreground">
          {hint}
        </span>
      </div>
    </div>
  );
}
