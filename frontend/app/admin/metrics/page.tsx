"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Database,
  HeartPulse,
  Loader2,
  Play,
  Server,
} from "lucide-react";
import { toast } from "sonner";

import { AppShell } from "@/components/layout/app-shell";
import {
  getDiagnostics,
  getOpsMetrics,
  runDiagnostics,
  type Diagnostics,
  type OpsMetrics,
} from "@/lib/api/ops";

export default function AdminMetricsPage() {
  const [metrics, setMetrics] = useState<OpsMetrics | null>(null);
  const [diag, setDiag] = useState<Diagnostics | null>(null);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    if (!sessionStorage.getItem("apeiro_access")) {
      window.location.href = "/login";
      return;
    }
    Promise.all([getOpsMetrics(), getDiagnostics()])
      .then(([m, d]) => {
        setMetrics(m);
        setDiag(d);
      })
      .catch(() =>
        toast.error("Super-admin access required for /admin/metrics."),
      )
      .finally(() => setLoading(false));
  }, []);

  async function runTest() {
    setTesting(true);
    try {
      setDiag(await runDiagnostics());
      toast.success("Diagnostics executed.");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Diagnostics failed.");
    } finally {
      setTesting(false);
    }
  }

  if (loading)
    return (
      <AppShell>
        <div className="flex items-center gap-2 py-16 text-sm text-muted-foreground">
          <Loader2 size={16} className="animate-spin" /> Loading SaaS metrics…
        </div>
      </AppShell>
    );

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl py-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-warning">
              Secret super-admin dashboard
            </p>
            <h1 className="text-2xl font-semibold tracking-tight">
              SaaS Operations & Telemetry
            </h1>
          </div>
          <button
            onClick={runTest}
            disabled={testing}
            className="apeiro-btn apeiro-btn-primary"
          >
            {testing ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Play size={15} />
            )}
            Run worker health check
          </button>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <Metric
            label="Total MRR"
            value={`$${metrics?.mrr_dollars.toFixed(2) ?? "—"}`}
            hint={`${metrics?.active_subscribers ?? 0} active subscribers`}
            icon={<Database size={17} />}
          />
          <Metric
            label="Registered Users"
            value={String(metrics?.total_users ?? "—")}
            hint={`${metrics?.active_subscribers ?? 0} paying · ${metrics?.past_due_subscriptions ?? 0} past due`}
            icon={<Activity size={17} />}
          />
          <Metric
            label="Checks (24h)"
            value={String(metrics?.checks_24h ?? "—")}
            hint={`${metrics?.failed_checks_24h ?? 0} failed · ${metrics?.active_monitors ?? 0}/${metrics?.total_monitors ?? 0} monitors active`}
            icon={<Server size={17} />}
          />
          <Metric
            label="Queue Latency"
            value={
              metrics?.worker_queue.latency_ms != null
                ? `${metrics.worker_queue.latency_ms} ms`
                : "—"
            }
            hint={`depth ${metrics?.worker_queue.celery_queue_depth ?? "?"} · redis ${metrics?.worker_queue.redis ?? "?"}`}
            icon={<HeartPulse size={17} />}
          />
          <Metric
            label="Disk / Artifacts"
            value={
              metrics?.storage?.used_pct != null
                ? `${metrics.storage.used_pct}% used`
                : "—"
            }
            hint={
              metrics?.storage?.status === "ok"
                ? `${metrics.storage.used_mb} / ${metrics.storage.total_mb} MB · artifacts ${metrics.storage.artifacts_mb} MB (${metrics.storage.artifact_files} files)`
                : (metrics?.storage?.error ?? "disk unavailable")
            }
            icon={<AlertTriangle size={17} />}
          />
        </div>

        <div className="apeiro-card mt-6 p-5">
          <h2 className="font-semibold">Worker & dependency health</h2>
          <div className="mt-3 grid gap-3 text-sm md:grid-cols-3">
            <HealthCard title="Redis" data={diag?.redis} />
            <HealthCard title="Celery / Beat" data={diag?.celery} />
            <HealthCard title="Playwright pool" data={diag?.playwright} />
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            Overall: {diag?.overall ?? "unknown"} · Active monitors:{" "}
            {metrics?.active_monitors ?? "—"} · Churn risk:{" "}
            {metrics?.churn_risk.score ?? "—"}/100 (
            {metrics?.churn_risk.past_due_subscriptions ?? 0} past due) ·
            Canceled (30d): {metrics?.churn_risk.canceled_last_30d ?? "—"} ·
            Failing repeatedly:{" "}
            {metrics?.churn_risk.monitors_failing_repeatedly_24h ?? "—"}
          </p>
        </div>
      </div>
    </AppShell>
  );
}

function Metric({
  label,
  value,
  hint,
  icon,
}: {
  label: string;
  value: string;
  hint?: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="apeiro-card p-5">
      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-secondary">
        {icon}
      </div>
      <p className="mt-4 text-sm text-muted-foreground">{label}</p>
      <p className="text-xl font-semibold tabular-nums">{value}</p>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

function HealthCard({
  title,
  data,
}: {
  title: string;
  data: Record<string, unknown> | undefined;
}) {
  const status = String(data?.status ?? "unknown");
  const ok = status === "ok";
  return (
    <div className="rounded-xl border border-border p-4">
      <p className="flex items-center justify-between font-medium">
        {title}
        <span
          className={`rounded-full px-2 py-0.5 text-xs ${
            ok
              ? "bg-success-muted text-success"
              : "bg-warning-muted text-warning"
          }`}
        >
          {status}
        </span>
      </p>
      <pre className="mt-2 max-h-40 overflow-auto text-[0.7rem] leading-5 text-muted-foreground">
        {JSON.stringify(data ?? {}, null, 2)}
      </pre>
    </div>
  );
}
