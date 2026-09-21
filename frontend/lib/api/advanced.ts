import { apiFetch, apiFetchBlob } from "./client";

export type AdvancedMode =
  | "http"
  | "dom"
  | "screenshot"
  | "price";

export interface AdvancedConfig {
  mode: AdvancedMode;
  selector: string;
  price_selector: string;
  price_currency: string;
  screenshot_threshold: number;
}

export interface ChangeDiff {
  id: string;
  type: "dom" | "screenshot" | "price";
  summary: string;
  diff_percentage: number | null;
  artifact_available: boolean;
  artifact_type: "dom" | "screenshot" | "price";
  artifact_download_url: string | null;
  previous_check_id: string;
  current_check_id: string;
  created_at: string;
}

export interface PricePoint {
  id: string;
  check_id: string;
  price: string;
  currency: string;
  raw_value: string;
  created_at: string;
}

export function getAdvancedConfig(
  accessToken: string,
  monitorId: string,
) {
  return apiFetch<AdvancedConfig>(
    `/api/monitors/${monitorId}/advanced/`,
    {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    },
  );
}

export function updateAdvancedConfig(
  accessToken: string,
  monitorId: string,
  data: Partial<AdvancedConfig>,
) {
  return apiFetch<AdvancedConfig>(
    `/api/monitors/${monitorId}/advanced/`,
    {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    },
  );
}

export function testAdvancedMonitor(
  accessToken: string,
  monitorId: string,
) {
  return apiFetch<{
    status: string;
    task_id: string;
    monitor_id: string;
  }>(
    `/api/monitors/${monitorId}/advanced/test/`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    },
  );
}

export function getMonitorDiffs(
  accessToken: string,
  monitorId: string,
) {
  return apiFetch<ChangeDiff[]>(
    `/api/monitors/${monitorId}/diffs/`,
    {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    },
  );
}

export function downloadDiffArtifact(diffId: string) {
  return apiFetchBlob(`/api/monitors/artifacts/${diffId}/download/`);
}

export function getMonitorPrices(
  accessToken: string,
  monitorId: string,
) {
  return apiFetch<PricePoint[]>(
    `/api/monitors/${monitorId}/prices/`,
    {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    },
  );
}