/* Sitemyra browser extension — service worker.
 *
 * SECURITY INVARIANTS (these are the whole point of this file):
 *
 * 1. The token is a short-lived, scoped, revocable BrowserSession token
 *    minted by the user in the Sitemyra app. It is stored ONLY in
 *    chrome.storage.local, never in a cookie, never in a URL, never in
 *    sync storage, and never in this file.
 *
 * 2. The scope is `monitors:read monitors:write` and nothing else. The
 *    server enforces this: any other endpoint refuses an extension token
 *    with 401. This extension therefore cannot reach billing, alert
 *    channels, exports, reports or agency membership — not because we
 *    promise not to call them, but because the API rejects them.
 *
 * 3. There is NO Stripe key, NO SMTP credential and NO Django secret
 *    anywhere in this package. The extension cannot leak what it does
 *    not have.
 *
 * 4. The only endpoint used is POST /api/intelligence/quick-monitor/,
 *    the same idempotent endpoint the dashboard uses. The extension adds
 *    a convenience, not a privileged code path.
 */

const STORAGE_TOKEN = "sitemyraExtensionToken";
const STORAGE_API = "sitemyraApiOrigin";

const DEFAULT_API = "https://app.sitemyra.com";

async function getSettings() {
  const stored = await chrome.storage.local.get([STORAGE_TOKEN, STORAGE_API]);
  return {
    token: stored[STORAGE_TOKEN] || null,
    apiOrigin: (stored[STORAGE_API] || DEFAULT_API).replace(/\/$/, ""),
  };
}

async function setToken(token) {
  await chrome.storage.local.set({ [STORAGE_TOKEN]: token });
}

async function clearToken() {
  await chrome.storage.local.remove([STORAGE_TOKEN]);
}

async function apiRequest(path, { method = "GET", body } = {}) {
  const { token, apiOrigin } = await getSettings();
  if (!token) {
    return { ok: false, status: 401, error: "Not connected to Sitemyra." };
  }
  const headers = { Authorization: `Bearer ${token}` };
  if (body) headers["Content-Type"] = "application/json";
  try {
    const response = await fetch(`${apiOrigin}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (response.status === 401) {
      // Expired or revoked: drop it so the popup asks the user to reconnect.
      await clearToken();
      return { ok: false, status: 401, error: "This extension session has expired." };
    }
    const text = await response.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch (_err) {
      data = { detail: text };
    }
    return { ok: response.ok, status: response.status, data };
  } catch (err) {
    return { ok: false, status: 0, error: "Could not reach Sitemyra." };
  }
}

const RECIPES = {
  page: null,
  product: "product",
  price: "pricing",
  content: "everything",
};

async function monitorCurrentPage(recipeKey) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.url) {
    return { ok: false, error: "No page to monitor." };
  }
  const url = tab.url;
  if (!/^https?:\/\//i.test(url)) {
    return { ok: false, error: "Sitemyra only monitors public http and https pages." };
  }
  if (/app\.(sitemyra|localhost)/i.test(url)) {
    return { ok: false, error: "That is the Sitemyra app itself." };
  }
  return apiRequest("/api/intelligence/quick-monitor/", {
    method: "POST",
    body: { url, recipe: RECIPES[recipeKey] ?? null },
  });
}

async function openInSitemyra(path) {
  const { apiOrigin } = await getSettings();
  await chrome.tabs.create({ url: `${apiOrigin}${path}` });
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  (async () => {
    switch (message?.type) {
      case "status": {
        const { token } = await getSettings();
        sendResponse({ connected: Boolean(token) });
        return;
      }
      case "connect":
        await setToken(String(message.token || "").trim());
        sendResponse({ connected: true });
        return;
      }
      case "disconnect":
        await clearToken();
        sendResponse({ connected: false });
        return;
      case "monitor":
        sendResponse(await monitorCurrentPage(message.recipe || "page"));
        return;
      case "open":
        await openInSitemyra(message.path || "/dashboard");
        sendResponse({ ok: true });
        return;
      default:
        sendResponse({ ok: false, error: "Unknown request." });
    }
  })();
  return true; // keep the message channel open for the async response
});
