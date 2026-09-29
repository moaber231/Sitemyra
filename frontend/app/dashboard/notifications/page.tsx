"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BellRing, CheckCircle2, Clock3, Loader2, RefreshCw, XCircle } from "lucide-react";

import { AppShell } from "@/components/layout/app-shell";
import { DashboardHeader } from "@/components/navigation/DashboardHeader";
import {
  getNotificationHistory,
  type NotificationHistoryItem,
} from "@/lib/api/notifications";

const PAGE_SIZE = 20;

function eventLabel(eventType: string) {
  switch (eventType) {
    case "change":
      return "Change detected";
    case "failure":
      return "Monitor failure";
    case "recovery":
      return "Monitor recovered";
    default:
      return "Monitor notification";
  }
}

function statusLabel(status: string) {
  switch (status) {
    case "delivered":
      return "Delivered";
    case "failed":
      return "Failed";
    case "skipped":
      return "Skipped";
    default:
      return status;
  }
}

function statusStyle(status: string) {
  if (status === "delivered") return "text-success";
  if (status === "failed") return "text-danger";
  return "text-muted-foreground";
}

function StatusIcon({ status }: { status: string }) {
  if (status === "delivered") return <CheckCircle2 size={15} aria-hidden="true" />;
  if (status === "failed") return <XCircle size={15} aria-hidden="true" />;
  return <Clock3 size={15} aria-hidden="true" />;
}

function DeliveryRow({ item }: { item: NotificationHistoryItem }) {
  return (
    <li className="space-y-3 px-4 py-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-foreground">
            {eventLabel(item.event_type)} · {item.monitor_name}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            <Link
              href={`/dashboard/monitors/${item.monitor_id}`}
              className="underline decoration-border underline-offset-2 hover:text-accent"
            >
              View monitor
            </Link>
            <span> · {new Date(item.created_at).toLocaleString()}</span>
          </p>
        </div>
      </div>
      {item.deliveries.length ? (
        <ul className="space-y-2 border-l-2 border-border pl-3">
          {item.deliveries.map((delivery, index) => (
            <li key={`${delivery.channel_type}-${delivery.created_at}-${index}`} className="flex flex-wrap items-center justify-between gap-2 text-xs">
              <span className="text-muted-foreground">{delivery.channel_type}</span>
              <span className={`flex items-center gap-1.5 font-medium ${statusStyle(delivery.status)}`}>
                <StatusIcon status={delivery.status} />
                {statusLabel(delivery.status)} · {delivery.attempts} {delivery.attempts === 1 ? "attempt" : "attempts"}
                <span className="font-normal text-muted-foreground">{new Date(delivery.created_at).toLocaleString()}</span>
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-muted-foreground">Event recorded; no delivery attempt is recorded.</p>
      )}
    </li>
  );
}

export default function NotificationHistoryPage() {
  const [items, setItems] = useState<NotificationHistoryItem[]>([]);
  const [count, setCount] = useState(0);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");

  async function load(offset = 0) {
    if (offset === 0) setLoading(true);
    else setLoadingMore(true);
    setError("");
    try {
      const page = await getNotificationHistory(PAGE_SIZE, offset);
      setItems((current) => (offset === 0 ? page.results : [...current, ...page.results]));
      setCount(page.count);
      setNextOffset(page.next_offset);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load notification history.");
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }

  useEffect(() => {
    if (!sessionStorage.getItem("apeiro_access")) {
      window.location.href = "/login";
      return;
    }
    void load();
  }, []);

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl space-y-5 py-6">
        <div>
          <DashboardHeader
            title="Alerts"
            children={(
              <div className="flex flex-wrap gap-2">
                <Link href="/dashboard/channels" className="apeiro-btn apeiro-btn-outline !min-h-0 !py-2 text-xs">
                  Manage alert destinations
                </Link>
                <Link href="/dashboard/settings#alerts" className="apeiro-btn apeiro-btn-ghost !min-h-0 !py-2 text-xs">
                  Preferences
                </Link>
              </div>
            )}
          />
          <p className="mt-2 text-sm text-muted-foreground">
            See changes, failures, recoveries, and whether each alert was delivered. Destination secrets are never shown here.
          </p>
        </div>

        {error ? (
          <div className="apeiro-card flex items-center justify-between gap-3 p-4" role="alert">
            <p className="text-sm text-danger">{error}</p>
            <button type="button" onClick={() => void load()} className="apeiro-btn apeiro-btn-outline !min-h-0 !py-2 text-xs">
              Retry
            </button>
          </div>
        ) : null}

        {loading ? (
          <div className="flex items-center gap-2 py-12 text-sm text-muted-foreground" aria-busy="true">
            <Loader2 size={16} className="animate-spin" /> Loading notification history…
          </div>
        ) : items.length === 0 ? (
          <div className="apeiro-card flex flex-col items-center gap-3 p-10 text-center">
            <BellRing size={22} className="text-muted-foreground" aria-hidden="true" />
            <p className="text-sm font-medium text-foreground">No alerts recorded yet.</p>
            <p className="max-w-md text-xs leading-5 text-muted-foreground">
              An entry appears when a monitor change, failure, or recovery is dispatched. Configure where alerts go under Alert destinations.
            </p>
          </div>
        ) : (
          <>
            <p className="text-xs text-muted-foreground">{count} delivery record{count === 1 ? "" : "s"}</p>
            <ul className="divide-y divide-border overflow-hidden rounded-2xl border border-border bg-card">
              {items.map((item) => <DeliveryRow key={item.id} item={item} />)}
            </ul>
            {nextOffset !== null ? (
              <button
                type="button"
                onClick={() => void load(nextOffset)}
                disabled={loadingMore}
                className="apeiro-btn apeiro-btn-outline mx-auto"
              >
                {loadingMore ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
                Load more
              </button>
            ) : null}
          </>
        )}
      </div>
    </AppShell>
  );
}
