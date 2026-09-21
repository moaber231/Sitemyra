"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  ExternalLink,
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
  } = useQuery({
    queryKey: ["monitors"],
    queryFn: () => getMonitors(accessToken!),
    enabled: Boolean(accessToken),
    refetchInterval: 30_000,
  });

  const healthyCount = monitors.filter(
    (monitor) => monitor.status === "healthy",
  ).length;

  const changedCount = monitors.filter(
    (monitor) => monitor.status === "changed",
  ).length;

  const failingCount = monitors.filter(
    (monitor) => monitor.status === "failing",
  ).length;

  const activeCount = monitors.filter(
    (monitor) => monitor.active,
  ).length;

  const averageResponse = monitors
    .map((monitor) => monitor.last_response_time_ms)
    .filter((value): value is number => value != null)
    .reduce((total, value) => total + value, 0);

  const averageResponseLabel =
    monitors.length > 0
      ? Math.round(averageResponse / monitors.length) > 0
        ? `${Math.round(averageResponse / monitors.length)} ms avg`
        : "No data yet"
      : "No data yet";

  const latestChanged = monitors
    .filter((monitor) => monitor.last_changed_at)
    .sort(
      (left, right) =>
        new Date(right.last_changed_at!).getTime() -
        new Date(left.last_changed_at!).getTime(),
    )[0];

  const attentionCount = changedCount + failingCount;

  return (
    <AppShell>
      <div className="mx-auto max-w-7xl px-0 py-6 sm:px-0 lg:py-9">
        <div className="animate-apeiro-fade-up">
          <div className="relative overflow-hidden rounded-2xl border border-emerald-500/15 bg-[linear-gradient(135deg,#0d1322_0%,#101c33_55%,#0d1a2e_100%)] p-6 text-slate-100 shadow-[0_20px_60px_rgba(0,0,0,0.45)] sm:p-8">
            <div className="absolute -right-20 -top-24 h-64 w-64 rounded-full bg-accent opacity-[0.10] blur-3xl" />
            <div className="pointer-events-none absolute -left-24 bottom-0 h-56 w-56 rounded-full bg-emerald-500 opacity-[0.08] blur-3xl" />

            <div className="pointer-events-none absolute right-8 top-1/2 hidden -translate-y-1/2 select-none text-[9rem] font-black leading-none tracking-tighter opacity-[0.04] lg:block">
              {attentionCount === 0 ? "ALL GOOD" : "ACTION"}
            </div>

            <div className="relative flex flex-col justify-between gap-7 sm:flex-row sm:items-end">
              <div className="max-w-2xl">
                <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-medium text-slate-200">
                  <Activity size={13} className="text-accent" />
                  {attentionCount === 0
                    ? "Everything looks good"
                    : `${attentionCount} monitor${attentionCount === 1 ? "" : "s"} need attention`}
                </div>

                <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
                  Know when the web changes.
                </h1>

                <p className="mt-2 max-w-xl text-sm leading-6 text-slate-400">
                  Apeiro watches your important pages and tells you when
                  something changes, fails, or comes back online.
                </p>
              </div>

              <Link
                href="/dashboard/monitors/new"
                className="apeiro-btn apeiro-btn-accent shrink-0"
              >
                <Plus size={16} />
                Add monitor
              </Link>
            </div>
          </div>
        </div>

        <section className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Total monitors"
            value={String(monitors.length)}
            hint={`${activeCount} active`}
            icon={<ShieldCheck size={18} />}
          />

          <StatCard
            label="Healthy"
            value={String(healthyCount)}
            hint={averageResponseLabel}
            icon={<CheckCircle2 size={18} />}
            tone="success"
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
            label="Failing"
            value={String(failingCount)}
            hint={failingCount > 0 ? "Needs attention" : "No failures"}
            icon={<XCircle size={18} />}
            tone="danger"
          />
        </section>

        <section className="apeiro-card mt-6 overflow-hidden">
          <div className="flex items-center justify-between gap-4 border-b border-border px-5 py-4 sm:px-6">
            <div>
              <h2 className="font-semibold tracking-tight">Your monitors</h2>

              <p className="mt-0.5 text-sm text-muted-foreground">
                Live monitoring activity
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

          {loading ? (
            <MonitorListSkeleton />
          ) : monitors.length === 0 ? (
            <EmptyState />
          ) : (
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
          )}
        </section>
      </div>
    </AppShell>
  );
}

function EmptyState() {
  return (
    <div className="relative overflow-hidden px-5 py-16 text-center sm:px-6">
      <div className="absolute inset-x-1/3 top-0 h-32 rounded-full bg-accent opacity-10 blur-3xl" />

      <div className="relative">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-primary text-accent shadow-lg">
          <ShieldCheck size={23} />
        </div>

        <h3 className="mt-5 text-base font-semibold">
          Your web watchlist starts here
        </h3>

        <p className="mx-auto mt-1.5 max-w-md text-sm leading-6 text-muted-foreground">
          Add a URL and Apeiro will keep an eye on it for you. You&apos;ll
          know when the content changes or the site goes down.
        </p>

        <Link
          href="/dashboard/monitors/new"
          className="apeiro-btn apeiro-btn-primary mt-6"
        >
          <Plus size={16} />
          Create your first monitor
        </Link>
      </div>
    </div>
  );
}

function MonitorListSkeleton() {
  return (
    <div className="divide-y divide-border">
      {[1, 2, 3].map((item) => (
        <div key={item} className="space-y-3 px-5 py-5 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="apeiro-skeleton h-9 w-9 rounded-xl" />
            <div className="apeiro-skeleton h-4 w-48 max-w-full" />
          </div>
          <div className="apeiro-skeleton h-3 w-72 max-w-full" />
        </div>
      ))}
    </div>
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