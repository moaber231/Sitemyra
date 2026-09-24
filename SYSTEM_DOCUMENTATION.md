# Sitemyra — System Documentation

**Purpose.** A single, accurate reference for how Sitemyra is built, how it runs, and what is (and is not) implemented.

**Audience.** Technical maintainers, the operations/deployment agent, and due-diligence reviewers.

**Scope.** The full repository: Next.js frontend, Django/DRF backend, Celery workers, Docker Compose (dev + prod), PostgreSQL/Redis/MinIO, and on-disk artifacts.

### Verification status (this revision)

| Check | Result |
|-------|--------|
| Backend test suite | **220 tests, all passing** (~63 s) — run via `docker compose run --rm celery-browser-worker python manage.py test accounts monitors notifications billing common` (the browser image contains pixelmatch, which some monitor tests import; the API image intentionally does not) |
| Frontend type check / build | `npx tsc --noEmit` clean; `npm run build` exit 0 (19 routes) |
| API image isolation | `import config.wsgi` OK with Playwright blocked by a `sys.meta_path` blocker; `import playwright`/`pixelmatch` → `ModuleNotFoundError` in the API image |
| Version control | Git repository, branch `main`, remote `github.com/moaber231/Sitemyra` |
| Integration claims | Every "implemented" claim below was verified against source in this revision |

> **Companion documents.** `docs/OPTIMIZATION-PLAN.md` (the executed
> optimization mission), `docs/BROWSER-WORKER.md` (Chromium worker
> internals, SSRF residuals, driver-thread design), `docs/RESOURCE-BUDGET.md`
> (measured resource numbers and method), `docs/FREE-TIER-DEPLOYMENT.md`
> (why no free-tier claim is made yet).

> **Naming note.** Earlier briefs used shorthand names. The mapping to actual code identifiers is: `CheckResult` → `MonitorCheck`, `DiffLog` → `ChangeDiff`, `NotificationChannel` → `AlertChannel`, `PriceHistoryChart` → `PriceIntelligenceCard`.

---

## 1. System Overview

### 1.1 Executive summary

**Sitemyra** is a multi-tenant website change-detection and uptime-monitoring SaaS. Users register watch targets (URLs); the platform polls them on a schedule, detects content, visual, and price changes as well as outages, and alerts by email, Slack/Discord webhook, or generic webhook.

The product is built around one monitor object that can be evaluated by four engines — cheap HTTP hashing, rendered DOM comparison, pixel screenshots, and price extraction — plus team workspaces with role-based access control, Stripe-metered plans, and one-click compliance exports.

**Primary user workflows:**

| # | Workflow | Path |
|---|----------|------|
| 1 | Sign up → 3-step onboarding (add URL → pick engine → set webhook) | `/register` → `/dashboard/onboarding` |
| 2 | Create monitor; first check is dispatched immediately | `/dashboard/monitors/new` |
| 3 | Configure engine (HTTP/DOM/Screenshot/Price) and thresholds | `/dashboard/monitors/[id]` (`AdvancedConfigPanel`) |
| 4 | Triage changes and failures; inspect diffs and price history | `/dashboard`, `/dashboard/monitors/[id]/diffs/[diffId]` |
| 5 | Invite team (Owner/Admin/Viewer); manage webhooks and API keys | `/dashboard/workspaces`, `/dashboard/channels`, `/dashboard/api-keys` |
| 6 | Upgrade plan through Stripe Checkout; manage subscription via Portal | `/dashboard/billing` |
| 7 | Download auditor-ready uptime/SLA report (CSV/PDF) | `/dashboard/compliance` |
| 8 | Download stored diff artifacts (screenshot / visual diff) | `/dashboard/monitors/[id]/diffs/[diffId]` |
| 9 | (Super-admin) SaaS telemetry and worker diagnostics | `/admin/metrics` |

### 1.2 Monitoring engines

**HTTP ping / content hashing (default, cheapest).**
`Monitor` (`monitors/models.py`) offers `check_interval` ∈ {30 s, 1 m, 5 m, 15 m, 30 m, 60 m} and `timeout` 1–120 s (DB check constraint `monitor_timeout_range`). `check_monitor` (`monitors/tasks.py`) fetches with `httpx` (`services/fetcher.py`), normalizes the content — strips `script/style/noscript/template`, collapses whitespace (`services/normalizer.py`) — computes a SHA-256 hash, and compares it with `last_content_hash` (`services/change_detector.py`). The first successful check establishes the baseline and is never reported as a change. The `Monitor.status` property derives `healthy / changed / failing / paused / never_checked` from the latest `MonitorCheck`.

**DOM diffing (BeautifulSoup).**
`AdvancedMonitorConfig.mode = "dom"` with an optional CSS `selector`. Rendered HTML is normalized to text (`services/dom_diff.py`, ignoring `script/style/noscript/svg`, optionally scoped to the selector) and a `ChangeDiff(diff_type="dom")` row records that normalized page content changed. The UI renders it as an LCS line diff (`components/observability/diff-viewer.tsx`).

**Playwright visual screenshots.**
`mode = "screenshot"`: `fetch_with_browser` (`services/browser_fetcher.py`) renders the page headless (1440×900, full-page PNG) in the dedicated browser worker. A **persistent browser pool** (`services/browser_pool.py`) keeps one Chromium per prefork child alive across checks (lazy start, fresh incognito context per check, recycle by job count/RSS, crash auto-restart) — checks do *not* pay full launch cost after warm-up. Navigation waits `load` plus a bounded network-idle settle (`BROWSER_IDLE_SETTLE_MS`, default 3 s) — never an unbounded blind `networkidle`. `compare_screenshots` (`services/screenshot_diff.py`, Pillow + `pixelmatch`, per-pixel threshold 0.1) produces a percentage-changed value; a `ChangeDiff(diff_type="screenshot")` is stored only when it meets the user-configurable `screenshot_threshold`. Screenshot mode **never** applies resource blocking. See `docs/BROWSER-WORKER.md`.

