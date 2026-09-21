# Sitemyra — System Architecture & Technical Operations Manual

> **Audience:** acquirer / buyer technical team, M&A due-diligence reviewers, and future maintainers.
> **Scope:** entire repository as audited — Next.js frontend, Django/DRF backend, Celery workers, Docker Compose, PostgreSQL/Redis, and on-disk artifacts.
> **Codebase status at time of writing:** 21 backend tests passing (`accounts` 2, `monitors` 15, `notifications` 4), `tsc --noEmit` clean, `next build` green. The repo is **not under git version control** (no `.git` directory) — see §5.4.
>
> **Naming note:** this document uses the *actual* model/file names found in code. Where the acquisition brief used shorthand names, the mapping is: `CheckResult` → `MonitorCheck`, `DiffLog` → `ChangeDiff`, `NotificationChannel` → `AlertChannel`, `PriceHistoryChart` → `PriceIntelligenceCard`.

---

## 1. Executive System Overview & Capabilities

### 1.1 Executive Summary

**Sitemyra** is a multi-tenant website change-detection and uptime-monitoring SaaS. Users register watch-targets (URLs); the platform polls them on a schedule, detects content / visual / price changes and outages, and alerts via email, Slack/Discord webhooks, or generic webhooks.

**Value proposition:** "Know when the web changes without constantly checking." Differentiation comes from four monitoring engines behind one monitor object (cheap HTTP hashing → rendered DOM → pixel screenshots → price extraction), team workspaces with RBAC, Stripe-metered plans, and one-click compliance exports — packaged for SMB buyers who need uptime evidence for audits.

**Primary user workflows:**

| # | Workflow | Path |
|---|----------|------|
| 1 | Sign up → 3-step onboarding wizard (add URL → pick engine → set webhook) | `/register` → `/dashboard/onboarding` |
| 2 | Create monitor, first check runs immediately (`check_monitor.delay`) | `/dashboard/monitors/new` |
| 3 | Configure engine (HTTP/DOM/Screenshot/Price) + thresholds | `/dashboard/monitors/[id]` (`AdvancedConfigPanel`) |
| 4 | Triage changes/failures on dashboard; inspect diffs & price history | `/dashboard`, `/dashboard/monitors/[id]/diffs/[diffId]` |
| 5 | Invite team (Owner/Admin/Viewer), manage webhooks & API keys | `/dashboard/workspaces`, `/dashboard/channels`, `/dashboard/api-keys` |
| 6 | Upgrade plan via Stripe Checkout; manage subscription via Portal | `/dashboard/billing` |
| 7 | Download auditor-ready uptime/SLA report (CSV/PDF) | `/dashboard/compliance` |
| 8 | (Super-admin) SaaS telemetry + worker diagnostics | `/admin/metrics` |

### 1.2 Core Features Checklist

**HTTP Ping / content monitoring (default, cheapest).**
`Monitor` (`monitors/models.py:9`) with `check_interval` ∈ {30s, 1m, 5m, 15m, 30m, 60m} and `timeout` 1–120s (DB check constraint `monitor_timeout_range`). `check_monitor` (`monitors/tasks.py:102`) fetches via `httpx` (`services/fetcher.py`), normalizes content (strips `script/style/noscript/template`, collapses whitespace — `services/normalizer.py`), SHA-256 hashes it, and compares with `last_content_hash` (`services/change_detector.py`). First successful check establishes the baseline (never reported as a change). Monitor `status` property derives `healthy / changed / failing / paused / never_checked` from the latest `MonitorCheck`.

**DOM diffing (BeautifulSoup).**
`AdvancedMonitorConfig.mode = "dom"` + CSS `selector` (`monitors/models.py:166`). The browser-rendered HTML is normalized to text (`services/dom_diff.py`, ignores `script/style/noscript/svg`, optional selector scoping) and a `ChangeDiff(diff_type="dom")` row records "Normalized page content changed." Frontend renders it with `DiffViewer` (LCS line diff, `diff-viewer.tsx`).

