import { apiFetch } from "./client";

export type AlertChannel = {
  id: string;
  channel_type: string;
  name: string;
  workspace: string | null;
  config_preview: string;
  verified: boolean;
  created_at: string;
};

export function getChannels() {
  return apiFetch<AlertChannel[]>("/api/notifications/channels/");
}

export function createChannel(data: {
  channel_type: string;
  name: string;
  workspace?: string | null;
  config: string;
}) {
  return apiFetch<AlertChannel>("/api/notifications/channels/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function deleteChannel(id: string) {
  return apiFetch<void>(`/api/notifications/channels/${id}/`, {
    method: "DELETE",
  });
}

export type ChannelTestResult = {
  ok: boolean;
  channel_id: string;
  channel_type: string;
  verified: boolean;
  config_preview: string;
  attempts: number;
  detail: string;
  status_code?: number;
};

export function testChannel(id: string) {
  return apiFetch<ChannelTestResult>(
    `/api/notifications/channels/${id}/test/`,
    { method: "POST" },
  );
}

export type MonitorChannelLink = {
  id: string;
  channel_type: string;
  name: string;
  config_preview: string;
  verified: boolean;
  created_at: string;
};

export type OpsMetrics = {
  total_users: number | null;
  mrr_cents: number;
  mrr_dollars: number;
  active_subscribers: number;
  past_due_subscriptions: number;
  checks_24h: number;
  failed_checks_24h: number;
  active_monitors: number;
  total_monitors: number;
  worker_queue: {
    latency_ms: number | null;
    redis: string;
    celery_queue_depth: number | null;
    queue_latency_ms: number | null;
  };
  storage: {
    status: string;
    path?: string;
    total_mb?: number;
    used_mb?: number;
    free_mb?: number;
    used_pct?: number;
    artifacts_mb?: number;
    artifact_files?: number;
    error?: string;
  };
  churn_risk: {
    past_due_subscriptions: number;
    canceled_last_30d: number;
    monitors_failing_repeatedly_24h: number;
    score: number;
  };
  generated_at: string;
};

export type Diagnostics = {
  overall: string;
  redis: Record<string, unknown>;
  celery: Record<string, unknown>;
  playwright: Record<string, unknown>;
  test_dispatch: Record<string, unknown> | null;
};

export function getOpsMetrics() {
  return apiFetch<OpsMetrics>("/api/admin/metrics/");
}

export function getDiagnostics() {
  return apiFetch<Diagnostics>("/api/admin/diagnostics/");
}

export function runDiagnostics() {
  return apiFetch<Diagnostics>("/api/admin/diagnostics/", { method: "POST" });
}

export function complianceUrl(type: "csv" | "pdf") {
  const base =
    process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  return `${base}/api/monitors/export/compliance/?type=${type}`;
}