**Price tracking.**
`mode = "price"` with `price_selector` (and optional `price_currency`): `extract_price` (`services/price_extractor.py`, regex for `$ € £` amounts, `Decimal` storage) writes one `PricePoint` per check, and a `ChangeDiff(diff_type="price")` records the transition. The weekly digest reports price drift; `PriceIntelligenceCard` charts baseline versus current with trend bars.

**Supporting capabilities.** Pause/resume/test actions, per-user and per-workspace monitors, plan-gated intervals and limits, Fernet-encrypted webhook secrets, `apeiro_…` Bearer API tokens, and a weekly digest email.

### 1.3 External integrations — verified status

| Integration | Status | Evidence |
|-------------|--------|----------|
| **Stripe** (Checkout, Customer Portal, webhooks) | ✅ Implemented; stub mode when keys are absent | `billing/views.py`, `billing/stripe_utils.py`, `STRIPE_*` env vars |
| **Slack / Discord / generic webhooks** | ✅ Implemented; outbound POST, secrets Fernet-encrypted | `notifications/services.py` (`deliver_to_channel`, `dispatch_webhooks`), `AlertChannel`, `/dashboard/channels` |
| **Email (SMTP)** | ✅ Implemented via Django `send_mail` — console backend in dev, Hostinger SMTP in prod. `django-anymail` is installed but **not wired to any provider** | `config/settings/development.py`, `config/settings/production.py` |
| **Google / GitHub OAuth (SSO)** | ✅ Implemented as a full authorization-code flow: `GET /api/auth/oauth/<provider>/start/` → provider → frontend `/auth/callback` → `GET …/callback/` with signed state, server-side code exchange, and `email_verified` required | `accounts/oauth.py`, `accounts/views.py`, `frontend/app/auth/callback/page.tsx` |
| **S3 / MinIO artifact storage** | ✅ Implemented (`boto3`); local disk by default, `ARTIFACT_STORAGE=s3` switches to S3-compatible storage with presigned download URLs; a MinIO service ships in the dev compose file | `common/artifact_storage.py`, `docker-compose.yml` |
| **SendGrid** | ❌ Not integrated — no SDK calls, no backend configuration | — |
| **Twilio (SMS)** | ❌ Not integrated — `sms` is only an `AlertChannel` type label; dispatch POSTs JSON to the stored URL like a generic webhook | `notifications/models.py`, `services.py` |
| **Telegram** | ❌ Not integrated — shown in the UI as "next on the roadmap" with no backend delivery | `components/observability/alert-channels.tsx` |

> **Due-diligence flag.** Marketing or buyer material should not claim SendGrid, Twilio, or Telegram integrations. Each is a small, isolated build-out (extension points in §5.6).

---

## 2. Frontend (Next.js)

**Stack.** Next.js 15 (App Router, `output: "standalone"`), React 19, TypeScript, Tailwind CSS v4, TanStack React Query 5, react-hook-form + zod, lucide-react icons, sonner toasts. No Axios, no SWR, no global state store.

### 2.1 Routes

All routes are client-rendered.

| Route | File | Purpose |
|-------|------|---------|
| `/` | `app/page.tsx` | Marketing landing |
| `/login`, `/register` | `app/login/page.tsx`, `app/register/page.tsx` | Email/password plus Google/GitHub SSO buttons |
| `/auth/callback` | `app/auth/callback/page.tsx` | OAuth redirect target; exchanges `code`/`state` for a JWT |
| `/dashboard` | `app/dashboard/page.tsx` | Overview: stat cards, live monitor list (30 s refetch) |
| `/dashboard/monitors` | `app/dashboard/monitors/page.tsx` | Monitor list |
| `/dashboard/monitors/new` | `app/dashboard/monitors/new/page.tsx` | Create form (name/URL/interval/timeout) |
| `/dashboard/monitors/[id]` | `app/dashboard/monitors/[id]/page.tsx` | Detail page with `AdvancedMonitoringSection` |
| `/dashboard/monitors/[id]/diffs/[diffId]` | `…/diffs/[diffId]/page.tsx` | Single diff view and artifact download |
| `/dashboard/settings` | `app/dashboard/settings/page.tsx` | Email preferences and channel cards |
| `/dashboard/onboarding` | `app/dashboard/onboarding/page.tsx` | 3-step wizard |
| `/dashboard/workspaces` | `app/dashboard/workspaces/page.tsx` | Workspaces, members, invites |
| `/dashboard/billing` | `app/dashboard/billing/page.tsx` | Plans, checkout, portal |
| `/dashboard/channels` | `app/dashboard/channels/page.tsx` | Webhook CRUD (masked secrets) |
| `/dashboard/api-keys` | `app/dashboard/api-keys/page.tsx` | Token generation (shown once) and revocation |
| `/dashboard/compliance` | `app/dashboard/compliance/page.tsx` | Authenticated CSV/PDF download |
| `/admin/metrics` | `app/admin/metrics/page.tsx` | Super-admin SaaS telemetry and diagnostics |

Route-level UX: `loading.tsx` skeletons under `/dashboard`, plus `global-error.tsx` and `not-found.tsx`.

### 2.2 Components

