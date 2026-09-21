import { apiFetch } from "./client";

export type NotificationPreferences = {
  email_on_change: boolean;
  email_on_failure: boolean;
  email_on_recovery: boolean;
};

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
