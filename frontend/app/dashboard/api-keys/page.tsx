"use client";

import { useEffect, useState } from "react";
import { KeyRound, Loader2, Trash2, Copy } from "lucide-react";
import { toast } from "sonner";

import { AppShell } from "@/components/layout/app-shell";
import {
  createApiKey,
  getApiKeys,
  revokeApiKey,
  type ApiKey,
} from "@/lib/api/developer";
import { getWorkspaces, type Workspace } from "@/lib/api/workspaces";

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [name, setName] = useState("");
  const [workspace, setWorkspace] = useState("");
  const [freshKey, setFreshKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    try {
      setKeys(await getApiKeys());
      setWorkspaces(await getWorkspaces());
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not load API keys.");
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

  async function generate() {
    if (!name.trim()) return toast.error("Name your key.");
    try {
      const created = await createApiKey(
        name.trim(),
        workspace || null,
      );
      setName("");
      setFreshKey(created.key ?? null);
      toast.success("API key generated — copy it now, it won't be shown again.");
      await refresh();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not generate key.");
    }
  }

  if (loading)
    return (
      <AppShell>
        <div className="flex items-center gap-2 py-16 text-sm text-muted-foreground">
          <Loader2 size={16} className="animate-spin" /> Loading API keys…
        </div>
      </AppShell>
    );

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl py-6">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <KeyRound size={22} /> API Keys
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Bearer tokens for programmatic headless monitoring. Use as{" "}
          <code>Authorization: Bearer apeiro_…</code>. Only hashes are stored.
          Workspace-scoped keys require Owner/Admin role.
        </p>

        {freshKey && (
          <div className="mt-4 rounded-2xl border border-accent bg-accent/10 p-4 text-sm">
            <p className="font-medium">Copy your new key now:</p>
            <div className="mt-2 flex items-center gap-2">
              <code className="flex-1 break-all rounded-lg bg-background p-2">
                {freshKey}
              </code>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(freshKey);
                  toast.success("Copied.");
                }}
                className="apeiro-btn apeiro-btn-ghost"
              >
                <Copy size={15} /> Copy
              </button>
            </div>
          </div>
        )}

        <div className="apeiro-card mt-4 flex flex-col gap-3 p-5 sm:flex-row">
          <input
            className="apeiro-input flex-1"
            placeholder="Key name, e.g. CI pipeline"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <select
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm"
            value={workspace}
            onChange={(e) => setWorkspace(e.target.value)}
          >
            <option value="">Personal (no workspace)</option>
            {workspaces.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name} ({w.role})
              </option>
            ))}
          </select>
          <button onClick={generate} className="apeiro-btn apeiro-btn-primary">
            Generate
          </button>
        </div>

        <div className="mt-4 divide-y divide-border rounded-2xl border border-border">
          {keys.map((k) => (
            <div key={k.id} className="flex items-center justify-between p-4 text-sm">
              <div>
                <p className="font-medium">
                  {k.name}{" "}
                  <span className="text-xs text-muted-foreground">
                    · {k.prefix}… · last used {k.last_used_at ?? "never"}
                  </span>
                </p>
              </div>
              <button
                onClick={async () => {
                  await revokeApiKey(k.id);
                  toast.success("Key revoked.");
                  await refresh();
                }}
                aria-label="Revoke key"
                className="rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
          {keys.length === 0 && (
            <p className="p-6 text-sm text-muted-foreground">
              No API keys yet.
            </p>
          )}
        </div>
      </div>
    </AppShell>
  );
}