| Component | File | Role |
|-----------|------|------|
| `AdvancedConfigPanel` | `monitors/advanced-config.tsx` | Mode picker (HTTP/DOM/Screenshot/Price), selector/currency/threshold inputs, save and test |
| `AdvancedMonitoringSection` | `monitors/advanced-monitoring-section.tsx` | Wires config, diffs, and prices on the detail page |
| `MonitorChannelManager` | `monitors/monitor-channels.tsx` | Per-monitor alert channel assignment |
| `DiffViewer` (plus LCS utils and `priceDiffFromSummary`) | `observability/diff-viewer.tsx` | GitHub-style add/remove diffs for dom/price/screenshot summaries |
| `PriceIntelligenceCard` | `observability/price-intelligence.tsx` | Baseline vs current, delta %, bar-chart trend |
| `AlertChannels` | `observability/alert-channels.tsx` | Channel status cards |
| `AppShell` / `Sidebar` / `Topbar` / `AccountMenu` | `layout/` | Navigation shell |
| `DashboardHeader` | `navigation/DashboardHeader.tsx` | Page header used across dashboard pages |
| `Modal`, `BackButton`, `Button` | `ui/` | Primitives |
| `QueryProvider` | `providers/query-provider.tsx` | Single `QueryClient` (`staleTime` 30 s, `retry: 1`) mounted in `app/layout.tsx` with the global `Toaster` |

### 2.3 State, API layer, and styling

- **Transport.** `lib/api/client.ts` exposes `apiFetch`, a thin `fetch` wrapper. Domain modules: `auth.ts`, `monitors.ts`, `advanced.ts` (config, diffs, prices, artifact download), `notifications.ts`, `workspaces.ts`, `billing.ts`, `developer.ts` (API keys/OAuth/onboarding), `ops.ts` (metrics/diagnostics/compliance).
- **Auth handling.** JWT access token in `sessionStorage` (`apeiro_access`), refresh token in `apeiro_refresh`. `apiFetch` attaches `Authorization: Bearer`, retries once after a silent refresh on 401, then clears the session and throws "session has expired". Tokens are never written to `localStorage`, and no Django secret exists in frontend environment variables (only `NEXT_PUBLIC_API_URL`).
- **Data fetching.** React Query (`useQuery` with 30 s polling on the dashboard, `useMutation` for saves) mixed with plain `useEffect` + `useState` on several CRUD pages — a known inconsistency (§5.5).
- **Styling.** Dark-only theme (`color-scheme: dark` in `app/globals.css`). Tailwind v4 `@theme inline` maps semantic tokens (`background`, `card`, `accent`, `success/warning/danger` plus muted variants) to CSS variables; components use the `apeiro-card`, `apeiro-btn`, `apeiro-input`, `apeiro-badge` utilities and `animate-apeiro-*` animations.

---

## 3. Backend and Worker Engine (Django and Celery)

**Stack.** Django 5.2, DRF 3.18, SimpleJWT 5.5, Celery 5.6 (Redis broker and result backend), PostgreSQL 16, `httpx`, `beautifulsoup4`, Pillow (also required by `reportlab`), `stripe`, `cryptography` (Fernet), `redis`, `reportlab`, `boto3`. **Playwright + Chromium + pixelmatch exist only in the browser-worker image**; the API/HTTP-worker/beat image (`Dockerfile` target `api`) contains none of them. Celery runs as three queues — `celery_http`, `celery_browser`, `celery_notifications` — consumed by dedicated services (§4.1).

### 3.1 Applications and authentication

**Django apps** (registered in `config/settings/base.py`): `accounts` (auth, OAuth, API keys), `monitors`, `notifications`, `workspaces`, `billing`, `ops` (super-admin telemetry), `common` (crypto helpers, artifact storage, integration status).

**Authentication classes** (`REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES`, order matters):

1. `accounts.api_key_auth.ApiKeyAuthentication` — `Bearer apeiro_…` developer tokens. SHA-256 hash lookup, `last_used_at` touch, attaches `request.api_key`. Returns `None` for non-`apeiro_` tokens so JWT still applies, and exposes `authenticate_header` so missing credentials yield **401**, not 403.
2. `rest_framework_simplejwt.authentication.JWTAuthentication` — 15-minute access / 7-day refresh. **Refresh tokens are not rotated** and no blacklist app is installed.

### 3.2 REST endpoint inventory

| Prefix | Endpoints | Notes |
|--------|-----------|-------|
| `/api/health/` | `GET` | Unauthenticated liveness; per-dependency `postgres`/`redis`/`celery` status (200 all healthy, otherwise 503). The celery check reads a Redis worker-heartbeat registry (`config/worker_heartbeat.py`) — ~20 ms and concurrency-safe (§5.4; former broadcast defect fixed, see `docs/RESOURCE-BUDGET.md` §6) |
| `/api/auth/` | `register/`, `login/`, `refresh/`, `me/`, `onboarding/` (GET/PATCH), `api-keys/` (list/create, key shown once), `api-keys/<uuid>/` (soft revoke) | Signup auto-creates a Free `Subscription` and `OnboardingProgress` |
| `/api/auth/oauth/` | `status/` (GET), `<provider>/start/` (GET), `<provider>/callback/` (GET), legacy `POST /` | The legacy POST requires a provider `code` — raw email identities are never accepted |
| `/api/monitors/` | ViewSet CRUD + `pause/`, `resume/`, `test/`, `checks/`, `changes/`, `channels/` (GET/POST, `channels/<id>/` DELETE); `<uuid>/advanced/` (GET/PATCH), `advanced/test/`, `diffs/`, `prices/`; `export/compliance/?type=csv\|pdf`; `artifacts/<diff_id>/download/` | Plan limits and workspace RBAC enforced |
| `/api/notifications/` | `preferences/` (GET/PATCH), `channels/` (GET/POST), `channels/<uuid>/` (GET/PUT/DELETE), `channels/<uuid>/test/` (POST) | Plan channel caps; workspace webhooks are Owner/Admin-only |
| `/api/workspaces/` | CRUD, `members/` (GET/POST role change), `members/<id>` (DELETE), `invites/` (GET/POST), `invites/<token>/accept/` | Owner auto-membership; the Owner role is not grantable by invite |
| `/api/billing/` | `plans/`, `subscription/`, `checkout/`, `portal/`, `webhook/` (CSRF-exempt) | Stub responses without keys; signature-verified when `STRIPE_WEBHOOK_SECRET` is set |
| `/api/admin/` | `metrics/` (GET), `diagnostics/` (GET, POST to run a live dispatch test) | `IsAdminUser` (staff/superuser) only |

