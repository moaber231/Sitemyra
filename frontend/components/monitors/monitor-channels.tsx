"use client";

import { useCallback, useEffect, useState } from "react";
import { BellRing, Loader2, PlugZap, FlaskConical } from "lucide-react";
import { toast } from "sonner";

import {
  attachMonitorChannel,
  detachMonitorChannel,
  getMonitorChannels,
  type MonitorChannel,
} from "@/lib/api/monitors";
import { getChannels, testChannel, type AlertChannel } from "@/lib/api/ops";

export function MonitorChannelManager({
  accessToken,
  monitorId,
}: {
  accessToken: string;
  monitorId: string;
}) {
  const [all, setAll] = useState<AlertChannel[]>([]);
  const [assigned, setAssigned] = useState<MonitorChannel[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [channels, links] = await Promise.all([
        getChannels(),
        getMonitorChannels(accessToken, monitorId),
      ]);
      setAll(channels);
      setAssigned(links);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not load channels.");
    } finally {
      setLoading(false);
    }
  }, [accessToken, monitorId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const assignedIds = new Set(assigned.map((c) => c.id));

  async function toggle(channelId: string, attached: boolean) {
    setBusy(channelId);
    setNotice(null);
    try {
      if (attached) {
        await detachMonitorChannel(accessToken, monitorId, channelId);
        setNotice("Channel detached from this monitor.");
      } else {
        await attachMonitorChannel(accessToken, monitorId, channelId);
        setNotice("Channel attached — this monitor will notify it.");
      }
      await refresh();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not update channel.");
    } finally {
      setBusy(null);
    }
  }

  async function runTest(channelId: string) {
    setBusy(channelId);
    try {
      const result = await testChannel(channelId);
      setNotice(result.detail);
      toast.success(result.detail);
      await refresh();
    } catch (e) {
      const message = e instanceof Error ? e.message : "Test delivery failed.";
      setNotice(message);
      toast.error(message);
    } finally {
      setBusy(null);
    }
  }

  if (loading) {
    return (
      <div className="apeiro-card flex items-center gap-2 p-6 text-sm text-slate-400">
        <Loader2 size={15} className="animate-spin" /> Loading alert routing…
      </div>
    );
  }

  return (
    <div className="apeiro-card p-6">
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-secondary text-slate-300">
          <BellRing size={16} />
        </span>
        <div>
          <h2 className="text-sm font-semibold">Monitor notifications</h2>
          <p className="mt-1 text-sm text-slate-400">
            This monitor notifies only its attached channels. Email alerts go
            to your account email (see Settings).
          </p>
        </div>
      </div>

      {all.length === 0 ? (
        <p className="mt-4 text-sm text-slate-400">
          No channels yet — create one on the{" "}
          <a href="/dashboard/channels" className="underline">
            Alert Channels
          </a>{" "}
          page, then attach it here.
        </p>
      ) : (
        <ul className="mt-4 divide-y divide-border rounded-xl border border-border">
          {all.map((ch) => {
            const attached = assignedIds.has(ch.id);
            const working = busy === ch.id;
            return (
              <li
                key={ch.id}
                className="flex flex-col gap-2 p-4 text-sm sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <p className="font-medium">
                    {ch.name}{" "}
                    <span className="text-xs text-muted-foreground">
                      · {ch.channel_type} · {ch.config_preview}
                    </span>
                  </p>
                  <p className="mt-0.5 text-xs text-slate-400">
                    {ch.verified ? "Verified" : "Not verified yet"}
                    {attached ? " · attached to this monitor" : ""}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <button
                    type="button"
                    disabled={working}
                    onClick={() => runTest(ch.id)}
                    className="apeiro-btn apeiro-btn-outline !min-h-[2rem] !py-1.5 text-xs"
                  >
                    {working ? (
                      <Loader2 size={13} className="animate-spin" />
                    ) : (
                      <FlaskConical size={13} />
                    )}
                    Test
                  </button>
                  <button
                    type="button"
                    disabled={working}
                    onClick={() => toggle(ch.id, attached)}
                    className={`apeiro-btn !min-h-[2rem] !py-1.5 text-xs ${
                      attached
                        ? "apeiro-btn-ghost"
                        : "apeiro-btn-primary"
                    }`}
                  >
                    {working ? (
                      <Loader2 size={13} className="animate-spin" />
                    ) : (
                      <PlugZap size={13} />
                    )}
                    {attached ? "Detach" : "Attach"}
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {notice && (
        <p className="mt-3 text-xs text-slate-400" role="status">
          {notice}
        </p>
      )}
    </div>
  );
}
