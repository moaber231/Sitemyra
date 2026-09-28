import { apiFetch } from "./client";

export type NotificationPreferences = {
  email_on_change: boolean;
  email_on_failure: boolean;
  email_on_recovery: boolean;
  email_weekly_digest: boolean;
};

export type NotificationDeliveryHistory = {
  channel_type: string;
  status: "delivered" | "failed" | "skipped" | string;
  attempts: number;
  created_at: string;
};

export type NotificationHistoryItem = {
  id: string;
  monitor_id: string;
  monitor_name: string;
  event_type: "change" | "failure" | "recovery" | string;
  created_at: string;
  deliveries: NotificationDeliveryHistory[];
};

export type NotificationHistoryPage = {
  count: number;
  limit: number;
  offset: number;
  next_offset: number | null;
  results: NotificationHistoryItem[];
};

export function getNotificationHistory(limit = 20, offset = 0) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return apiFetch<NotificationHistoryPage>(
    `/api/notifications/history/?${params.toString()}`,
  );
}

export function getNotificationPreferences() {
  return apiFetch<NotificationPreferences>(
    "/api/notifications/preferences/",
  );
}

export function updateNotificationPreferences(
  data: NotificationPreferences,
) {
  return apiFetch<NotificationPreferences>(
    "/api/notifications/preferences/",
    {
      method: "PATCH",
      body: JSON.stringify(data),
    },
  );
}
