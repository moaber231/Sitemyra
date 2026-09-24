# Sitemyra

Website monitoring that tells you what changed.

## What's in the box

- Next.js and TypeScript frontend
- Django and Django REST Framework backend
- PostgreSQL for application data
- Redis for Celery messaging
- Celery workers: a lightweight **HTTP worker** (queues `celery_http` + `celery_notifications`, no Chromium), a dedicated **browser worker** (queue `celery_browser`, concurrency 1, one Chromium per prefork child), and Celery beat
- Team workspaces/RBAC, Stripe billing, alert channels, compliance export, onboarding

Monitoring checks run fully without Chromium for 16 of 19 features; only the `dom`, `price` and `screenshot` modes execute in the isolated browser worker. See `SYSTEM_DOCUMENTATION.md` for architecture and `docs/BROWSER-WORKER.md` for the browser-worker internals.

## Run locally

1. Copy `.env.example` to `.env` and replace the placeholder secrets.
2. Start the development stack:

   ```sh
   docker compose up --build
   ```

3. Apply backend migrations in a second terminal:

   ```sh
   docker compose exec backend python manage.py migrate
   ```

4. Open the frontend at http://localhost:3000 and the backend health endpoint at http://localhost:8000/api/health/.

The backend container runs Django's development server. Monitoring checks execute on the `celery-http-worker` and `celery-browser-worker` services that the same compose file starts.

## Production deploy (single VPS or PaaS)

A hardened production overlay lives in `docker-compose.prod.yml`: Gunicorn API (3 workers, 120s timeout), split Celery services (`celery-http-worker` without Chromium, `celery-browser-worker` with Chromium at concurrency 1, `celery-beat`), Next.js standalone build, no source mounts, no published DB ports, a named `artifact_data` volume, `restart: unless-stopped`, and capped JSON logs (`10m` × 3) on every service. PostgreSQL/Redis refuse to start without real secrets (`POSTGRES_*`, `REDIS_PASSWORD`).

```sh
cp .env.example .env   # fill secrets; set REDIS_URL=redis://:<password>@redis:6379/0
docker compose -f docker-compose.prod.yml up --build -d
docker compose -f docker-compose.prod.yml exec backend python manage.py migrate
```

`/api/health/` reports `postgres` / `redis` / `celery` connectivity (HTTP 200 when all healthy, 503 otherwise) for load-balancer and compose healthchecks.

### Deployment domain configuration

The production Sitemyra domain is **not** hardcoded anywhere. Before going
live, update these environment variables (see `.env.example`) — no code
changes are needed:

* `FRONTEND_URL` — public app URL (also used for OAuth fallbacks/email links)
* `NEXT_PUBLIC_API_URL` / `BACKEND_PUBLIC_URL` — public API origin for the
  browser bundle and pre-built frontend image
* `BACKEND_URL` — internal API origin for local development
* `DJANGO_ALLOWED_HOSTS` — API host(s)
* `CORS_ALLOWED_ORIGINS` — frontend origin(s) allowed to call the API
* `GOOGLE_REDIRECT_URI` / `GITHUB_REDIRECT_URI` — must exactly match the
  redirect URIs registered in the Google/GitHub provider consoles
  (default: `<FRONTEND_URL>/auth/callback`)
* Stripe webhook endpoint — `<BACKEND_URL>/api/billing/webhook/` must be
  registered in the Stripe dashboard (with `STRIPE_WEBHOOK_SECRET`)
* `EMAIL_FROM` — production sender mailbox (e.g. `info@<your-domain>`);
  `EMAIL_FROM_NAME` (default `Sitemyra`); `EMAIL_HOST/PORT/USER/PASSWORD`
  plus `EMAIL_USE_SSL=1` (Hostinger, port 465) or `EMAIL_USE_TLS=1` (port 587)

Provider-console checklists (Google, GitHub, Stripe) and DNS/mailbox setup
are manual deployment steps — see the final verification report.

## Authentication

The API uses short-lived JWT access tokens (15 minutes) and refresh tokens (7 days) in the `Authorization: Bearer <access-token>` header. The frontend should keep tokens in memory and use the refresh endpoint when an access token expires; do not put tokens in `localStorage` or expose Django secrets to frontend environment variables. Refresh tokens are not rotated in this phase and should be treated as sensitive credentials.

Google/GitHub SSO is available at `POST /api/auth/oauth/` (JWT is still returned, so the frontend flow is unchanged). The backend exchanges the OAuth `code` server-side against `GOOGLE_/GITHUB_CLIENT_ID+SECRET`; there is no bridge/fallback identity path — without those credentials configured the exchange fails, so SSO requires the provider credentials.

## Enterprise SaaS modules

- **Team Workspaces & RBAC** (`/api/workspaces/`): create workspaces, invite members as `owner`/`admin`/`viewer`, accept invites via token. Viewers are read-only; only Owner/Admin can manage API keys and webhook configs. Monitors can belong to a workspace.
- **Stripe billing** (`/api/billing/`): `plans/`, `subscription/`, `checkout/` (Checkout), `portal/` (Customer Portal), `webhook/` (dunning → `past_due`, cancel → graceful downgrade to Free with excess monitors paused, never deleted). Without `STRIPE_SECRET_KEY` the endpoints run in stub mode so demos/CI work keyless. Plan limits enforced: Free 3 URLs / 15m / 1 channel / 7d history, Pro $19 → 25 URLs / 5m / 5 channels / 30d, Business $49 → 100 URLs / 1m / 50 channels / 90d.
- **Super-admin telemetry** (`/api/admin/metrics/`, `/api/admin/diagnostics/`, superuser-only): MRR, active subscribers, 24h checks, queue latency, churn risk, plus Redis/Celery-beat/Playwright health checks. Frontend: `/admin/metrics`.
- **Onboarding & retention**: 3-step wizard (`/dashboard/onboarding`, state at `/api/auth/onboarding/`) and a weekly digest email (`notifications.tasks.send_weekly_digests`, scheduled weekly via Celery beat).
- **Security & compliance**: third-party secrets (alert channels) encrypted at rest with Fernet (`common.crypto.EncryptedTextField`); 1-click compliance CSV/PDF export (`/api/monitors/export/compliance/?type=csv|pdf`, UI at `/dashboard/compliance`); developer Bearer tokens (`apeiro_…`) at `/api/auth/api-keys/` (UI at `/dashboard/api-keys`), hash-only storage, workspace RBAC enforced.
