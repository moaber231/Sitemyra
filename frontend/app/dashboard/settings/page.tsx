"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Mail } from "lucide-react";
import { toast } from "sonner";

import {
  getNotificationPreferences,
  updateNotificationPreferences,
  type NotificationPreferences,
} from "@/lib/api/notifications";
import { BackButton } from "@/components/ui/back-button";
import {
  AlertChannels,
  buildAlertChannels,
} from "@/components/observability/alert-channels";

const defaults: NotificationPreferences = {
  email_on_change: true,
  email_on_failure: true,
  email_on_recovery: true,
};

const PREFERENCES: {
  key: keyof NotificationPreferences;
  title: string;
  description: string;
}[] = [
  {
    key: "email_on_change",
    title: "Content changes",
    description: "Notify me when monitored content changes.",
  },
  {
    key: "email_on_failure",
    title: "Monitor failures",
    description: "Notify me when a monitor starts failing.",
  },
  {
    key: "email_on_recovery",
    title: "Monitor recovery",
    description: "Notify me when a failed monitor recovers.",
  },
];

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [preferences, setPreferences] =
    useState<NotificationPreferences>(defaults);

  const { data, isLoading } = useQuery({
    queryKey: ["notification-preferences"],
    queryFn: getNotificationPreferences,
  });

  useEffect(() => {
    if (data) setPreferences(data);
  }, [data]);

  const mutation = useMutation({
    mutationFn: updateNotificationPreferences,
    onSuccess: (updated) => {
      setPreferences(updated);
      queryClient.setQueryData(
        ["notification-preferences"],
        updated,
      );
      toast.success("Notification settings saved.");
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Could not save settings.",
      );
    },
  });

  function toggle(key: keyof NotificationPreferences) {
    setPreferences((current) => ({
      ...current,
      [key]: !current[key],
    }));
  }

  const emailActive =
    preferences.email_on_change ||
    preferences.email_on_failure ||
    preferences.email_on_recovery;

  const alertChannels = buildAlertChannels({ email: emailActive });

  return (
    <div className="mx-auto max-w-3xl animate-apeiro-fade-up space-y-6">
      <div>
        <BackButton href="/dashboard" label="Back to dashboard" />

        <div className="mt-4">
          <h1 className="text-2xl font-semibold">Account settings</h1>

          <p className="mt-1 text-sm text-slate-400">
            Manage how Sitemyra keeps you informed.
          </p>
        </div>
      </div>

      <div id="alerts" className="scroll-mt-24">
        <AlertChannels
          description="Route Sitemyra alerts to the channels you trust. Email is active — connect Slack and Discord webhooks from the Alert Channels page."
          channels={alertChannels}
        />
      </div>

      <section className="apeiro-card overflow-hidden">
        <div className="border-b border-border p-6">
          <div className="flex items-start gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-secondary text-foreground">
              <Mail size={17} />
            </span>

            <div>
              <h2 className="text-lg font-semibold">
                Email notifications
              </h2>

              <p className="mt-1 text-sm text-slate-400">
                Choose which monitoring events should send an email.
              </p>
            </div>
          </div>
        </div>

        <div className="divide-y divide-border">
          {PREFERENCES.map((preference) => (
            <PreferenceRow
              key={preference.key}
              title={preference.title}
              description={preference.description}
              checked={preferences[preference.key]}
              onChange={() => toggle(preference.key)}
              disabled={isLoading}
            />
          ))}
        </div>

        <div className="flex items-center justify-between gap-4 border-t border-border bg-secondary/40 px-6 py-4">
          <p className="text-xs text-slate-400">
            {isLoading
              ? "Loading your preferences…"
              : "Preferences are saved to your account."}
          </p>

          <button
            type="button"
            onClick={() => mutation.mutate(preferences)}
            disabled={mutation.isPending || isLoading}
            className="apeiro-btn apeiro-btn-primary"
          >
            {mutation.isPending ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Mail size={15} />
            )}
            {mutation.isPending ? "Saving..." : "Save changes"}
          </button>
        </div>
      </section>
    </div>
  );
}

function PreferenceRow({
  title,
  description,
  checked,
  onChange,
  disabled,
}: {
  title: string;
  description: string;
  checked: boolean;
  onChange: () => void;
  disabled: boolean;
}) {
  return (
    <label
      className={`flex cursor-pointer items-center justify-between gap-6 px-6 py-4 transition ${
        disabled ? "opacity-60" : "hover:bg-muted/50"
      }`}
    >
      <span>
        <span className="block text-sm font-medium">{title}</span>

        <span className="mt-1 block text-sm text-slate-400">
          {description}
        </span>
      </span>

      <span
        className={`relative h-6 w-11 shrink-0 rounded-full transition-colors duration-200 ${
          checked ? "bg-primary" : "bg-input"
        }`}
        aria-hidden="true"
      >
        <span
          className={`absolute top-0.5 h-5 w-5 rounded-full bg-card shadow transition-transform duration-200 ${
            checked ? "translate-x-[1.375rem]" : "translate-x-0.5"
          }`}
        />
      </span>

      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        className="sr-only"
      />
    </label>
  );
}