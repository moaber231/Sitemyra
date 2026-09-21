import { apiFetch } from "./client";

export type ApiKey = {
  id: string;
  name: string;
  prefix: string;
  workspace: string | null;
  scopes: string;
  last_used_at: string | null;
  revoked: boolean;
  created_at: string;
  key?: string;
};

export function getApiKeys() {
  return apiFetch<ApiKey[]>("/api/auth/api-keys/");
}

export function createApiKey(
  name: string,
  workspace?: string | null,
  scopes?: string,
) {
  return apiFetch<ApiKey>("/api/auth/api-keys/", {
    method: "POST",
    body: JSON.stringify({ name, workspace: workspace ?? null, scopes }),
  });
}

export function revokeApiKey(id: string) {
  return apiFetch<void>(`/api/auth/api-keys/${id}/`, { method: "DELETE" });
}

export type OAuthProvider = "google" | "github";

export type OAuthStatus = {
  providers: Record<
    OAuthProvider,
    { enabled: boolean; redirect_uri: string | null }
  >;
};

export function oauthStatus() {
  return apiFetch<OAuthStatus>("/api/auth/oauth/status/");
}

export function oauthStart(provider: OAuthProvider) {
  return apiFetch<{ authorization_url: string; provider: string; state: string }>(
    `/api/auth/oauth/${provider}/start/`,
  );
}

export function oauthCallback(
  provider: OAuthProvider,
  params: { code: string; state: string },
) {
  const query = new URLSearchParams(params).toString();
  return apiFetch<{
    user: unknown;
    access: string;
    refresh: string;
    provider: string;
    created: boolean;
  }>(`/api/auth/oauth/${provider}/callback/?${query}`);
}

export function oauthLogin(
  provider: OAuthProvider,
  identity: { email?: string; provider_user_id?: string; code?: string },
) {
  return apiFetch<{ user: unknown; access: string; refresh: string }>(
    "/api/auth/oauth/",
    { method: "POST", body: JSON.stringify({ provider, ...identity }) },
  );
}

export type Onboarding = {
  step: number;
  completed: boolean;
  first_monitor_id: string | null;
  engine: string;
  webhook_configured: boolean;
  updated_at: string;
};

export function getOnboarding() {
  return apiFetch<Onboarding>("/api/auth/onboarding/");
}

export function updateOnboarding(data: Partial<Onboarding>) {
  return apiFetch<Onboarding>("/api/auth/onboarding/", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}
