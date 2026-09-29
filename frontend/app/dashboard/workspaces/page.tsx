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
      toast.success(
        "Invitation created. No email was sent; share its token with the invited address.",
      );
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not invite member.");
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
                      Invitations are not emailed. Copy the token below and
                      send it to the person at that address yourself.
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
                      <div className="mt-3 space-y-1 text-xs text-muted-foreground">
                        {invites.map((i) => (
                          <div
                            key={i.id}
                            className="flex flex-wrap items-center gap-2 rounded-lg border border-border p-2"
                          >
                            <span className="min-w-0 flex-1 break-all">
                              {i.email} ({i.role})
                            </span>
                            <code className="max-w-full break-all rounded bg-muted px-2 py-1 font-mono">
                              {i.token}
                            </code>
                            <button
                              type="button"
                              onClick={async () => {
                                try {
                                  await navigator.clipboard.writeText(i.token);
                                  setCopiedInviteId(i.id);
                                  window.setTimeout(() => setCopiedInviteId(null), 2000);
                                } catch {
                                  toast.error("Copy failed. Select the token and copy it manually.");
                                }
                              }}
                              className="apeiro-btn apeiro-btn-outline !min-h-0 !py-1.5 text-xs"
                              aria-label={`Copy invitation token for ${i.email}`}
                            >
                              {copiedInviteId === i.id ? (
                                <Check size={13} />
                              ) : (
                                <Copy size={13} />
                              )}
                              {copiedInviteId === i.id ? "Copied" : "Copy token"}
                            </button>
                          </div>
                        ))}
                      </div>
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