### 3.3 Data models (UUID primary keys throughout)

| Model | File | Key fields |
|-------|------|------------|
| `User` (custom, email login) | `accounts/models.py` | Unique lowercased `email`, `is_staff`; related `OAuthAccount`, `OnboardingProgress`, `ApiKey` (prefix, `key_hash`, scopes, workspace, revoked) |
| `Workspace`, `WorkspaceMembership` (owner/admin/viewer with rank map), `WorkspaceInvite` | `workspaces/models.py` | Automatic slug derivation; `unique_workspace_member` constraint |
| `Monitor` | `monitors/models.py` | `user`, optional `workspace`, intervals 30 s–60 m, `next_check_at`, denormalized `last_*` fields, timeout constraint |
| `MonitorCheck` | `monitors/models.py` | `checked_at`, `status_code`, `response_time_ms`, `content_hash`, `changed`, `error` |
| `AdvancedMonitorConfig` (http/dom/screenshot/price) | `monitors/models.py` | `selector`, `price_selector`, `price_currency`, `screenshot_threshold` |
| `ChangeDiff` (dom/screenshot/price) | `monitors/models.py` | Previous/current check FKs, summary, `diff_percentage`, `artifact_path` (storage **key**, not a filesystem path) |
| `PricePoint` | `monitors/models.py` | `price` (`Decimal`), `currency`, `raw_value`, 1:1 check link |
| `NotificationPreference`, `NotificationEvent` (change/failure/recovery, unique per check), `AlertChannel` (slack/discord/email/webhook/sms, `config_encrypted`), `MonitorAlertChannel` (assignment), `NotificationDelivery` (per-attempt log) | `notifications/models.py` | Secrets encrypted through `common.crypto.EncryptedTextField` (Fernet key derived from `DJANGO_SECRET_KEY`) |
| `Subscription` (free/pro/business; active/trialing/past_due/canceled/incomplete; `mrr_cents`, Stripe IDs), `StripeWebhookEvent` | `billing/models.py` | `PLAN_LIMITS`, `PLAN_MRR_CENTS` (Pro $19, Business $49) |

### 3.4 Plan limits and enforcement

| Plan | Monitors | Min interval | Alert channels | History retention |
|------|----------|--------------|----------------|-------------------|
| Free | 3 | 15 min | 1 | 7 days |
| Pro ($19) | 25 | 5 min | 5 | 30 days |
| Business ($49) | 100 | 1 min | 50 | 90 days |