**Playwright visual screenshots.**
`mode = "screenshot"`: `fetch_with_browser` (`services/browser_fetcher.py`) launches **headless Chromium per check** (1440×900, `networkidle`, full-page PNG). `compare_screenshots` (`services/screenshot_diff.py`, Pillow + `pixelmatch`, per-pixel threshold 0.1) yields a `% changed`; a `ChangeDiff(diff_type="screenshot")` is stored only when the percentage ≥ the user-configurable `screenshot_threshold` (0–100). ⚠️ There is **no persistent browser pool** — each check pays full browser launch cost (see §3.3, §5.4).

**Price tracking.**
`mode = "price"` + `price_selector` (+ optional `price_currency`): `extract_price` (`services/price_extractor.py`, regex for `$ € £` amounts, `Decimal` storage) writes a `PricePoint` per check; a `ChangeDiff(diff_type="price")` records "Price changed from X to Y CUR." The weekly digest reports price drift; `PriceIntelligenceCard` (`price-intelligence.tsx`) charts baseline vs. current with trend bars.

**Supporting capabilities:** pause/resume/test actions, per-user + per-workspace monitors, plan-gated intervals/limits, encrypted webhook secrets, programmatic `apeiro_…` Bearer tokens, weekly digest emails.

### 1.3 External Integrations — audited status

| Integration | Status | Evidence |
|-------------|--------|----------|
| **Stripe** | ✅ Implemented (Checkout, Customer Portal, webhooks; stub mode without keys) | `billing/views.py`, `billing/stripe_utils.py`, `STRIPE_*` env vars |
| **Slack / Discord / generic webhooks** | ✅ Implemented (outbound POST, secrets Fernet-encrypted) | `notifications/services.py:dispatch_webhooks`, `AlertChannel`, `/dashboard/channels` |
| **Google / GitHub OAuth (SSO)** | ✅ Implemented (server-side code exchange when secrets set; email-identity bridge otherwise) | `accounts/views.py:oauth_login`, `OAuthAccount`, login-page SSO buttons |
| **Email (SMTP / console)** | ✅ Implemented via Django `send_mail` (`console` in dev, `SMTP` in prod). `django-anymail` is installed but **not wired to any provider** | `config/settings/development.py:21`, `production.py:29` |
| **SendGrid** | ❌ **Not integrated** — no SDK calls, no backend config; only a docstring mention. AnyMail could be pointed at SendGrid later | — |
| **Twilio (SMS)** | ❌ **Not integrated** — `sms` exists only as an `AlertChannel` type label; dispatch POSTs JSON to the stored URL like a generic webhook. No Twilio SDK | `notifications/models.py`, `services.py` |
| **Telegram** | ❌ UI-only — shown in settings as "next on the roadmap"; no backend delivery | `alert-channels.tsx:110`, `settings/page.tsx` |
| **S3 / MinIO** | ❌ **Not integrated** — no boto/storage SDK. Artifacts live on local disk (`/app/storage/monitor-artifacts`) | `monitors/services/artifacts.py` |

> **Due-diligence flag:** buyer decks should not claim live SendGrid/Twilio/S3/Telegram integrations. Each is a small, well-isolated build-out (extension points in §5.5).

---

## 2. Frontend Architecture (Next.js)

**Stack:** Next.js 15 (App Router, `output: "standalone"` — `next.config.ts`), React 19, TypeScript, Tailwind CSS v4, `@tanstack/react-query` 5, `react-hook-form` + `zod`, `lucide-react` icons, `sonner` toasts. No Axios, no SWR, no separate state store.

### 2.1 Component Map

**Routes** (`frontend/app/**/page.tsx`, all currently client-rendered):

