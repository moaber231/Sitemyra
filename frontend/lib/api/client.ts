const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const REFRESH_KEY = "apeiro_refresh";
const ACCESS_KEY = "apeiro_access";

function getSessionItem(key: string): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  return window.sessionStorage.getItem(key);
}

function setSessionItem(key: string, value: string) {
  if (typeof window === "undefined") {
    return;
  }

  window.sessionStorage.setItem(key, value);
}

export function clearSession() {
  if (typeof window === "undefined") {
    return;
  }

  window.sessionStorage.removeItem(ACCESS_KEY);
  window.sessionStorage.removeItem(REFRESH_KEY);
}

async function refreshAccessToken() {
  const refresh = getSessionItem(REFRESH_KEY);

  if (!refresh) {
    return null;
  }

  const response = await fetch(`${API_URL}/api/auth/refresh/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ refresh }),
  });

  if (!response.ok) {
    clearSession();
    return null;
  }

  const data = await response.json();

  if (typeof data.access !== "string") {
    clearSession();
    return null;
  }

  setSessionItem(ACCESS_KEY, data.access);

  return data.access as string;
}

function extractMessage(payload: unknown, fallback: string): string {
  if (typeof payload === "string" && payload.trim()) {
    return payload;
  }

  if (payload && typeof payload === "object") {
    const record = payload as Record<string, unknown>;

    if (typeof record.detail === "string") {
      return record.detail;
    }

    if (Array.isArray(record.detail)) {
      return record.detail
        .map((item) =>
          typeof item === "string" ? item : JSON.stringify(item),
        )
        .join(" ");
    }

    const messages: string[] = [];

    for (const value of Object.values(record)) {
      const items = Array.isArray(value) ? value : [value];

      for (const item of items) {
        if (typeof item === "string") {
          messages.push(item);
        }
      }
    }

    if (messages.length > 0) {
      return messages.join(" ");
    }
  }

  return fallback;
}

export async function apiFetchBlob(
  path: string,
  options: RequestInit = {},
): Promise<{ blob: Blob; filename: string | null }> {
  const accessToken = getSessionItem(ACCESS_KEY);

  const makeRequest = (token: string | null) =>
    fetch(`${API_URL}${path}`, {
      ...options,
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers as Record<string, string> | undefined),
      },
    });

  let response = await makeRequest(accessToken);

  if (response.status === 401 && accessToken) {
    const newAccessToken = await refreshAccessToken();

    if (newAccessToken) {
      response = await makeRequest(newAccessToken);
    }
  }

  if (!response.ok) {
    if (response.status === 401) {
      clearSession();
      throw new Error("Your session has expired. Please sign in again.");
    }

    throw new Error(`Download failed with status ${response.status}`);
  }

  const disposition = response.headers.get("content-disposition") ?? "";
  const match = /filename="?([^";]+)"?/.exec(disposition);
  return { blob: await response.blob(), filename: match?.[1] ?? null };
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const hasBody = typeof options.body === "string" && options.body.length > 0;
  const accessToken = getSessionItem(ACCESS_KEY);

  const makeRequest = (token: string | null) => {
    const headers: Record<string, string> = {
      ...(hasBody ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers as Record<string, string> | undefined),
    };

    return fetch(`${API_URL}${path}`, {
      ...options,
      headers,
    });
  };

  let response = await makeRequest(accessToken);

  if (response.status === 401 && accessToken) {
    const newAccessToken = await refreshAccessToken();

    if (newAccessToken) {
      response = await makeRequest(newAccessToken);
    }
  }

  if (response.status === 204) {
    return undefined as T;
  }

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));

    if (response.status === 401) {
      clearSession();
      throw new Error(
        "Your session has expired. Please sign in again.",
      );
    }

    throw new Error(
      extractMessage(
        payload,
        `Request failed with status ${response.status}`,
      ),
    );
  }

  return response.json();
}