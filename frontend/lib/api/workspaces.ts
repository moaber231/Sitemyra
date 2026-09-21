import { apiFetch } from "./client";

export type Workspace = {
  id: string;
  name: string;
  slug: string;
  role: "owner" | "admin" | "viewer" | null;
  member_count: number;
  created_at: string;
};

export type Member = {
  id: string;
  user: string;
  email: string;
  role: string;
  created_at: string;
};

export type Invite = {
  id: string;
  email: string;
  role: string;
  token: string;
  accepted: boolean;
  created_at: string;
};

export function getWorkspaces() {
  return apiFetch<Workspace[]>("/api/workspaces/");
}

export function createWorkspace(name: string) {
  return apiFetch<Workspace>("/api/workspaces/", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export function getMembers(workspaceId: string) {
  return apiFetch<Member[]>(`/api/workspaces/${workspaceId}/members/`);
}

export function updateMemberRole(
  workspaceId: string,
  memberId: string,
  role: string,
) {
  return apiFetch<Member>(`/api/workspaces/${workspaceId}/members/`, {
    method: "POST",
    body: JSON.stringify({ id: memberId, role }),
  });
}

export function getInvites(workspaceId: string) {
  return apiFetch<Invite[]>(`/api/workspaces/${workspaceId}/invites/`);
}

export function inviteMember(
  workspaceId: string,
  email: string,
  role: string,
) {
  return apiFetch<Invite>(`/api/workspaces/${workspaceId}/invites/`, {
    method: "POST",
    body: JSON.stringify({ email, role }),
  });
}

export function acceptInvite(token: string) {
  return apiFetch<{ detail: string; workspace_id: string; role: string }>(
    `/api/workspaces/invites/${token}/accept/`,
    { method: "POST" },
  );
}