| Route | File | Purpose |
|-------|------|---------|
| `/` | `app/page.tsx` | Marketing landing |
| `/login`, `/register` | `app/login/page.tsx`, `app/register/page.tsx` | Email/password + Google/GitHub SSO buttons |
| `/dashboard` | `app/dashboard/page.tsx` | Overview: stat cards, live monitor list (30s refetch) |
| `/dashboard/monitors` | `app/dashboard/monitors/page.tsx` | Monitor list |
| `/dashboard/monitors/new` | `app/dashboard/monitors/new/page.tsx` | Create form (name/URL/interval/timeout) |
| `/dashboard/monitors/[id]` | `app/dashboard/monitors/[id]/page.tsx` | Detail + `AdvancedMonitoringSection` |
| `/dashboard/monitors/[id]/diffs/[diffId]` | `…/diffs/[diffId]/page.tsx` | Single diff view |
| `/dashboard/settings` | `app/dashboard/settings/page.tsx` | Email preferences + channel cards |
| `/dashboard/onboarding` | `app/dashboard/onboarding/page.tsx` | 3-step wizard |
| `/dashboard/workspaces` | `app/dashboard/workspaces/page.tsx` | Workspaces, members, invites |
| `/dashboard/billing` | `app/dashboard/billing/page.tsx` | Plans, checkout, portal |
| `/dashboard/channels` | `app/dashboard/channels/page.tsx` | Webhook CRUD (masked secrets) |
| `/dashboard/api-keys` | `app/dashboard/api-keys/page.tsx` | Token generate (shown once) / revoke |
| `/dashboard/compliance` | `app/dashboard/compliance/page.tsx` | Authenticated CSV/PDF download |
| `/admin/metrics` | `app/admin/metrics/page.tsx` | Super-admin SaaS telemetry + diagnostics |

**Reusable UI** (`frontend/components/`):

| Component | File | Role |
|-----------|------|------|
| `AdvancedConfigPanel` | `monitors/advanced-config.tsx` | Mode picker (HTTP/DOM/Screenshot/Price), selector/currency/threshold inputs, save + test |
| `AdvancedMonitoringSection` | `monitors/advanced-monitoring-section.tsx` | Wires config + diffs + prices on the detail page |
| `DiffViewer` (+ `diffLines`/`diffText` LCS utils, `priceDiffFromSummary` parser) | `observability/diff-viewer.tsx` | GitHub-style add/remove line diffs for dom/price/screenshot summaries |
| `PriceIntelligenceCard` | `observability/price-intelligence.tsx` | Baseline vs current, delta %, bar-chart trend |
| `AlertChannels` (+ `buildAlertChannels`, `DEFAULT_CHANNELS`) | `observability/alert-channels.tsx` | Channel status cards |
| `AppShell` / `Sidebar` / `Topbar` / `AccountMenu` | `layout/` | Navigation shell; sidebar links to all dashboard sections |
| `Modal`, `BackButton` | `ui/` | Primitives |
| `QueryProvider` | `providers/query-provider.tsx` | Single `QueryClient` (`staleTime` 30s, `retry: 1`), mounted in `app/layout.tsx` alongside the global `Toaster` |

### 2.2 State & API Layer

- **Transport:** `lib/api/client.ts` — thin `fetch` wrapper (`apiFetch`). No Axios/SWR. Domain modules per area: `auth.ts`, `monitors.ts`, `advanced.ts`, `notifications.ts`, `workspaces.ts`, `billing.ts`, `developer.ts` (API keys/OAuth/onboarding), `ops.ts` (metrics/diagnostics/compliance URL).
- **Auth handling:** JWT access token in `sessionStorage` (`apeiro_access`), refresh in `apeiro_refresh`. `apiFetch` attaches `Authorization: Bearer`, retries once after silent refresh on 401, clears session + throws "session has expired" on failure. Pages without React Query read `sessionStorage` directly and redirect to `/login` when absent. Tokens never go in `localStorage`; no Django secrets in frontend env (only `NEXT_PUBLIC_API_URL`).
- **Data fetching:** React Query (`useQuery` with 30s polling on the dashboard; `useMutation` for settings saves) mixed with plain `useEffect` + `useState` on newer CRUD pages — a known inconsistency (see §5.4).
- **Styling (dark-mode):** dark-only theme (`color-scheme: dark` in `app/globals.css`, 538 lines). Tailwind v4 `@theme inline` maps semantic tokens (`background`, `card`, `accent`, `success/warning/danger` + muted variants) to CSS variables; components use `apeiro-card`, `apeiro-btn`, `apeiro-input`, `apeiro-badge` utilities plus `animate-apeiro-*` animations.