Enforcement points: monitor creation checks `max_monitors` (HTTP 402 with an upgrade hint) and `min_interval_seconds` (serializer validation); channel creation checks `max_alert_channels`; workspace writes require Admin+ (`workspaces/permissions.py`); `MonitorViewSet` querysets union owned and workspace-member monitors (API-key requests are scoped to the key's workspace and require `monitors:write` for writes); `history_days` drives the daily retention task (§4.3).

### 3.5 Worker pipeline and scheduled tasks

```
Celery beat (settings/base.py CELERY_BEAT_SCHEDULE)
  ├─ every 60 s   → monitors.tasks.schedule_due_monitors (batched, SCHEDULER_BATCH_SIZE=500)
  ├─ Mon 09:00 UTC → notifications.tasks.send_weekly_digests (crontab, not a float interval)
  └─ daily 00:00  → monitors.tasks.cleanup_expired_artifacts
        ↓ (single-hop: the scheduler locks/advances each row, then enqueues directly)
Redis broker — three queues:
  celery_http          → celery-http-worker  (no Chromium): monitors.tasks.check_monitor
  celery_browser       → celery-browser-worker (concurrency 1, prefetch 1):
                          monitors.advanced_tasks.run_advanced_monitor
  celery_notifications → celery-http-worker: notifications.tasks.*
        ↓ (per task)
  http mode     → check_monitor         (httpx engine)
  browser mode  → run_advanced_monitor  (Playwright engine, driver-thread model)
        ↓ (off the critical path)
notifications.services.deliver_monitor_event.delay(...)  →  celery_notifications
  ├─ records NotificationEvent (unique per check → dedupe)
  ├─ owner email               (SMTP, preference-gated)
  └─ deliver_to_channel × N    (per-channel failure isolation)
        → NotificationDelivery log row per attempt
```

- **Single-hop scheduling.** The scheduler selects due monitors (batched at `SCHEDULER_BATCH_SIZE=500`, `select_related("advanced_config")`), re-locks each row with `select_for_update(of=("self",))` inside a transaction, advances `next_check_at` *before* dispatch, and enqueues the right queue directly — no intermediate hop. `dispatch_monitor_check` remains for compatibility. Safe against duplicate execution across workers.
- **Notifications are off the critical path.** Tasks hand events to `deliver_monitor_event.delay()` inside `try/except` isolation; eager mode (`CELERY_TASK_ALWAYS_EAGER=True`) is set in development settings **only**, so tests/local runs behave synchronously while production drains `celery_notifications` on the HTTP worker.
- **Failure semantics.** First failure records a `FAILURE` event, recovery a `RECOVERY` event, change a `CHANGE` event — each gated by `NotificationPreference` flags and a unique-per-check constraint. Notification dispatch never raises into the monitor task.
- **Retries.** `run_advanced_monitor` (`max_retries=5`) retries only `retryable` browser errors (timeouts, 429, 5xx) with capped exponential backoff (60·2ⁿ, max 900 s); 401/403/404 fail fast. `send_owner_email` applies its own bounded attempts inline, and the queued `send_notification_email` task auto-retries transient provider failures 3× with backoff.
- **Digest.** `send_weekly_digests` aggregates per-user uptime %, average latency, and price drift over the trailing 7 days.
- **Legacy path.** `queue_notification`, `send_notification_email`, and `dispatch_webhooks` remain as a secondary/queued path (covered by tests); new code should call `dispatch_monitor_event`.

### 3.6 Engine comparison

| | HTTP engine (`fetcher.py` + `normalizer.py`) | Browser engine (`browser_fetcher.py` + `dom_diff.py` / `screenshot_diff.py` / `price_extractor.py`) |
|---|---|---|
| Transport | `httpx` streaming client, manual redirect loop (max 5, every hop re-validated) | Playwright Chromium in the dedicated browser worker; `wait_until="load"` + bounded idle settle (never blind `networkidle`); full-page PNG plus `page.content()` |
| Parsing | Raw bytes → charset-aware text normalization → SHA-256 | Rendered HTML → selector-scoped text → SHA-256 (DOM); pixel diff (screenshot); selector-scoped price regex (price) |
| Cost (measured) | milliseconds; 40-check batch peaked 30.5 % CPU / 306 MiB on the HTTP worker | seconds; warm checks 1.7–2.8 s, chatty screenshot 6.5 s; browser-worker RSS peak 418 MiB (Chromium stays ~328 MiB flat across checks — see `docs/RESOURCE-BUDGET.md`) |
| SSRF posture | Aggressive guard: blocks loopback/private/link-local/multicast/reserved IPs, `localhost`, cloud metadata hosts, credentialed URLs, non-80/443 ports (incl. out-of-range `:99999`), 10 MB cap; re-validated on every redirect | Same `validate_url()` guard runs **before** any browser starts, and **every request the page makes** — subresources and each HTTP-3xx redirect hop — is re-validated via CDP `Fetch` interception (`context.route` misses hop targets: microsoft/playwright#34994). Final URL re-validated after redirects. **Residuals (open):** WebSocket handshakes bypass Fetch interception; DNS-rebinding TOCTOU (validate-then-connect without a pinning proxy). Fail-closed on DNS errors/exhausted lookup budget. See `docs/BROWSER-WORKER.md` §5 |
| Retry | None (failure recorded immediately) | Retryable (timeout/429/5xx, 5 tries, backoff); non-retryable (401/403/404) |
| Routing | Scheduler (or `dispatch_monitor_check`, kept for compat) routes by `advanced_config.mode`: `http` → `celery_http`, `dom`/`screenshot`/`price` → `celery_browser`. No automatic HTTP→browser upgrade on parse failure | — |
| Resource blocking | n/a | `dom`/`price` block images/media/fonts only (`BROWSER_BLOCK_RESOURCES`, `none` disables); **screenshot never blocks** (hard requirement, test-covered) |

---

## 4. Infrastructure, Docker, and Artifact Storage

### 4.1 Development stack (`docker-compose.yml`)

| Service | Image / build | Command | Ports (host:container) | Depends on |
|---------|---------------|---------|------------------------|------------|
| `frontend` | `frontend/Dockerfile`, target `development`, source bind-mount + `WATCHPACK_POLLING` | `npm run dev` | `3000:3000` | backend (started) |
| `backend` | `backend/Dockerfile` **target `api`** (python:3.12-slim, **no Chromium/Playwright/pixelmatch** — 289 MB) | `manage.py runserver 0.0.0.0:8000` (or `$PORT` via entrypoint) | `8000:8000` | postgres, redis (healthy) |
| `celery-http-worker` | target `api` (same 289 MB image as backend) | `celery -A config worker -Q celery_http,celery_notifications` (`HTTP_WORKER_CONCURRENCY`, default 4) | — | postgres, redis |
| `celery-browser-worker` | **target `browser`** (1.47 GB: + Playwright/Chromium at `/ms-playwright`, uid 10001) | `celery -A config worker -Q celery_browser --concurrency=1 --prefetch-multiplier=1 --max-tasks-per-child=50` | — | postgres, redis; `CELERY_IMPORTS=monitors.advanced_tasks` set on this service only |
| `celery-beat` | target `api` | `celery -A config beat` | — | postgres, redis |
| `postgres` | `postgres:16-alpine`, volume `postgres_data` | — | `5434:5432` | healthcheck `pg_isready` |
| `redis` | `redis:7-alpine`, volume `redis_data` | — | `6380:6379` | healthcheck `ping` |
| `minio` | `pgsty/minio`, volumes `minio_data` | `server /data --console-address ":9001"` | `9000:9000`, `9001:9001` | — (opt-in: set `ARTIFACT_STORAGE=s3` + `AWS_*`) |

All services run with `init: true`; the browser worker has a
`stop_grace_period` for graceful browser teardown. Queue routing is
defined in `monitors/routing.py` (explicit per-queue `Exchange` +
`routing_key`); the API/beat enqueue by task **name** via
`app.send_task`, so they never import Playwright-dependent modules.
Local artifact root is overridable via `ARTIFACT_LOCAL_ROOT`.

### 4.2 Production stack (`docker-compose.prod.yml`)

| Difference | Detail |
|------------|--------|
| Services | `frontend`, `backend`, `celery-http-worker`, `celery-browser-worker`, `celery-beat`, `postgres`, `redis` (the browser worker uses the **browser** image; everything else the **api** image) |
| API server | Gunicorn (`config.wsgi:application`, 3 workers, 120 s timeout) instead of `runserver`; `PORT` env selects the listen port |
| Frontend | Next.js `production` build; `NEXT_PUBLIC_API_URL` baked in from `BACKEND_PUBLIC_URL` at build time; `GET /health` liveness route |
| Settings | `DJANGO_SETTINGS_MODULE=config.settings.production`, `DJANGO_DEBUG=0`, everything else from `.env`; `CONN_MAX_AGE=60`, `CONN_HEALTH_CHECKS` available |
| Isolation | No source bind-mounts, no published database ports (`expose` only), no default database/Redis secrets (`:?` required) |
| Resilience | `restart: unless-stopped` and capped JSON logs (`10m` × 3) on every service; healthchecks on frontend, backend, workers, postgres, redis; `init: true` everywhere; browser worker `stop_grace_period`; resource-limit examples included as **comments only** |
| Artifacts | Named volume `artifact_data` mounted at `/app/storage` on backend, HTTP worker, and browser worker — local artifacts survive rebuilds |
| Not included | No Nginx/Caddy/Traefik (terminate TLS at the edge), no MinIO/S3 service (add `ARTIFACT_STORAGE=s3` + `AWS_*` if preferred) |

`/api/health/` reports per-dependency status for load-balancer and compose healthchecks (200 when healthy, 503 otherwise).

### 4.3 Artifacts: storage, retention, and download

- **Storage backends.** `common/artifact_storage.py` selects the backend from `ARTIFACT_STORAGE` (`local` default, `s3` for any S3-compatible endpoint including MinIO). Writes go to `<monitor_id>/<check_id>/<uuid>.<ext>` — `.html` normalized snapshots, `.png` screenshots, `-diff.png` visual diffs. Keys, never filesystem paths, are stored on `ChangeDiff.artifact_path`; legacy absolute paths remain readable. Credentials stay server-side.
- **Persistence.** Development bind-mounts `./backend:/app`, so local artifacts land in `backend/storage/`. Production mounts the named volume `artifact_data` at `/app/storage` on backend, HTTP worker, and browser worker; `ARTIFACT_STORAGE=s3` with `AWS_*` switches to S3-compatible storage instead.
- **Retention and hygiene.** `ARTIFACT_RETENTION_DAYS` (optional env) caps retention at `min(plan history_days, cap)` — it can only shorten, never extend, plan retention. The daily cleanup task also runs an **orphan sweep** (storage objects with no live monitor/check, skipping files younger than a 10-minute grace window), deletes a monitor's whole artifact prefix when a monitor is deleted (signal), prunes empty directories, and logs bytes/count reclaimed. The sweep is idempotent and safe to re-run.
- **Retention.** `monitors.tasks.cleanup_expired_artifacts` runs daily at 00:00 via Celery beat. For each monitor it applies the owner's plan `history_days`, deletes stale diffs and their storage objects first (so no dangling rows), then cascades the `MonitorCheck` rows (which removes `PricePoint` and `NotificationEvent` children).
- **Download.** `GET /api/monitors/artifacts/<diff_id>/download/` enforces ownership, then returns 302 to a presigned URL (S3) or streams the file with `X-Content-Type-Options: nosniff` (local). Misses return a uniform 404. The API only exposes `artifact_available`, `artifact_type`, and `artifact_download_url` — never raw paths.

### 4.4 Environment variables

Full annotated template: `.env.example`. `.env` is git-ignored and must never be committed.

| Variable | Required | Used by | Notes |
|----------|----------|---------|-------|
| `DATABASE_URL` | Yes | backend, worker, beat | `postgres://apeiro:apeiro@postgres:5432/apeiro` in dev |
| `POSTGRES_DB/USER/PASSWORD` | Yes (prod: mandatory) | postgres container | Defaults `apeiro` in dev; `:?`-required in prod |
| `REDIS_URL`, `REDIS_PASSWORD` | Yes | backend, worker, beat, ops diagnostics | Prod Redis runs `--requirepass` |
| `DJANGO_SECRET_KEY` | **Yes — rotate for prod** | Django, JWT signing, Fernet key derivation | Dev placeholder is detected and logged at startup |
| `DJANGO_DEBUG` | Yes | settings switch | `1` dev / `0` prod image |
| `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` | Prod | `production.py` hardening | CSV lists |
| `FRONTEND_URL`, `BACKEND_URL`, `NEXT_PUBLIC_API_URL`, `BACKEND_PUBLIC_URL` | Yes | CORS, OAuth/email links, Stripe return URLs, browser bundle | `NEXT_PUBLIC_*` is baked at **build** time |
| `FRONTEND_PORT`, `BACKEND_PORT` | No | compose port mapping | Defaults 3000 / 8000 |
| `EMAIL_HOST/PORT/USER/PASSWORD` | Prod | Hostinger SMTP (`smtp.hostinger.com:465`) | Password lives only in `.env` / secret manager |
| `EMAIL_USE_SSL`, `EMAIL_USE_TLS` | Prod | Mutually exclusive | `SSL=1` for 465 (Hostinger), `TLS=1` for 587 |
| `EMAIL_FROM`, `EMAIL_FROM_NAME` | Optional | Sender mailbox and display name | Console backend in dev |
| `ARTIFACT_STORAGE`, `ARTIFACT_LOCAL_ROOT` | Optional | Artifact backend switch / local root | `local` (default) or `s3`; local root default `/app/storage/monitor-artifacts` |
| `AWS_STORAGE_BUCKET_NAME/REGION`, `AWS_S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_PREFIX` | If `ARTIFACT_STORAGE=s3` | `common/artifact_storage.py` | Bucket is auto-created when possible |
| `ARTIFACT_RETENTION_DAYS` | Optional | Retention **cap** for artifacts/checks | `min(plan history_days, cap)`; unset/0/invalid = no cap |
| `ARTIFACT_URL_EXPIRES_SECONDS` | No | Presigned URL lifetime | 60–86400, default 900 |
| `PORT` | No | Backend listen port | Default 8000 (entrypoint passes it to gunicorn/runserver) |
| `HTTP_WORKER_CONCURRENCY` | No | `celery-http-worker` children | Default 4 |
| `BROWSER_WORKER_CONCURRENCY`, `BROWSER_MAX_TASKS_PER_CHILD` | No | Browser worker children / child recycle | Keep concurrency at 1; default max-tasks 50 |
| `BROWSER_MAX_TASKS`, `BROWSER_MAX_RSS_MB`, `BROWSER_LAUNCH_TIMEOUT_MS`, `BROWSER_PAGE_OP_TIMEOUT_MS`, `BROWSER_IDLE_SETTLE_MS`, `BROWSER_BLOCK_RESOURCES`, `BROWSER_MAX_DNS_LOOKUPS`, `BROWSER_DNS_CACHE_TTL_S`, `SCREENSHOT_MAX_HEIGHT_PX` | No | Browser lifecycle/timeouts/blocking | Defaults and semantics: `docs/BROWSER-WORKER.md` §10 |
| `CELERY_HTTP_TASK_SOFT_TIME_LIMIT`/`_TIME_LIMIT`, `CELERY_NOTIFICATION_TASK_*`, `CELERY_SCHEDULER_TASK_*`, `CELERY_BROWSER_TASK_*`, `CELERY_DIGEST_TASK_*` | No | Celery time limits (env-driven) | Defaults 150/180 (http), 90/120 (notifications), 50/60 (scheduler), 180/240 (browser), 600/900 (digest); soft is clamped to hard |
| `CELERY_TASK_IGNORE_RESULT` | No | Result-backend behavior | Default `true` — no result traffic in Redis |
| `SCHEDULER_BATCH_SIZE` | No | Scheduler enqueue cap per 60 s tick | Default 500 |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_PRO/BUSINESS` | For live billing | `billing/` | Empty = billing endpoints respond in stub/503 mode |
| `STRIPE_DEV_STUB`, `STRIPE_DEV_SKIP_WEBHOOK_VERIFY` | Dev only | Billing test convenience | Honoured only when `DEBUG=True` |
| `GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI`, `GITHUB_CLIENT_ID/SECRET/REDIRECT_URI` | For real SSO | `accounts/oauth.py` | Empty = provider reported unavailable (503 on start) |
| `OAUTH_STATE_TTL_SECONDS` | No | Signed state lifetime | Default 600 |
| `MINIO_ROOT_USER/PASSWORD` | If using dev MinIO | minio container | Dev only |

---

## 5. Operations Handbook

### 5.1 Local setup and tests

```sh
cp .env.example .env              # fill secrets; never commit .env
docker compose up --build         # first boot includes Chromium install (~5–10 min)
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser   # for /admin/metrics
# App:    http://localhost:3000
# Health: http://localhost:8000/api/health/
```

Test suite (verified in this revision — 220 tests, ~63 s):

```sh
docker compose up -d postgres redis
docker compose run --rm celery-browser-worker python manage.py test \
  accounts monitors notifications billing common
docker compose run --rm celery-browser-worker python manage.py \
  makemigrations --check --dry-run
```

> The suite runs on the **browser-worker service** because some monitor
> tests import `pixelmatch`, which exists only in the browser image — the
> API image deliberately excludes it. Migrations/config gates:
> `docker compose config -q` and
> `REDIS_PASSWORD=x docker compose -f docker-compose.prod.yml config -q`.

Frontend type check: `cd frontend && npx tsc --noEmit`; build: `npm run build`. No virtualenv is committed or required; everything runs through Docker. Post-optimization resource measurements: `docs/RESOURCE-BUDGET.md`.

### 5.2 Production deployment checklist

1. Set `DJANGO_DEBUG=0`, a strong `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, and `CORS_ALLOWED_ORIGINS`; use `config.settings.production` (selected automatically by `docker-compose.prod.yml`).
2. Start the hardened overlay: `docker compose -f docker-compose.prod.yml up --build -d`, then run `migrate` on each release.
3. Terminate TLS at the edge (Hostinger VPS proxy, Cloudflare, or CDN) in front of `FRONTEND_PORT`/`BACKEND_PORT`. Ensure the edge forwards `X-Forwarded-Proto`, because production enables `SECURE_SSL_REDIRECT`.
4. Use managed PostgreSQL 16 + Redis, or the same-VPS containers to start; point `DATABASE_URL` / `REDIS_URL` accordingly.
5. Configure Hostinger SMTP (`EMAIL_HOST=smtp.hostinger.com`, `EMAIL_PORT=465`, `EMAIL_USE_SSL=1`, plus `EMAIL_HOST_USER/PASSWORD`), the Stripe webhook endpoint `<API origin>/api/billing/webhook/`, and Google/GitHub OAuth redirect URIs (`<FRONTEND_URL>/auth/callback`).
6. Point artifacts at object storage: `ARTIFACT_STORAGE=s3` with `AWS_*` (or add a named volume for `/app/storage`); retention runs automatically via the daily beat task.
7. Scale by adding `celery-http-worker` replicas (`--concurrency N` on the `celery_http` queue); keep the browser worker at concurrency 1 per container and scale by adding browser-worker replicas instead — measured budget: one concurrent browser check ≈ 420 MiB peak RSS / up to ~2.2 cores on a chatty full-page screenshot (`docs/RESOURCE-BUDGET.md`).

### 5.3 Infrastructure cost estimates (2026)

| Topology | Components | Approx. cost/month | Practical limits |
|----------|-----------|--------------------|------------------|
| **Single VPS (start here)** | 1× 4 GB VPS (Hetzner CX32 ≈ $12 / DO Basic ≈ $24) running the full compose stack | **$12–$25** | ~500 monitors at 5 min HTTP; ~20 concurrent browser checks; disk = artifact growth |
| **Managed data** | + managed Postgres ($15) and managed Redis ($10–15) | **$40–$55** | Backups and failover offloaded |
| **Growth (+2 workers)** | + 2 worker VPSs sharing Redis/Postgres | **$70–$110** | ~5k monitors; browser checks sharded by queue |
| Serverless PaaS (Render/Railway) | Web + worker + beat + PG + Redis per service | **$35–$80** | Simplest operations; Playwright needs ≥ 2 GB instances |

Unit economics: a single Business customer ($49) covers the single-VPS fleet; HTTP checks cost fractions of a cent, so margin expands quickly with volume.

### 5.4 Scalability limits as built

- Browser checks run at **concurrency 1 per browser-worker container** (prefork, prefetch 1); RAM is the binding constraint (measured ~420 MiB peak for the worst chatty screenshot). Scale browser capacity by adding browser-worker replicas, not by raising concurrency inside one container. Chromium is pooled per prefork child (lazy start, recycle at 50 checks / 1 GiB RSS / Celery `--max-tasks-per-child`), so steady-state cost is well below per-check launch cost.
- `schedule_due_monitors` runs single-hop and **batched** (`SCHEDULER_BATCH_SIZE`, default 500 per 60 s tick → ≤500 checks/min enqueue rate per tick), with `select_related("advanced_config")` and per-row `select_for_update`. Raise the batch (or shard) past ~10k due monitors/minute.
- Artifact disk is bounded by plan `history_days` (7/30/90 d), the optional `ARTIFACT_RETENTION_DAYS` cap, the daily orphan sweep, and monitor-delete prefix purge; local storage persists on the `artifact_data` named volume (or S3).
- JWT refresh tokens do not rotate and there is no blacklist; API-key auth is a single global hash lookup with no per-key rate limit.
- **Health endpoint:** `/api/health/` celery check now reads a **Redis TTL-registry heartbeat** (`config/worker_heartbeat.py`: workers re-register every TTL/3 s, `WORKER_HEARTBEAT_TTL_S` default 15 s) instead of a live `inspect()` broadcast — ~20 ms per probe and safe under unlimited concurrency (20 concurrent probes measured < 1 s wall, `pg_stat_activity` flat; response shape unchanged). Root cause, before/after, and tests: `docs/RESOURCE-BUDGET.md` §6 and `backend/common/tests_health.py`. No sequencing constraint remains on probes.

### 5.5 Known gaps and technical debt

| # | Finding | Severity | Fix effort |
|---|---------|----------|------------|
| 1 | Refresh tokens never rotate; no blacklist app; no rate limiting on auth endpoints | Medium (security) | S–M — SimpleJWT rotation + denylist + throttling |
| 2 | Browser SSRF residuals: WebSocket handshakes bypass CDP `Fetch` interception; DNS-rebinding TOCTOU remains (validate-then-connect without a pinning proxy). Subresources and HTTP-3xx hops *are* now validated (microsoft/playwright#34994 fixed via CDP) | Medium (security, residual) | M — local DNS-pinning proxy; WS handshake validation in Chromium policy |
| 3 | Edge TLS: `SECURE_SSL_REDIRECT=True` but `SECURE_PROXY_SSL_HEADER` is unset — verify the edge sends `X-Forwarded-Proto` to avoid redirect loops | Medium (ops) | S |
| 4 | Frontend mixes React Query and ad-hoc `useEffect` fetching across pages | Low | M — standardize on Query hooks |
| 5 | `?format=` is unusable on the compliance export (DRF renderer 404); documented workaround is `?type=` | Low (docs) | XS |
| 6 | Two notification paths coexist (`deliver_monitor_event` → `celery_notifications` primary, `queue_notification`/`dispatch_webhooks` legacy) | Low | S — consolidate |
| 7 | Default `ALLOWED_HOSTS = ["*"]` in base settings; safe only because `production.py` overrides it from env | Low | XS |

Completed since earlier revisions (no longer open): repository under git; artifact retention job **plus** `ARTIFACT_RETENTION_DAYS` cap, orphan sweep, monitor-delete prefix purge, named `artifact_data` volume; S3/MinIO backend; artifact download endpoint; **per-hop + subresource SSRF validation for the browser (CDP Fetch)**; **persistent browser pool with driver-thread isolation**; **queue split (`celery_http`/`celery_browser`/`celery_notifications`) with API image free of Playwright**; **multi-stage Dockerfile (api/browser targets)**; **notifications off the critical path**; **scheduler batching + 3 new indexes (`MonitorCheck.checked_at`, `Subscription(status, updated_at)`/stripe IDs)**; **monitor-list N+1 fix**; **digest byte-identical N+1 rewrite + Monday 09:00 crontab**; real OAuth authorization-code flow (no identity-bridge fallback); **`/api/health/` celery check replaced with a concurrency-safe Redis worker heartbeat (former inspect() broadcast wedged under concurrency and pinned DB connections — former gap #3, fixed with 17 regression tests; see `docs/RESOURCE-BUDGET.md` §6)**.

### 5.6 Extension points

- **Proxy rotation and multi-region checks.** Add `proxy` + `region` fields to `Monitor`, thread them through `fetch_url()` (`httpx.Proxy`) and `browser.new_context(proxy=…)`, and route Celery tasks by region queue. All call sites are single functions.
- **SendGrid / Twilio / Telegram.** Implement one provider class behind the channel dispatcher; secrets already flow through the encrypted `AlertChannel` model, so no schema change is needed.
- **Status pages and SLA webhooks.** A read-only public view over `MonitorCheck` aggregates — the compliance export already computes them.
- **Metered overages.** Stripe usage-based line items on top of the `checks_24h` metrics already exposed by ops.
- **Enterprise SSO (SAML/OIDC).** Extend `OAuthAccount.provider` choices; JWT issuance is provider-agnostic.
- **Scheduler batching and a browser pool** — both implemented in the optimization mission (§5.4, `docs/OPTIMIZATION-PLAN.md`).

---

*Generated from a file-level audit of `backend/`, `frontend/`, `docker-compose*.yml`, and `.env(.example)`. Test and type-check results were executed in this revision. Integrations marked "not integrated" (SendGrid, Twilio, Telegram) reflect the code as written.*
