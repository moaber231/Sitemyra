"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  BellRing,
  CheckCircle2,
  Clock3,
  ExternalLink,
  FileDiff,
  Gauge,
  Hash,
  LayoutDashboard,
  Loader2,
  Pause,
  Pencil,
  Play,
  RefreshCw,
  ScanSearch,
  Settings2,
  Trash2,
  TriangleAlert,
  XCircle,
} from "lucide-react";

import { AppShell } from "@/components/layout/app-shell";
import { AdvancedMonitoringSection } from "@/components/monitors/advanced-monitoring-section";
import { AdvancedConfigPanel } from "@/components/monitors/advanced-config";
import { MonitorChannelManager } from "@/components/monitors/monitor-channels";
import { DashboardHeader } from "@/components/navigation/DashboardHeader";
import {
  AlertChannels,
  buildAlertChannels,
} from "@/components/observability/alert-channels";
import { Modal } from "@/components/ui/modal";
import {
  deleteMonitor,
  getMonitor,
  getMonitorChecks,
  pauseMonitor,
  resumeMonitor,
  testMonitor,
  updateMonitor,
  type Monitor,
  type MonitorCheck,
} from "@/lib/api/monitors";

type MonitorStatus =
  | "healthy"
  | "changed"
  | "failing"
  | "paused"
  | "never_checked";

type TabId = "overview" | "monitoring" | "changes" | "alerts";

const TABS: { id: TabId; label: string; icon: typeof LayoutDashboard }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "monitoring", label: "Monitoring", icon: ScanSearch },
  { id: "changes", label: "Changes", icon: FileDiff },
  { id: "alerts", label: "Alerts", icon: BellRing },
];

function StatusBadge({ status }: { status: MonitorStatus | string }) {
  const config = {
    healthy: {
      label: "Healthy",
      icon: CheckCircle2,
      className:
        "bg-emerald-500/10 text-emerald-300 border border-emerald-500/20",
      dot: "status-dot--on-pulse",
    },
    changed: {
      label: "Changed",
      icon: TriangleAlert,
      className:
        "bg-amber-500/10 text-amber-300 border border-amber-500/20",
      dot: "status-dot--warning",
    },
    failing: {
      label: "Failing",
      icon: XCircle,
      className: "bg-red-500/10 text-red-300 border border-red-500/25",
      dot: "status-dot--danger",
    },
    paused: {
      label: "Paused",
      icon: Pause,
      className: "bg-slate-800/80 text-slate-400 border border-slate-800",
      dot: "status-dot--off",
    },
    never_checked: {
      label: "Not checked",
      icon: Clock3,
      className: "bg-slate-800/80 text-slate-300 border border-slate-800",
      dot: "status-dot--info",
    },
  }[status as MonitorStatus];

  if (!config) {
    return (
      <span className="apeiro-badge bg-slate-800/80 text-slate-400 border border-slate-800">
        Unknown
      </span>
    );
  }

  const Icon = config.icon;

  return (
    <span className={`apeiro-badge ${config.className}`}>
      <span className={`status-dot ${config.dot}`} aria-hidden="true" />
      <Icon size={13} aria-hidden="true" />
      {config.label}
    </span>
  );
}

function formatDate(value: string | null) {
  if (!value) return "Never";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }

  return date.toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function formatInterval(seconds: number) {
  if (seconds < 3600) {
    return `${seconds / 60} minutes`;
  }

  return `${seconds / 3600} hour${seconds === 3600 ? "" : "s"}`;
}

function responseTone(ms: number) {
  if (ms < 500) return "text-success";
  if (ms < 2000) return "text-warning";
  return "text-danger";
}

