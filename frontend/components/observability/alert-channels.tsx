"use client";

import Link from "next/link";
import {
  Hash,
  Mail,
  MessageCircle,
  type LucideIcon,
} from "lucide-react";

export type AlertChannelId = "discord" | "slack" | "email";

export interface AlertChannelConfig {
  id: AlertChannelId;
  label: string;
  description: string;
  connected: boolean;
  meta?: string;
  href?: string;
}

export interface AlertChannelsProps {
  title?: string;
  description?: string;
  channels: AlertChannelConfig[];
}

const CHANNEL_META: Record<
  AlertChannelId,
  { icon: LucideIcon; iconClass: string; chipClass: string }
> = {
  discord: {
    icon: MessageCircle,
    iconClass: "text-indigo-300",
    chipClass: "bg-indigo-500/15",
  },
  slack: {
    icon: Hash,
    iconClass: "text-sky-300",
    chipClass: "bg-sky-500/15",
  },
  email: {
    icon: Mail,
    iconClass: "text-emerald-300",
    chipClass: "bg-emerald-500/15",
  },
};

export const DEFAULT_CHANNELS: Omit<AlertChannelConfig, "connected">[] = [
  {
    id: "discord",
    label: "Discord",
    description: "Webhook notifications to a Discord channel.",
    href: "/dashboard/settings#alerts",
  },
  {
    id: "slack",
    label: "Slack",
    description: "Post alerts to a Slack channel or workspace.",
    href: "/dashboard/settings#alerts",
  },
  {
    id: "email",
    label: "Email",
    description: "Summary and change notifications by email.",
  },
];

export function buildAlertChannels(
  connected: Partial<Record<AlertChannelId, boolean>>,
): AlertChannelConfig[] {
  return DEFAULT_CHANNELS.map((channel) => ({
    ...channel,
    connected: Boolean(connected[channel.id]),
  }));
}

export function AlertChannels({
  title = "Alert channels",
  description = "Route Apeiro alerts to the channels you trust.",
  channels,
}: AlertChannelsProps) {
  const total = channels.length;
  const active = channels.filter((channel) => channel.connected).length;

  return (
    <section className="apeiro-card overflow-hidden">
      <div className="flex flex-col justify-between gap-4 border-b border-border p-6 sm:flex-row sm:items-center">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
            Integrations
          </p>

          <h2 className="mt-2 text-lg font-semibold">{title}</h2>

          <p className="mt-1 text-sm text-slate-400">{description}</p>
        </div>

        <span className="inline-flex shrink-0 items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-300">
          <span className="status-dot status-dot--on" aria-hidden="true" />
          {active}/{total} active
        </span>
      </div>

      <div className="grid gap-3 p-6 sm:grid-cols-2 lg:grid-cols-4">
        {channels.map((channel) => {
          const meta = CHANNEL_META[channel.id];
          const Icon = meta.icon;

          const content = (
            <>
              <div className="flex items-start justify-between gap-3">
                <span
                  className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${meta.chipClass} ${meta.iconClass}`}
                >
                  <Icon size={17} />
                </span>

                <span className="inline-flex items-center gap-1.5 text-xs font-medium">
                  <span
                    className={`status-dot ${
                      channel.connected
                        ? "status-dot--on"
                        : "status-dot--off"
                    }`}
                    aria-hidden="true"
                  />
                  <span
                    className={
                      channel.connected
                        ? "text-emerald-300"
                        : "text-slate-500"
                    }
                  >
                    {channel.connected ? "Active" : "Not connected"}
                  </span>
                </span>
              </div>

              <p className="mt-4 text-sm font-semibold">{channel.label}</p>

              <p className="mt-1 text-xs leading-5 text-slate-400">
                {channel.connected && channel.meta
                  ? channel.meta
                  : channel.description}
              </p>
            </>
          );

          const base = `apeiro-interactive relative flex flex-col rounded-xl border p-4 text-left ${
            channel.connected
              ? "border-emerald-500/30 bg-emerald-500/[0.04]"
              : "border-border bg-card hover:border-slate-700"
          }`;

          return channel.href ? (
            <Link key={channel.id} href={channel.href} className={base}>
              {content}
            </Link>
          ) : (
            <div key={channel.id} className={base}>
              {content}
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default AlertChannels;