---

## 3. Backend & Worker Engine Architecture (Django & Celery)

**Stack:** Django 5.2, DRF 3.18, SimpleJWT 5.5, Celery 5.6 (Redis broker + result backend), PostgreSQL 16, `httpx`, `beautifulsoup4`, `Pillow` + `pixelmatch`, Playwright + Chromium, `stripe`, `cryptography` (Fernet), `redis`, `reportlab` (PDF fallback is hand-rolled if missing).

### 3.1 Django Apps & REST API

**Apps** (`backend/*/apps.py`, all registered in `config/settings/base.py`): `accounts` (auth), `monitors`, `notifications`, `workspaces`, `billing`, `ops` (super-admin), `common` (crypto helpers).

**Authentication classes** (`REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES`, order matters):
1. `accounts.api_key_auth.ApiKeyAuthentication` — `Bearer apeiro_…` developer tokens (SHA-256 hash lookup, `last_used_at` touch, attaches `request.api_key`; returns `None` for non-`apeiro_` tokens so JWT still works; exposes `authenticate_header` so missing credentials yield **401**, not 403).
2. `rest_framework_simplejwt.authentication.JWTAuthentication` — 15-min access / 7-day refresh, **no rotation** (`ROTATE_REFRESH_TOKENS: False`).

**Endpoint inventory:**

| Prefix | Endpoints | Notes |
|--------|-----------|-------|
| `/api/health/` | `GET` | Unauthenticated liveness |
| `/api/auth/` | `register/`, `login/`, `oauth/` (google/github), `refresh/`, `me/`, `onboarding/` (GET/PATCH), `api-keys/` (list/create, key shown once), `api-keys/<uuid>/` (revoke = soft `revoked` flag) | Auto-creates Free `Subscription` + `OnboardingProgress` on signup |
| `/api/monitors/` | ViewSet CRUD + `pause/`, `resume/`, `test/`, `checks/`, `changes/`; `<uuid>/advanced/`, `<uuid>/advanced/test/`, `<uuid>/diffs/`, `<uuid>/prices/`; `export/compliance/?type=csv\|pdf` | Plan limits + workspace RBAC enforced (see below) |
| `/api/notifications/` | `preferences/` (GET/PATCH), `channels/` + `channels/<uuid>/` | Plan channel caps; workspace webhooks Owner/Admin-only |
| `/api/workspaces/` | CRUD, `members/` (GET/POST role change), `members/<id>` (DELETE), `invites/` (GET/POST), `invites/<token>/accept/` | Owner auto-membership; Owner role not grantable via invite |
| `/api/billing/` | `plans/`, `subscription/`, `checkout/`, `portal/`, `webhook/` (CSRF-exempt) | Stub URLs in dev; signature-verified when `STRIPE_WEBHOOK_SECRET` set |
| `/api/admin/` | `metrics/`, `diagnostics/` (GET + POST dispatch test) | `IsAdminUser` (staff/superuser) only |

**Data models (UUID PKs throughout):**