export default function MonitorDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const queryClient = useQueryClient();

  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [monitorId, setMonitorId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("overview");

  useEffect(() => {
    const token = sessionStorage.getItem("apeiro_access");

    if (!token) {
      window.location.href = "/login";
      return;
    }

    setAccessToken(token);

    params.then(({ id }) => {
      setMonitorId(id);
      setActiveTab("overview");
    });
  }, [params]);

  const monitorQuery = useQuery<Monitor, Error>({
    queryKey: ["monitor", monitorId],
    queryFn: () => getMonitor(accessToken!, monitorId!),
    enabled: Boolean(accessToken && monitorId),
  });

  const checksQuery = useQuery<MonitorCheck[], Error>({
    queryKey: ["monitor-checks", monitorId],
    queryFn: () => getMonitorChecks(accessToken!, monitorId!),
    enabled: Boolean(accessToken && monitorId),
  });

  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const monitor = monitorQuery.data;

  const [editForm, setEditForm] = useState({
    name: "",
    url: "",
    check_interval: "300",
    timeout: "10",
  });

  useEffect(() => {
    if (!monitor) return;

    setEditForm({
      name: monitor.name,
      url: monitor.url,
      check_interval: String(monitor.check_interval),
      timeout: String(monitor.timeout),
    });
  }, [monitor?.id, monitor?.name, monitor?.url]);

  const refreshMonitor = async () => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: ["monitor", monitorId],
      }),
      queryClient.invalidateQueries({
        queryKey: ["monitor-checks", monitorId],
      }),
      queryClient.invalidateQueries({
        queryKey: ["monitors"],
      }),
    ]);
  };

  const testMutation = useMutation({
    mutationFn: () => testMonitor(accessToken!, monitorId!),
    onSuccess: async () => {
      await refreshMonitor();
      toast.success("Monitor check queued.");
    },
    onError: (error: Error) => {
      toast.error(error.message || "Unable to test monitor.");
    },
  });

  const pauseResumeMutation = useMutation({
    mutationFn: async () => {
      if (monitorQuery.data?.active) {
        return pauseMonitor(accessToken!, monitorId!);
      }

      return resumeMonitor(accessToken!, monitorId!);
    },
    onSuccess: async () => {
      const wasActive = monitorQuery.data?.active;

      await refreshMonitor();

      toast.success(wasActive ? "Monitor paused." : "Monitor resumed.");
    },
    onError: (error: Error) => {
      toast.error(error.message || "Unable to update monitor.");
    },
  });

  const editMutation = useMutation({
    mutationFn: () =>
      updateMonitor(accessToken!, monitorId!, {
        name: editForm.name.trim(),
        url: editForm.url.trim(),
        check_interval: Number(editForm.check_interval),
        timeout: Number(editForm.timeout),
      }),
    onSuccess: async () => {
      setEditOpen(false);
      await refreshMonitor();
      toast.success("Monitor updated.");
    },
    onError: (error: Error) => {
      toast.error(error.message || "Unable to update monitor.");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteMonitor(accessToken!, monitorId!),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["monitors"],
      });

      toast.success("Monitor deleted.");
      window.location.href = "/dashboard/monitors";
    },
    onError: (error: Error) => {
      toast.error(error.message || "Unable to delete monitor.");
    },
  });

  if (!accessToken || !monitorId || monitorQuery.isLoading) {
    return (
      <AppShell>
        <div className="mx-auto max-w-6xl px-0 py-2">
          <DashboardHeader
            title="Monitor"
            parentHref="/dashboard/monitors"
            parentLabel="Monitors"
          />
          <div
            className="flex min-h-[50vh] items-center justify-center gap-2 text-sm text-slate-400"
            role="status"
            aria-label="Loading monitor"
          >
            <Loader2 size={17} className="animate-spin" aria-hidden="true" />
            Loading monitor...
          </div>
        </div>
      </AppShell>
    );
  }

  if (monitorQuery.isError || !monitorQuery.data) {
    return (
      <AppShell>
        <div className="mx-auto max-w-6xl px-0 py-2">
          <DashboardHeader
            title="Monitor"
            parentHref="/dashboard/monitors"
            parentLabel="Monitors"
          />

          <div className="apeiro-glass mt-6 p-8 text-center">
            <h1 className="font-semibold text-slate-100">
              Something went wrong
            </h1>

            <p className="mt-1 text-sm text-slate-400">
              We couldn&apos;t load this monitor.
            </p>
          </div>
        </div>
      </AppShell>
    );
  }

  const currentMonitor = monitorQuery.data;
  const checks = checksQuery.data ?? [];
  const latestCheck = checks[0];

  const actionLoading =
    testMutation.isPending ||
    pauseResumeMutation.isPending ||
    deleteMutation.isPending ||
    editMutation.isPending;

  const successRate =
    checks.length > 0
      ? Math.round(
          (checks.filter(
            (check) => check.status_code != null && check.status_code < 400,
          ).length /
            checks.length) *
            100,
        )
      : null;

  const alertChannels = buildAlertChannels({ email: true });

  return (
    <AppShell>
      <div className="relative mx-auto max-w-6xl px-0 py-2 lg:py-4">
        <div
          aria-hidden="true"
          className="absolute -z-10 left-1/2 top-0 h-72 w-72 -translate-x-1/2 bg-indigo-500/10 blur-3xl rounded-full pointer-events-none"
        />
        <div className="apeiro-stagger stagger-1">
          <DashboardHeader
            title={currentMonitor.name}
            parentHref="/dashboard/monitors"
            parentLabel="Monitors"
          >
            <button
              type="button"
              onClick={() => testMutation.mutate()}
              disabled={actionLoading}
              className="apeiro-btn apeiro-btn-outline !min-h-[2.25rem] !py-2 text-[0.8125rem]"
            >
              {testMutation.isPending ? (
                <Loader2 size={15} className="animate-spin" aria-hidden="true" />
              ) : (
                <RefreshCw size={15} aria-hidden="true" />
              )}
              Test now
            </button>

            <button
              type="button"
              onClick={() => setEditOpen(true)}
              disabled={actionLoading}
              className="apeiro-btn apeiro-btn-secondary !min-h-[2.25rem] !py-2 text-[0.8125rem]"
            >
              <Pencil size={15} aria-hidden="true" />
              Edit
            </button>

            <button
              type="button"
              onClick={() => pauseResumeMutation.mutate()}
              disabled={actionLoading}
              className="apeiro-btn apeiro-btn-primary !min-h-[2.25rem] !py-2 text-[0.8125rem]"
            >
              {pauseResumeMutation.isPending ? (
                <Loader2 size={15} className="animate-spin" aria-hidden="true" />
              ) : currentMonitor.active ? (
                <Pause size={15} aria-hidden="true" />
              ) : (
                <Play size={15} aria-hidden="true" />
              )}

              {currentMonitor.active ? "Pause" : "Resume"}
            </button>

            <button
              type="button"
              onClick={() => setDeleteOpen(true)}
              disabled={actionLoading}
              aria-label={`Delete ${currentMonitor.name}`}
              className="apeiro-btn apeiro-btn-danger !min-h-[2.25rem] !py-2 text-[0.8125rem]"
            >
              <Trash2 size={15} aria-hidden="true" />
              <span className="hidden sm:inline">Delete</span>
            </button>
          </DashboardHeader>
        </div>

        <div className="apeiro-stagger stagger-2 mt-6 mb-6 flex flex-col justify-between gap-4">
          <div className="min-w-0">
            <div className="mb-3">
              <StatusBadge status={currentMonitor.status} />
            </div>

            <a
              href={currentMonitor.url}
              target="_blank"
              rel="noreferrer"
              className="mt-2 inline-flex max-w-full items-center gap-1.5 truncate text-sm text-slate-400 transition-colors duration-200 hover:text-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/60 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 rounded"
            >
              <span className="truncate">{currentMonitor.url}</span>
              <ExternalLink size={13} className="shrink-0" aria-hidden="true" />
            </a>
          </div>
        </div>

        <div
          role="tablist"
          aria-label="Monitor sections"
          className="no-scrollbar apeiro-stagger stagger-3 mb-6 flex items-center gap-1 overflow-x-auto rounded-xl border border-slate-800/80 bg-slate-900/40 p-1 backdrop-blur-xl"
        >
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const selected = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                id={`tab-${tab.id}`}
                aria-selected={selected}
                aria-controls={`panel-${tab.id}`}
                onClick={() => setActiveTab(tab.id)}
                className={`inline-flex shrink-0 items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/60 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 ${
                  selected
                    ? "bg-gradient-to-r from-indigo-600 via-indigo-500 to-violet-600 text-white shadow-[0_0_16px_rgba(99,102,241,0.3)]"
                    : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
                }`}
              >
                <Icon size={15} aria-hidden="true" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {activeTab === "overview" && (
          <div
            role="tabpanel"
            id="panel-overview"
            aria-labelledby="tab-overview"
            className="animate-apeiro-fade-up space-y-6"
          >
            <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <MetricCard
                label="HTTP status"
                icon={<Hash size={17} aria-hidden="true" />}
                value={latestCheck?.status_code?.toString() ?? "—"}
                tone={
                  latestCheck?.status_code != null &&
                  latestCheck.status_code < 400
                    ? "success"
                    : latestCheck?.status_code != null
                      ? "danger"
                      : undefined
                }
              />

              <MetricCard
                label="Response time"
                icon={<Gauge size={17} aria-hidden="true" />}
                value={
                  latestCheck?.response_time_ms != null
                    ? `${latestCheck.response_time_ms} ms`
                    : "—"
                }
                valueTone={
                  latestCheck?.response_time_ms != null
                    ? responseTone(latestCheck.response_time_ms)
                    : undefined
                }
              />

              <MetricCard
                label="Check interval"
                icon={<Clock3 size={17} aria-hidden="true" />}
                value={formatInterval(currentMonitor.check_interval)}
              />

              <MetricCard
                label="Last checked"
                icon={<RefreshCw size={17} aria-hidden="true" />}
                value={formatDate(currentMonitor.last_checked_at)}
                small
              />
            </section>

            <section className="apeiro-glass overflow-hidden">
              <div className="flex flex-col justify-between gap-2 border-b border-border px-5 py-4 sm:flex-row sm:items-center">
                <div className="flex items-center gap-2">
                  <Clock3 size={17} />
                  <h2 className="font-medium">Check history</h2>

                  {successRate != null && (
                    <span
                      className={`rounded-md px-1.5 py-0.5 text-xs font-semibold ${
                        successRate >= 90
                          ? "bg-success-muted text-success"
                          : "bg-danger-muted text-danger"
                      }`}
                    >
                      {successRate}% success
                    </span>
                  )}
                </div>
              </div>

              {checksQuery.isLoading ? (
                <div className="space-y-3 p-6">
                  {[1, 2, 3, 4].map((item) => (
                    <div key={item} className="apeiro-skeleton h-12" />
                  ))}
                </div>
              ) : checks.length === 0 ? (
                <div className="px-5 py-12 text-center text-sm text-slate-400">
                  No checks recorded yet. Run one with
                  <span className="mx-1 font-medium text-slate-100">
                    Test now
                  </span>
                  to get started.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[42rem] text-left text-sm">
                    <thead>
                      <tr className="border-b border-border text-xs uppercase tracking-wide text-slate-400">
                        <th className="px-5 py-3 font-medium">Checked at</th>
                        <th className="px-4 py-3 font-medium">Status</th>
                        <th className="px-4 py-3 font-medium">HTTP</th>
                        <th className="px-4 py-3 font-medium">Response</th>
                        <th className="px-5 py-3 font-medium">Result</th>
                      </tr>
                    </thead>

                    <tbody className="divide-y divide-border">
                      {checks.map((check) => (
                        <tr
                          key={check.id}
                          className="transition-colors hover:bg-muted/50"
                        >
                          <td className="whitespace-nowrap px-5 py-3.5 font-medium">
                            {formatDate(check.checked_at)}
                          </td>

                          <td className="px-4 py-3.5">
                            <span
                              className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-semibold ${
                                check.status_code == null
                                  ? "bg-danger-muted text-danger"
                                  : check.status_code < 400
                                    ? "bg-success-muted text-success"
                                    : "bg-warning-muted text-warning"
                              }`}
                            >
                              {check.status_code == null ? (
                                <XCircle size={12} />
                              ) : (
                                <CheckCircle2 size={12} />
                              )}
                              {check.status_code == null
                                ? "Error"
                                : "OK"}
                            </span>
                          </td>

                          <td className="px-4 py-3.5 tabular-nums text-slate-400">
                            {check.status_code ?? "—"}
                          </td>

                          <td className="px-4 py-3.5 tabular-nums">
                            {check.response_time_ms != null ? (
                              <span className={responseTone(check.response_time_ms)}>
                                {check.response_time_ms} ms
                              </span>
                            ) : (
                              <span className="text-slate-500">—</span>
                            )}
                          </td>

                          <td className="px-5 py-3.5">
                            {check.error ? (
                              <span className="inline-flex items-center gap-1.5 text-xs font-medium text-danger">
                                <TriangleAlert size={12} />
                                <span className="max-w-[16rem] truncate" title={check.error}>
                                  {check.error}
                                </span>
                              </span>
                            ) : (
                              <span
                                className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                                  check.changed
                                    ? "bg-warning-muted text-warning"
                                    : "bg-success-muted text-success"
                                }`}
                              >
                                {check.changed ? "Changed" : "No change"}
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>
        )}

        {activeTab === "monitoring" && (
          <div
            role="tabpanel"
            id="panel-monitoring"
            aria-labelledby="tab-monitoring"
            className="animate-apeiro-fade-up"
          >
            <AdvancedConfigPanel monitorId={monitorId} />
          </div>
        )}

        {activeTab === "changes" && (
          <div
            role="tabpanel"
            id="panel-changes"
            aria-labelledby="tab-changes"
            className="animate-apeiro-fade-up"
          >
            <AdvancedMonitoringSection monitorId={monitorId} />
          </div>
        )}

        {activeTab === "alerts" && (
          <div
            role="tabpanel"
            id="panel-alerts"
            aria-labelledby="tab-alerts"
            className="animate-apeiro-fade-up space-y-6"
          >
            <AlertChannels channels={alertChannels} />

            {accessToken && monitorId && (
              <MonitorChannelManager
                accessToken={accessToken}
                monitorId={monitorId}
              />
            )}

            <div className="apeiro-card flex flex-col justify-between gap-4 p-6 sm:flex-row sm:items-center">
              <div className="flex items-start gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-secondary text-slate-300">
                  <Settings2 size={16} />
                </span>

                <div>
                  <h2 className="text-sm font-semibold">
                    Delivery preferences
                  </h2>

                  <p className="mt-1 text-sm text-slate-400">
                    Choose which monitoring events trigger alerts in
                    Account settings.
                  </p>
                </div>
              </div>

              <Link
                href="/dashboard/settings"
                className="apeiro-btn apeiro-btn-outline shrink-0"
              >
                Alert settings
                <ExternalLink size={14} />
              </Link>
            </div>
          </div>
        )}
      </div>

      <Modal
        open={editOpen}
        onClose={() => setEditOpen(false)}
        title="Edit monitor"
        description="Update how Sitemyra watches this page."
      >
        <form
          onSubmit={(event) => {
            event.preventDefault();
            editMutation.mutate();
          }}
          className="space-y-5"
        >
          <label className="block">
            <span className="mb-2 block text-sm font-medium">
              Monitor name
            </span>

            <input
              value={editForm.name}
              onChange={(event) =>
                setEditForm({ ...editForm, name: event.target.value })
              }
              required
              className="apeiro-input"
            />
          </label>

          <label className="block">
            <span className="mb-2 block text-sm font-medium">URL</span>

            <input
              type="url"
              value={editForm.url}
              onChange={(event) =>
                setEditForm({ ...editForm, url: event.target.value })
              }
              required
              className="apeiro-input"
            />
          </label>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="mb-2 block text-sm font-medium">
                Check interval
              </span>

              <select
                value={editForm.check_interval}
                onChange={(event) =>
                  setEditForm({
                    ...editForm,
                    check_interval: event.target.value,
                  })
                }
                className="apeiro-input"
              >
                <option value="300">Every 5 minutes</option>
                <option value="900">Every 15 minutes</option>
                <option value="1800">Every 30 minutes</option>
                <option value="3600">Every hour</option>
              </select>
            </label>

            <label className="block">
              <span className="mb-2 block text-sm font-medium">
                Request timeout
              </span>

              <select
                value={editForm.timeout}
                onChange={(event) =>
                  setEditForm({
                    ...editForm,
                    timeout: event.target.value,
                  })
                }
                className="apeiro-input"
              >
                <option value="5">5 seconds</option>
                <option value="10">10 seconds</option>
                <option value="15">15 seconds</option>
                <option value="30">30 seconds</option>
                <option value="60">60 seconds</option>
                <option value="120">120 seconds</option>
              </select>
            </label>
          </div>

          <div className="flex justify-end gap-2 border-t border-border pt-4">
            <button
              type="button"
              onClick={() => setEditOpen(false)}
              className="apeiro-btn apeiro-btn-ghost"
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={editMutation.isPending}
              className="apeiro-btn apeiro-btn-primary"
            >
              {editMutation.isPending ? (
                <Loader2 size={15} className="animate-spin" />
              ) : (
                <Pencil size={15} />
              )}
              Save changes
            </button>
          </div>
        </form>
      </Modal>

      <Modal
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        title="Delete monitor"
        description={`This permanently deletes "${currentMonitor.name}" and all of its check history. This cannot be undone.`}
      >
        <div className="flex items-start gap-3 rounded-lg border border-danger/30 bg-danger-muted p-4 text-sm text-danger">
          <TriangleAlert size={17} className="mt-0.5 shrink-0" />
          <span>
            Any active monitoring for this URL will stop immediately.
          </span>
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={() => setDeleteOpen(false)}
            className="apeiro-btn apeiro-btn-ghost"
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={() => deleteMutation.mutate()}
            disabled={deleteMutation.isPending}
            className="apeiro-btn apeiro-btn-danger"
          >
            {deleteMutation.isPending ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Trash2 size={15} />
            )}
            {deleteMutation.isPending ? "Deleting..." : "Delete monitor"}
          </button>
        </div>
      </Modal>
    </AppShell>
  );
}

function MetricCard({
  label,
  icon,
  value,
  tone,
  valueTone,
  small,
}: {
  label: string;
  icon: React.ReactNode;
  value: string;
  tone?: "success" | "danger";
  valueTone?: string;
  small?: boolean;
}) {
  const toneClass =
    tone === "success"
      ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
      : tone === "danger"
        ? "border-red-500/25 bg-red-500/10 text-red-300"
        : "border-slate-800 bg-slate-800/60 text-slate-300";

  return (
    <div className="apeiro-glass p-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
          {label}
        </p>

        <span
          className={`flex h-7 w-7 items-center justify-center rounded-lg border ${toneClass}`}
          aria-hidden="true"
        >
          {icon}
        </span>
      </div>

      <p
        className={`mt-3 font-semibold tracking-tight text-slate-100 tabular-nums ${
          small ? "text-sm leading-5" : "text-2xl"
        } ${valueTone ?? ""}`}
      >
        {value}
      </p>
    </div>
  );
}