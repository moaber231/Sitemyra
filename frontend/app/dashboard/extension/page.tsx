"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, Copy, Loader2, Puzzle, ShieldCheck, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { AppShell } from "@/components/layout/app-shell";
import { DashboardHeader } from "@/components/navigation/DashboardHeader";
import { Note, SectionLabel, relativeTime } from "@/components/intelligence/primitives";
import {
  createExtensionSession,
  getExtensionSessions,
  revokeExtensionSession,
} from "@/lib/api/intelligence";

/**
 * Browser extension sessions (Phase 6).
 *
 * The page that mints the one credential that ever lives in a browser, and
 * the place to revoke it. The token is shown exactly once.
 */
export default function ExtensionPage() {
  const [issued, setIssued] = useState<{ token: string; warning: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const [label, setLabel] = useState("Chrome extension");
  const queryClient = useQueryClient();

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["extension-sessions"],
    queryFn: getExtensionSessions,
    retry: false,
  });

  const create = useMutation({
    mutationFn: () => createExtensionSession(label.trim() || "Browser extension"),
    onSuccess: (session) => {
      setIssued({ token: session.token, warning: session.warning });
      setCopied(false);
      void queryClient.invalidateQueries({ queryKey: ["extension-sessions"] });
    },
    onError: (caught) =>
      toast.error(caught instanceof Error ? caught.message : "Could not create a session."),
  });

  const revoke = useMutation({
    mutationFn: (id: string) => revokeExtensionSession(id),
    onSuccess: () => {
      toast.success("Session revoked. The extension stops working immediately.");
      void queryClient.invalidateQueries({ queryKey: ["extension-sessions"] });
    },
    onError: (caught) =>
      toast.error(caught instanceof Error ? caught.message : "Could not revoke the session."),
  });

  const sessions = data?.sessions ?? [];

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl space-y-6">
        <div className="apeiro-stagger stagger-1">
          <DashboardHeader title="Browser extension" />
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Monitor any public competitor page from the browser you are already using. The
            extension is a convenience — everything it does is also available in the app.
          </p>
        </div>

        <Note>
          <ShieldCheck size={12} className="mr-1 inline" aria-hidden="true" />
          <span className="font-semibold">Do not want a token in your browser?</span> Use the
          bookmarklet instead. It contains no token and calls no API — it just opens Sitemyra
          with the page you are on.
        </Note>

        <section className="apeiro-stagger stagger-2 apeiro-card p-6">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <Puzzle size={15} className="text-accent" aria-hidden="true" />
            Create an extension session
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            The token can read and create monitors. It cannot reach billing, alert channels,
            exports, reports or agency administration — the API refuses those requests
            outright.
          </p>

          <div className="mt-4 flex flex-col gap-3 sm:flex-row">
            <input
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              aria-label="Label for this session"
              placeholder="Chrome on my laptop"
              className="apeiro-input flex-1"
            />
            <button
              type="button"
              onClick={() => create.mutate()}
              disabled={create.isPending}
              className="apeiro-btn apeiro-btn-primary shrink-0"
            >
              {create.isPending ? <Loader2 size={15} className="animate-spin" aria-hidden="true" /> : null}
              Create session
            </button>
          </div>

          {issued ? (
            <div className="mt-4 rounded-2xl border border-warning/30 bg-warning-muted/50 p-4">
              <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-warning">
                <AlertTriangle size={12} aria-hidden="true" />
                Shown once
              </p>
              <code className="mt-2 block break-all rounded-lg bg-card p-3 font-mono text-xs text-foreground">
                {issued.token}
              </code>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(issued.token);
                      setCopied(true);
                      window.setTimeout(() => setCopied(false), 2500);
                    } catch {
                      toast.error("Copy failed — select the token manually.");
                    }
                  }}
                  className="apeiro-btn apeiro-btn-outline !min-h-0 !py-2 text-xs"
                >
                  {copied ? <Check size={13} aria-hidden="true" /> : <Copy size={13} aria-hidden="true" />}
                  {copied ? "Copied" : "Copy token"}
                </button>
              </div>
              <p className="mt-3 text-xs leading-5 text-foreground">{issued.warning}</p>
            </div>
          ) : null}
        </section>

        <section className="apeiro-stagger stagger-3">
          <h2 className="mb-3 text-sm font-semibold text-foreground">
            Your sessions{data ? ` (${sessions.length})` : ""}
          </h2>

          {isLoading ? (
            <div className="apeiro-card h-24 animate-pulse bg-muted/40" aria-busy="true" />
          ) : isError ? (
            <div className="apeiro-card p-8 text-center" role="alert">
              <p className="text-sm text-danger">
                {(error as Error)?.message ?? "Sitemyra could not load your sessions."}
              </p>
            </div>
          ) : sessions.length === 0 ? (
            <Note>No extension sessions yet.</Note>
          ) : (
            <ul className="divide-y divide-border overflow-hidden rounded-2xl border border-border bg-card">
              {sessions.map((session) => (
                <li key={session.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3.5">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">{session.label}</p>
                    <p className="mt-0.5 font-mono text-xs text-muted-foreground">
                      {session.prefix}… · created {relativeTime(session.created_at)}
                      {session.last_used_at ? ` · last used ${relativeTime(session.last_used_at)}` : ""}
                    </p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      Expires {relativeTime(session.expires_at)} · scope{" "}
                      <code className="font-mono">{session.scopes}</code>
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <span
                      className={`apeiro-badge ${
                        session.is_active ? "bg-success-muted text-success" : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {session.is_active ? "Active" : session.revoked_at ? "Revoked" : "Expired"}
                    </span>
                    {session.is_active ? (
                      <button
                        type="button"
                        onClick={() => revoke.mutate(session.id)}
                        disabled={revoke.isPending}
                        className="apeiro-btn apeiro-btn-danger !min-h-0 !py-1.5 text-xs"
                      >
                        <Trash2 size={12} aria-hidden="true" />
                        Revoke
                      </button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}

          <p className="mt-4 text-xs leading-5 text-muted-foreground">
            <SectionLabel>Why the scope is narrow</SectionLabel>{" "}
            A credential in a browser is the highest-risk surface in the product, so the server
            enforces the limit rather than trusting the extension: any request from an
            extension token to an endpoint outside the monitor read/write allowlist is refused
            before the view runs.
          </p>
        </section>
      </div>
    </AppShell>
  );
}