| Model | File | Key fields |
|-------|------|------------|
| `User` (custom, email login) | `accounts/models.py` | `email` (unique, lowercased), `is_staff`, `OAuthAccount`, `OnboardingProgress` (step/completed/engine/webhook), `ApiKey` (prefix, `key_hash`, scopes, workspace, revoked) |
| `Workspace`, `WorkspaceMembership` (owner/admin/viewer + rank map), `WorkspaceInvite` (token, role) | `workspaces/models.py` | slug auto-derivation; `unique_workspace_member` |
| `Monitor` | `monitors/models.py:9` | `user`, `workspace?`, intervals 30s–60m, `next_check_at`, `last_*` denormalized fields, timeout constraint |
| `MonitorCheck` | `monitors/models.py:114` | `checked_at`, `status_code`, `response_time_ms`, `content_hash`, `changed`, `error` |
| `AdvancedMonitorConfig` (HTTP/DOM/screenshot/price) | `monitors/models.py:166` | selector, price_selector/currency, screenshot_threshold |
| `ChangeDiff` (dom/screenshot/price) | `monitors/models.py:222` | prev/current check FKs, summary, `diff_percentage`, `artifact_path` |
| `PricePoint` | `monitors/models.py:292` | price (`Decimal`), currency, raw_value, 1:1 check link |
| `NotificationPreference`, `NotificationEvent` (change/failure/recovery, unique per check), `AlertChannel` (slack/discord/email/webhook/sms, `config_encrypted`) | `notifications/models.py` | Secrets encrypted via `common.crypto.EncryptedTextField` (Fernet, key derived from `DJANGO_SECRET_KEY`) |
| `Subscription` (free/pro/business; active/trialing/past_due/canceled/incomplete; `mrr_cents`, Stripe IDs) | `billing/models.py` | `PLAN_LIMITS`, `PLAN_MRR_CENTS` (Pro $19, Business $49) |

