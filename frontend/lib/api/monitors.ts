import { apiFetch } from "./client";

export type Monitor = {
  id: string;
  name: string;
  url: string;
  active: boolean;
  check_interval: number;
  timeout: number;
  status: "healthy" | "changed" | "failing" | "paused" | "never_checked";
  next_check_at: string | null;
  last_checked_at: string | null;
  last_success_at: string | null;
  last_changed_at: string | null;
  last_content_hash: string;
  last_status_code: number | null;
  created_at: string;
  updated_at: string;
  last_response_time_ms: number | null;
};
export type MonitorCheck = {
  id: string;
  monitor: string;
  checked_at: string;
  status_code: number | null;
  response_time_ms: number | null;
  content_hash: string;
  changed: boolean;
  error: string;
  created_at: string;
};

export function getMonitorChecks(
  accessToken: string,
  monitorId: string,
) {
  return apiFetch<MonitorCheck[]>(
    `/api/monitors/${monitorId}/checks/`,
    {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    },
  );
}
export type CreateMonitorInput = {
  name: string;
  url: string;
  check_interval: number;
  timeout: number;
};

export function getMonitors(accessToken: string) {
  return apiFetch<Monitor[]>("/api/monitors/", {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });
}

export function getMonitor(
  accessToken: string,
  monitorId: string,
) {
  return apiFetch<Monitor>(`/api/monitors/${monitorId}/`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });
}

export function createMonitor(
  accessToken: string,
  data: CreateMonitorInput,
) {
  return apiFetch<Monitor>("/api/monitors/", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(data),
  });
}


export type UpdateMonitorInput = {
  name: string;
  url: string;
  check_interval: number;
  timeout: number;
};

export function updateMonitor(
  accessToken: string,
  monitorId: string,
  data: UpdateMonitorInput,
) {
  return apiFetch<Monitor>(`/api/monitors/${monitorId}/`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(data),
  });
}

export function deleteMonitor(
  accessToken: string,
  monitorId: string,
) {
  return apiFetch<void>(`/api/monitors/${monitorId}/`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });
}

export function pauseMonitor(
  accessToken: string,
  monitorId: string,
) {
  return apiFetch<Monitor>(`/api/monitors/${monitorId}/pause/`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });
}

export function resumeMonitor(
  accessToken: string,
  monitorId: string,
) {
  return apiFetch<Monitor>(`/api/monitors/${monitorId}/resume/`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });
}

export function testMonitor(
  accessToken: string,
  monitorId: string,
) {
  return apiFetch<{ detail: string }>(
    `/api/monitors/${monitorId}/test/`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    },
  );
}

export type MonitorChannel = {
  id: string;
  channel_type: string;
  name: string;
  config_preview: string;
  verified: boolean;
  created_at: string;
};

function monitorAuth(accessToken: string) {
  return {
    Authorization: `Bearer ${accessToken}`,
  };
}

export function getMonitorChannels(
  accessToken: string,
  monitorId: string,
) {
  return apiFetch<MonitorChannel[]>(
    `/api/monitors/${monitorId}/channels/`,
    { headers: monitorAuth(accessToken) },
  );
}

export function attachMonitorChannel(
  accessToken: string,
  monitorId: string,
  channelId: string,
) {
  return apiFetch<{
    monitor_id: string;
    channel_id: string;
    channel_type: string;
    attached: boolean;
    created: boolean;
  }>(`/api/monitors/${monitorId}/channels/`, {
    method: "POST",
    headers: monitorAuth(accessToken),
    body: JSON.stringify({ channel_id: channelId }),
  });
}

export function detachMonitorChannel(
  accessToken: string,
  monitorId: string,
  channelId: string,
) {
  return apiFetch<void>(
    `/api/monitors/${monitorId}/channels/${channelId}/`,
    {
      method: "DELETE",
      headers: monitorAuth(accessToken),
    },
  );
}