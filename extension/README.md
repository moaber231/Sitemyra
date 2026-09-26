# Sitemyra browser extension (Phase 6)

A Manifest V3 Chromium extension that sends the page you are on to Sitemyra.

## Install (unpacked)

1. Open `chrome://extensions`, enable **Developer mode**.
2. Choose **Load unpacked** and select this `extension/` directory.
3. Open Sitemyra → **Extension**, create a session, and paste the token
   into the popup when prompted.

## What it does

| Action | Endpoint called |
|---|---|
| Monitor this page | `POST /api/intelligence/quick-monitor/` (no recipe) |
| Monitor this product | same, `recipe: "product"` |
| Track the price | same, `recipe: "pricing"` |
| Track content | same, `recipe: "everything"` |
| Open in Sitemyra | opens `/dashboard` in a tab |

Every action is idempotent: monitoring a page twice returns the existing
monitor instead of creating a duplicate.

## Security invariants

These are enforced by the **server**, not by this package, so a modified
copy of the extension gains nothing:

1. **Scoped, revocable, expiring token.** Stored as a SHA-256 hash
   server-side; the raw value is shown once. Max 90 days. Revoking takes
   effect on the next request.
2. **Hard scope ceiling: `monitors:read monitors:write`.**
   `intelligence/extension_auth.py` holds a deny-by-default allowlist
   keyed by URL name, so an extension token receives **401** from billing,
   alert channels, exports, reports, workspaces, organizations and admin
   endpoints. Anything not explicitly listed is refused.
3. **No privileged secrets in the browser.** No Stripe key, no SMTP
   credential, no `DJANGO_SECRET_KEY` — they are not in this package and
   are never sent to the frontend.
4. **No privileged code path.** The extension calls the same
   `quick-monitor` endpoint the dashboard uses, so it gets the same SSRF
   validation, plan limits and tenant rules.
5. **Storage is local only.** `chrome.storage.local`, never `sync`. The
   token never appears in a URL, a log line, or a report.
6. **Defensive UI.** The extension refuses `http(s)`-less pages and
   refuses to monitor the Sitemyra app itself.

## The zero-credential alternative

A user who does not want a token in their browser at all can use the
bookmarklet instead: `frontend/public/sitemyra-bookmarklet.js`. It
contains no token and calls no API — it only opens Sitemyra with the
current URL.