**Enforcement highlights:** monitor creation checks plan `max_monitors` (HTTP 402 + upgrade hint) and `min_interval_seconds` (serializer validation); channel creation checks `max_alert_channels`; workspace writes require Admin+ (`workspaces/permissions.py`); `MonitorViewSet` querysets union owned + workspace-member monitors (API-key requests scoped to the key's workspace; write scope `monitors:write`).

### 3.2 Asynchronous Worker Pipeline

```
Celery Beat (60s tick: schedule_due_monitors; 7d tick: send_weekly_digests)
  → Redis broker (queue "celery")
    → dispatch_monitor_check(monitor_id)
        ├─ advanced mode → run_advanced_monitor (browser engine)
        └─ http mode     → check_monitor (httpx engine)
    → notifications: queue_notification → send_notification_email (retry 3×, backoff)
```

- **Claim pattern:** `schedule_due_monitors` (`monitors/tasks.py:17`) selects due monitors, re-locks each with `select_for_update()` inside a transaction, advances `next_check_at` *before* dispatch — safe against duplicate execution across worker nodes.
- **Failure semantics:** first failure → `FAILURE` event + email; recovery → `RECOVERY` event; change → `CHANGE` event (each gated by `NotificationPreference` flags and a unique-per-check constraint). `send_monitor_email` fans out to Slack/Discord/webhooks via `dispatch_webhooks` after SMTP.
- **Advanced retries:** `run_advanced_monitor` (`max_retries=5`) retries only `retryable` browser errors (timeouts, 429, 5xx) with capped exponential backoff (60·2ⁿ, max 900s); 401/403/404 fail fast.
- **Digest:** `send_weekly_digests` (`notifications/tasks.py`) aggregates per-user uptime %, avg latency, and price drift over trailing 7 days.

### 3.3 Scraper Engines — differences & fallback logic

| | HTTP engine (`fetcher.py` + `normalizer.py`) | Browser engine (`browser_fetcher.py` + `dom_diff.py` / `screenshot_diff.py` / `price_extractor.py`) |
|---|---|---|
| Transport | `httpx` streaming client, manual redirect loop (max 5, every hop SSRF-validated) | Playwright Chromium, `networkidle`, full-page PNG + `page.content()` |
| Parsing | Raw bytes → charset-aware text normalization → SHA-256 | Rendered HTML → selector-scoped text → SHA-256 (DOM); pixel diff (screenshot); CSS-selector price regex (price) |
| Cost | ms, ~KB RAM | seconds, ~0.5–1 GB RAM transient per check |
| Security | Aggressive SSRF guard: blocks loopback/private/link-local/multicast/reserved IPs, `localhost`, cloud metadata hosts, credentialed URLs, non-80/443 ports; 10 MB cap | ⚠️ **No equivalent SSRF guard** — Playwright navigates the raw URL (gap, §5.4) |
| Retry | None (failure recorded immediately) | Retryable (timeout/429/5xx, 5 tries, backoff); non-retryable (401/403/404) |
| Fallback/routing | `dispatch_monitor_check` routes by `advanced_config.mode`; `HTTP` → lightweight task; anything else → browser task. `test_advanced_monitor` refuses `HTTP` mode. No automatic HTTP→browser upgrade on parse failure | |

---

## 4. Infrastructure, Docker & Artifact Storage

### 4.1 Container Breakdown (`docker-compose.yml`)

| Service | Image / build | Command | Ports (host:container) | Depends on |
|---------|---------------|---------|------------------------|------------|
| `frontend` | `frontend/Dockerfile` (node:22-alpine, dev target, `npm run dev`, live bind-mount + `WATCHPACK_POLLING`) | `npm run dev --hostname 0.0.0.0` | `3000:3000` | backend (started) |
| `backend` | `backend/Dockerfile` (python:3.12-slim, pip install, **`playwright install --with-deps chromium`** ≈ slow/heavy layer) + `runserver` | `manage.py runserver 0.0.0.0:8000` | `8000:8000` | postgres, redis (healthy) |
| `celery-worker` | same backend image | `celery -A config worker` | — | postgres, redis |
| `celery-beat` | same backend image | `celery -A config beat` | — | postgres, redis |
| `postgres` | `postgres:16-alpine`, volume `postgres_data` | — | `5434:5432` | (healthcheck `pg_isready`) |
| `redis` | `redis:7-alpine`, volume `redis_data` | — | `6380:6379` | (healthcheck `ping`) |

Notes: the dev overlay runs Django's dev server (not Gunicorn). Production uses `docker-compose.prod.yml`: Gunicorn (`config.wsgi:application`, 3 workers, 120s timeout), Next.js standalone image, no source bind-mounts, no published DB ports, `restart: unless-stopped`, capped JSON logs (`10m` × 3), password-required Postgres/Redis, and per-service healthchecks. `/api/health/` returns per-dependency statuses (`postgres`/`redis`/`celery`, HTTP 200/503). No Nginx, no TLS termination, no S3/MinIO service — terminate TLS at the VPS edge (Caddy/Traefik) or PaaS router. `frontend_next` / `node_modules` use named volumes. A stray `backend/celerybeat-schedule` file is committed to the repo (beat state — should be git-ignored).

### 4.2 Media & Artifact Persistence

- **Layout:** `save_artifact()` writes `/app/storage/monitor-artifacts/<monitor_id>/<check_id>/<uuid4>.<ext>` (`.html` normalized snapshots; `.png` screenshots; `-diff.png` visual diffs). Because `./backend:/app` is a **bind mount**, artifacts persist on the Docker host at `backend/storage/` (currently empty upstream).
- **DB linkage:** `ChangeDiff.artifact_path` stores the absolute container path; there is **no serving endpoint** for artifacts (paths are returned in API JSON but not downloadable — frontend gap).
- **Cleanup:** ⚠️ **none** — no retention job, no S3 lifecycle, no quota. Screenshot monitors at 30s intervals will grow disk unboundedly (top tech-debt item, §5.4). Buyer extension: Celery cleanup task + plan-gated retention (`history_days` already in `PLAN_LIMITS` but unenforced).

### 4.3 Environment Variables Matrix

| Variable | Required | Used by | Default / notes |
|----------|----------|---------|-----------------|
| `DATABASE_URL` | Yes | backend/worker/beat | `postgres://apeiro:apeiro@postgres:5432/apeiro` |
| `POSTGRES_DB/USER/PASSWORD` | Yes | postgres container | `apeiro/apeiro/apeiro` (change in prod!) |
| `REDIS_URL` | Yes | backend/worker/beat, ops diagnostics | `redis://redis:6379/0` |
| `DJANGO_SECRET_KEY` | **Yes — rotate!** | Django + Fernet secret derivation + JWT signing | dev-only placeholder in repo |
| `DJANGO_DEBUG` | Yes | settings switch | `1` dev / `0` prod image |
| `FRONTEND_URL` / `BACKEND_URL` / `NEXT_PUBLIC_API_URL` | Yes | CORS, Stripe return URLs, frontend API base | `http://localhost:3000` / `:8000` |
| `EMAIL_PROVIDER_API_KEY`, `EMAIL_FROM` | Optional | reserved for provider key; `EMAIL_FROM` is the sender | console backend in dev |
| `EMAIL_HOST/PORT/USER/PASSWORD/TLS` | Prod only | SMTP backend (`production.py`) | — |
| `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` | Prod only | `production.py` hardening (HSTS, secure cookies, `X-Frame: DENY`) | — |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_PRO/BUSINESS` | For live billing | `billing/` (stub mode when empty) | empty = demo-safe |
| `GOOGLE_CLIENT_ID/SECRET`, `GOOGLE_REDIRECT_URI`, `GITHUB_CLIENT_ID/SECRET` | For real SSO exchange | `accounts/views.py:_exchange_oauth_code` | empty = bridge mode |
| `POSTGRES_HOST/PORT` | No | fallback DB pieces when `DATABASE_URL` unset | `postgres/5432` |

---

## 5. Buyer Operational & Handover Manual

### 5.1 Local Setup & Deployment Guide

**Local (verified working):**
```sh
cp .env.example .env            # fill secrets (never commit .env)
docker compose up --build       # first boot: includes Chromium install (~5-10 min)
docker compose exec backend python manage.py migrate
# app: http://localhost:3000 · API: http://localhost:8000/api/health/
# create superuser for /admin/metrics:
docker compose exec backend python manage.py createsuperuser
```
Non-Docker backend work (tests): `backend/.venv-linux` exists; run with `DATABASE_URL=postgres://apeiro:<pw>@localhost:5434/apeiro REDIS_URL=redis://localhost:6380/0 DJANGO_SETTINGS_MODULE=config.settings.development python manage.py test accounts monitors notifications`.

**Production deploy (recommended path — Render/Railway/AWS/DigitalOcean):**
1. Set `DJANGO_DEBUG=0`, strong `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`; use `config.settings.production`.
2. Replace `runserver` with `gunicorn config.wsgi:application` (+ `--workers 3`); put Cloudflare/CDN + managed TLS in front.
3. Use managed Postgres 16 + managed Redis (or same-VPS containers to start); set `DATABASE_URL`/`REDIS_URL` accordingly.
4. Run `migrate` on release; `collectstatic` if admin/static is ever enabled (currently no static pipeline beyond defaults).
5. Configure `EMAIL_HOST_*` (SMTP) or wire AnyMail→SendGrid; add `STRIPE_*` + webhook endpoint `https://<api>/api/billing/webhook/`; add OAuth app credentials + redirect URIs.
6. Persist `/app/storage` on a volume (or migrate to S3 — §5.5); add artifact retention cron.
7. Scale horizontally: `celery-worker --concurrency N` replicas; Playwright checks are RAM-bound (~1 per 512 MB–1 GB).

### 5.2 Monthly Infrastructure Cost Breakdown (2026 estimates)

| Topology | Components | ≈ Cost/mo | Limits |
|----------|-----------|-----------|--------|
| **Single VPS (start here)** | 1× 4 GB VPS (Hetzner CX32 ≈ $12 / DO Basic ≈ $24) + Docker Compose all-in | **$12–$25** | ~500 monitors @5m HTTP; ~20 concurrent browser checks; disk = artifact growth |
| **Managed data** | + Managed Postgres ($15) + Managed Redis ($10–15) | **$40–$55** | Backups, failover offloaded |
| **Growth (+2 workers)** | + 2× worker VPSs, shared Redis/Postgres | **$70–$110** | ~5k monitors; browser checks shard by queue |
| Serverless PaaS (Render/Railway) | web + worker + beat + PG + Redis, billed per service | **$35–$80** | Simplest ops; Playwright needs ≥2 GB instances |

Unit economics sanity: Business plan MRR $49 covers a single-VPS fleet at ~5–10 paying customers; gross margin expands steeply since HTTP checks cost fractions of a cent.

### 5.3 Scalability Limits (as built)

- Browser checks launch a full Chromium per execution — the binding constraint (RAM, not CPU). Cap `screenshot`/`dom`/`price` concurrency via Celery worker concurrency + separate queue before marketing 30s visual plans.
- `schedule_due_monitors` pulls all due IDs each minute; fine to ~10k monitors, then needs batching/sharding (extension point exists: `services/scheduler.py:get_due_monitors(limit=100)`).
- Artifact disk is unbounded (no cleanup); monitor `backend/storage` size from day one.
- JWT has no rotation/blacklist; API-key auth is a single global hash lookup (add per-key rate limits for public API exposure).

### 5.4 Technical Debt & Due-Diligence Findings

| # | Finding | Severity | Fix effort |
|---|---------|----------|------------|
| 1 | No artifact retention/cleanup job (unbounded disk) | **High** | S — Celery task deleting by `history_days` |
| 2 | Browser engine lacks the HTTP engine's SSRF guard | **High (security)** | S — reuse `validate_url()` pre-navigation |
| 3 | No per-check browser pool (launch per check) | Medium (cost/perf) | M — persistent Playwright context pool |
| 4 | Repo is not a git repository; `celerybeat-schedule` binary committed | Medium (process) | S — `git init`, `.gitignore` beat file |
| 5 | ~~`monitors/advanced_urls.py` is dead code~~ — removed during the pre-launch freeze (verified zero imports before deletion) | Done | — |
| 6 | Frontend mixes React Query and ad-hoc `useEffect` fetching across pages | Low | M — standardize on Query hooks |
| 7 | Refresh tokens never rotate; no blacklist app installed | Low | S — SimpleJWT rotation + denylist |
| 8 | Artifact paths exposed but not servable (no download endpoint) | Low | S — signed-URL media view |
| 9 | `?format=` query key unusable on compliance export (DRF renderer 404) — documented workaround `?type=` | Low (docs) | XS — custom renderer or rename |
| 10 | Dev `runserver`, default DB passwords, committed `.env` pattern need production hardening (§5.1) | Medium | S — deploy checklist above |

### 5.5 Growth Levers (clean extension points for a buyer)

- **Proxy rotation & multi-region checks:** add `proxy` + `region` fields to `Monitor`; thread through `fetch_url()` (`httpx.Proxy`) and `browser.new_context(proxy=…)`; route Celery tasks by region queue. All call sites are single functions.
- **Real SendGrid/Twilio/Telegram:** implement one provider class each behind `dispatch_webhooks()`; secrets already flow through the encrypted `AlertChannel` model — no schema change.
- **S3/MinIO artifacts:** swap `save_artifact()` internals to `boto3` + return keys; serve via signed URLs (fixes finding #8); enforce `PLAN_LIMITS[].history_days` as retention.
- **Status pages & SLA webhooks:** new read-only public view over `MonitorCheck` aggregates (the compliance export already computes them).
- **Metered overages:** Stripe usage-based line items on top of `checks_24h` metrics already exposed by ops.
- **Enterprise SSO (SAML/OIDC):** extend `OAuthAccount.provider` choices; the JWT issuance path is provider-agnostic.

---

*Document generated from a full file-level audit of `backend/`, `frontend/`, `docker-compose.yml`, `.env(.example)`, and requirements. Integration claims above reflect code actually present — SendGrid, Twilio, Telegram, and S3 are explicitly called out as **not** implemented to protect buyer diligence.*
