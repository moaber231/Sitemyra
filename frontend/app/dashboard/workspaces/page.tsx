"use client";

import { useEffect, useState } from "react";
import { Check, Copy, Loader2, Plus, Users } from "lucide-react";
import { toast } from "sonner";

import { AppShell } from "@/components/layout/app-shell";
import {
  acceptInvite,
  createWorkspace,
  getInvites,
  getMembers,
  getWorkspaces,
  inviteMember,
  updateMemberRole,
  type Invite,
  type Member,
  type Workspace,
} from "@/lib/api/workspaces";

export default function WorkspacesPage() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selected, setSelected] = useState<Workspace | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [name, setName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("viewer");
  const [joinToken, setJoinToken] = useState("");
  const [copiedInviteId, setCopiedInviteId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    try {
      const list = await getWorkspaces();
      setWorkspaces(list);
      if (!selected && list.length > 0) setSelected(list[0]);
      else if (selected)
        setSelected(list.find((w) => w.id === selected.id) ?? list[0] ?? null);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not load workspaces.");
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selected) return;
    getMembers(selected.id).then(setMembers).catch(() => setMembers([]));
    getInvites(selected.id).then(setInvites).catch(() => setInvites([]));
  }, [selected]);

  // An emailed invitation lands here as ?invite=<token>. Pre-fill the join
  // box and scroll to it; the user still confirms, and the server still
  // verifies the signed-in email matches the invite.
  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("invite");
    if (!token) return;
    setJoinToken(token);
    toast.message("Invitation link opened. Sign in, then join the workspace.");
    document
      .getElementById("workspace-invite-token")
      ?.scrollIntoView({ block: "center" });
  }, []);

  const canAdmin = selected?.role === "owner" || selected?.role === "admin";

  async function handleCreate() {
    if (!name.trim()) return toast.error("Name your workspace.");
    try {
      const ws = await createWorkspace(name.trim());
      setName("");
      toast.success(`Workspace "${ws.name}" created.`);
      await refresh();
      setSelected(ws);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not create workspace.");
    }
  }

  async function handleInvite() {
    if (!selected || !inviteEmail.trim()) return;
    try {
      const created = await inviteMember(selected.id, inviteEmail.trim(), inviteRole);
      setInviteEmail("");
      setInvites((current) => [
        created,
        ...current.filter((invite) => invite.id !== created.id),
      ]);
      // Only claim an email was sent when the server recorded that outcome.
      if (created.email_status === "sent") {
        toast.success(`Invitation emailed to ${created.email}.`);
      } else if (created.email_status === "queued") {
        toast.success(
          `Invitation created. Sending the email to ${created.email}…`,
        );
      } else {
        toast.success(
          "Invitation created, but the email could not be sent. Copy the link and share it.",
        );
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not invite member.");
    }
  }

  async function handleCopyInvite(invite: Invite) {
    try {
      // Copy the full accept link, not a bare token: it is what the invitee
      // needs, and acceptance still requires the invited address.
      await navigator.clipboard.writeText(invite.accept_url || invite.token);
      setCopiedInviteId(invite.id);
      window.setTimeout(() => setCopiedInviteId(null), 2000);
    } catch {
      toast.error("Copy failed. Select the link and copy it manually.");
    }
  }

  async function handleJoin() {
    if (!joinToken.trim()) return;
    try {
      const res = await acceptInvite(joinToken.trim());
      setJoinToken("");
      toast.success(res.detail);
      await refresh();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Invalid invite token.");
    }
  }

  if (loading)
    return (
      <AppShell>
        <div className="flex items-center gap-2 py-16 text-sm text-muted-foreground">
          <Loader2 size={16} className="animate-spin" /> Loading workspaces…
        </div>
      </AppShell>
    );

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl py-6">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <Users size={22} /> Workspaces
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Group monitors by team. Owners and admins can invite teammates and
          manage shared alerts.
        </p>

        <div className="apeiro-card mt-6 flex flex-col gap-3 p-5 sm:flex-row">
          <input
            className="apeiro-input flex-1"
            placeholder="New workspace name, e.g. Acme Corp"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <button onClick={handleCreate} className="apeiro-btn apeiro-btn-primary">
            <Plus size={16} /> Create workspace
          </button>
        </div>

        <div className="apeiro-card mt-4 flex flex-col gap-3 p-5 sm:flex-row">
          <label className="sr-only" htmlFor="workspace-invite-token">
            Invitation token
          </label>
          <input
            id="workspace-invite-token"
            className="apeiro-input flex-1"
            placeholder="Paste an invitation token (sign in with the invited email)"
            value={joinToken}
            onChange={(e) => setJoinToken(e.target.value)}
          />
          <button onClick={handleJoin} className="apeiro-btn apeiro-btn-ghost">
            Join workspace
          </button>
        </div>

        <div className="mt-6 grid gap-4 lg:grid-cols-3">
          <div className="space-y-2">
            {workspaces.map((w) => (
              <button
                key={w.id}
                onClick={() => setSelected(w)}
                className={`w-full rounded-xl border p-4 text-left transition ${
                  selected?.id === w.id
                    ? "border-accent bg-accent/10"
                    : "border-border hover:bg-muted"
                }`}
              >
                <p className="font-semibold">{w.name}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {w.role} · {w.member_count} member(s)
                </p>
              </button>
            ))}
            {workspaces.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No workspaces yet — create one above.
              </p>
            )}
          </div>

          <div className="apeiro-card p-5 lg:col-span-2">
            {!selected ? (
              <p className="text-sm text-muted-foreground">Select a workspace.</p>
            ) : (
              <>
                <h2 className="font-semibold">
                  {selected.name}{" "}
                  <span className="text-xs font-normal text-muted-foreground">
                    (your role: {selected.role})
                  </span>
                </h2>
                <h3 className="mt-4 text-sm font-medium">Members</h3>
                <div className="mt-2 divide-y divide-border text-sm">
                  {members.map((m) => (
                    <div key={m.id} className="flex items-center justify-between py-2">
                      <span>{m.email}</span>
                      {canAdmin ? (
                        <select
                          className="rounded-lg border border-border bg-background px-2 py-1 text-xs"
                          value={m.role}
                          onChange={async (e) => {
                            try {
                              await updateMemberRole(selected.id, m.id, e.target.value);
                              setMembers(await getMembers(selected.id));
                            } catch (err) {
                              toast.error(
                                err instanceof Error ? err.message : "Role update failed.",
                              );
                            }
                          }}
                        >
                          <option value="viewer">Viewer</option>
                          <option value="admin">Admin</option>
                          <option value="owner">Owner</option>
                        </select>
                      ) : (
                        <span className="text-xs text-muted-foreground">{m.role}</span>
                      )}
                    </div>
                  ))}
                </div>

                {canAdmin && (
                  <>
                    <h3 className="mt-5 text-sm font-medium">Invite teammate</h3>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">
                      Sitemyra emails the invitation. It can only be accepted
                      by signing in as the address you enter.
                    </p>
                    <div className="mt-2 flex flex-col gap-2 sm:flex-row">
                      <input
                        className="apeiro-input flex-1"
                        placeholder="teammate@company.com"
                        value={inviteEmail}
                        onChange={(e) => setInviteEmail(e.target.value)}
                      />
                      <select
                        className="rounded-lg border border-border bg-background px-2 py-2 text-sm"
                        value={inviteRole}
                        onChange={(e) => setInviteRole(e.target.value)}
                      >
                        <option value="viewer">Viewer</option>
                        <option value="admin">Admin</option>
                      </select>
                      <button onClick={handleInvite} className="apeiro-btn apeiro-btn-primary">
                        Invite
                      </button>
                    </div>
                    {invites.length > 0 && (
                      <ul className="mt-3 space-y-2 text-xs text-muted-foreground">
                        {invites.map((i) => (
                          <li
                            key={i.id}
                            className="rounded-lg border border-border p-3"
                          >
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="min-w-0 flex-1 break-all font-medium text-foreground">
                                {i.email} ({i.role})
                              </span>
                              <EmailStatusLabel invite={i} />
                            </div>
                            {i.email_status === "sent" ? (
                              <p className="mt-1">
                                Email delivered to {i.email}. They accept it by
                                signing in with that address.
                              </p>
                            ) : (
                              <>
                                <p className="mt-1">
                                  {i.email_status === "queued"
                                    ? "Sending the invitation email…"
                                    : i.email_error ||
                                      "The email was not sent. Share the link below."}
                                </p>
                                <div className="mt-2 flex flex-wrap items-center gap-2">
                                  <code className="max-w-full break-all rounded bg-muted px-2 py-1 font-mono">
                                    {i.token}
                                  </code>
                                  <CopyButton
                                    invite={i}
                                    copied={copiedInviteId === i.id}
                                    onCopy={handleCopyInvite}
                                  />
                                </div>
                              </>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                  </>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}

function CopyButton({
  invite,
  copied,
  onCopy,
}: {
  invite: Invite;
  copied: boolean;
  onCopy: (invite: Invite) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onCopy(invite)}
      className="apeiro-btn apeiro-btn-outline !min-h-0 !py-1.5 text-xs"
      aria-label={`Copy invitation link for ${invite.email}`}
    >
      {copied ? <Check size={13} /> : <Copy size={13} />}
      {copied ? "Copied" : "Copy link"}
    </button>
  );
}

function EmailStatusLabel({ invite }: { invite: Invite }) {
  const config = {
    sent: {
      label: "Email sent",
      className: "bg-success-muted text-success",
    },
    queued: {
      label: "Sending…",
      className: "bg-secondary text-secondary-foreground",
    },
    failed: {
      label: "Email failed",
      className: "bg-danger-muted text-danger",
    },
    not_configured: {
      label: "Not emailed",
      className: "bg-warning-muted text-warning",
    },
    skipped: {
      label: "Already joined",
      className: "bg-muted text-muted-foreground",
    },
  }[invite.email_status] ?? {
    label: "Not emailed",
    className: "bg-warning-muted text-warning",
  };

  return (
    <span className={`apeiro-badge ${config.className}`}>{config.label}</span>
  );
}
