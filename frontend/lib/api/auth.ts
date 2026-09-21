import { apiFetch } from "./client";

export type User = {
  id: string;
  email: string;
  created_at: string;
};

export type AuthResponse = {
  user: User;
  access: string;
  refresh: string;
};

export function login(email: string, password: string) {
  return apiFetch<AuthResponse>("/api/auth/login/", {
    method: "POST",
    body: JSON.stringify({
      email,
      password,
    }),
  });
}

export function register(email: string, password: string) {
  return apiFetch<AuthResponse>("/api/auth/register/", {
    method: "POST",
    body: JSON.stringify({
      email,
      password,
    }),
  });
}

export function refreshAccessToken(refresh: string) {
  return apiFetch<{ access: string }>("/api/auth/refresh/", {
    method: "POST",
    body: JSON.stringify({
      refresh,
    }),
  });
}

export function getMe(accessToken: string) {
  return apiFetch<User>("/api/auth/me/", {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });
}