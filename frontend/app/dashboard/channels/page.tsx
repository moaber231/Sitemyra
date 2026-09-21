"use client";

import { useEffect, useState } from "react";
import { BellRing, Loader2, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { AppShell } from "@/components/layout/app-shell";
import {
  createChannel,
  deleteChannel,
  getChannels,
  testChannel,
  type AlertChannel,
} from "@/lib/api/ops";

const TYPES = ["slack", "discord", "webhook"];
const UNSUPPORTED = new Set(["email", "sms"]);

export default function ChannelsPage() {
  const [channels, setChannels] = useState<AlertChannel[]>([]);
  const [name, setName] = useState("");
  const [type, setType] = useState("slack");
  const [config, setConfig] = useState("");
  const [loading, setLoading] = useState(true);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testNote, setTestNote] = useState<string | null>(null);

  async function refresh() {
    try {
      setChannels(await getChannels());
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not load channels.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!sessionStorage.getItem("apeiro_access")) {
      window.location.href = "/login";
      return;
    }
    refresh();
  }, []);

  async function add() {
    if (!name.trim() || !config.trim())
      return toast.error("Name and webhook URL/key are required.");
    try {
      await createChannel({
        channel_type: type,
        name: name.trim(),
        config: config.trim(),
      });
      setName("");
      setConfig("");
      toast.success("Alert channel saved (secret encrypted at rest).");
      await refresh();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not save channel.");
    }
  }

  async function runTest(id: string) {
    setTestingId(id);
    setTestNote(null);
    try {
      const result = await testChannel(id);
      setTestNote(result.detail);
      toast.success(result.detail);
      await refresh();
    } catch (e) {
      const message = e instanceof Error ? e.message : "Test delivery failed.";
      setTestNote(message);
      toast.error(message);
    } finally {
      setTestingId(null);
    }
  }

  if (loading)
    return (
      <AppShell>
        <div className="flex items-center gap-2 py-16 text-sm text-muted-foreground">
          <Loader2 size={16} className="animate-spin" /> Loading channels…
        </div>
      </AppShell>
    );

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl py-6">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <BellRing size={22} /> Alert Channels
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Slack, Discord, or generic webhooks. Secrets are encrypted at rest
          (Fernet) and only a masked preview is ever displayed. Email alerts
          use your account email (see Settings); SMS is not implemented and
          cannot be created. Workspace channels require Owner/Admin role.
        </p>
        {testNote && (
          <p className="mt-2 text-sm text-muted-foreground" role="status">
            {testNote}
          </p>
        )}

        <div className="apeiro-card mt-6 space-y-3 p-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <input
              className="apeiro-input"
              placeholder="Channel name, e.g. #incidents"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <select
              className="rounded-lg border border-border bg-background px-3 py-2 text-sm"
              value={type}
              onChange={(e) => setType(e.target.value)}
            >
              {TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
          <input
            className="apeiro-input"
            placeholder="Webhook URL or provider key (stored encrypted)"
            value={config}
            onChange={(e) => setConfig(e.target.value)}
          />
          <button onClick={add} className="apeiro-btn apeiro-btn-primary">
            Save channel
          </button>
        </div>

        <div className="mt-4 divide-y divide-border rounded-2xl border border-border">
          {channels.map((ch) => (
            <div key={ch.id} className="flex items-center justify-between gap-3 p-4 text-sm">
              <div className="min-w-0">
                <p className="font-medium">
                  {ch.name}{" "}
                  <span className="text-xs text-muted-foreground">
                    · {ch.channel_type} · {ch.config_preview}
                    {UNSUPPORTED.has(ch.channel_type) && (
                      <> · unsupported (no delivery)</>
                    )}
                    {ch.verified ? <> · verified</> : <> · not verified</>}
                  </span>
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <button
                  onClick={() => runTest(ch.id)}
                  disabled={testingId === ch.id}
                  aria-label={`Test ${ch.name}`}
                  className="rounded-lg px-2 py-2 text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50"
                >
                  {testingId === ch.id ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    "Test"
                  )}
                </button>
                <button
                  onClick={async () => {
                    await deleteChannel(ch.id);
                    await refresh();
                  }}
                  aria-label="Delete channel"
                  className="rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-foreground"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          ))}
          {channels.length === 0 && (
            <p className="p-6 text-sm text-muted-foreground">
              No channels yet — add your first Slack or Discord webhook above.
            </p>
          )}
        </div>
      </div>
    </AppShell>
  );
}
