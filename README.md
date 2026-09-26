# Sitemyra

Competitive intelligence that starts with a URL.

Paste a competitor or product URL. Sitemyra reads the page, decides what
is worth watching, and tells you what changed — with the source, the
timestamp and the before/after attached to every claim.

## What's in the box

- Next.js and TypeScript frontend
- Django and Django REST Framework backend
- PostgreSQL for application data
- Redis for Celery messaging
- Celery workers: a lightweight **HTTP worker** (queues `celery_http` + `celery_notifications`, no Chromium), a dedicated **browser worker** (queue `celery_browser`, concurrency 1, one Chromium per prefork child), and Celery beat
- Team workspaces/RBAC, Stripe billing, alert channels, compliance export, onboarding
- **Competitive intelligence** (`intelligence` app): URL analysis, discovered monitoring targets, monitoring recipes, product tracking, and explainable field-level change history

Monitoring checks run fully without Chromium for 16 of 19 features; only the `dom`, `price` and `screenshot` modes execute in the isolated browser worker. See `SYSTEM_DOCUMENTATION.md` for architecture, `docs/INTELLIGENCE-ROADMAP.md` for the competitive-intelligence roadmap, `docs/DEPLOY-PHASE1.md` for the Phase 1 release handoff, and `docs/BROWSER-WORKER.md` for the browser-worker internals.

## Competitive intelligence (Phase 1, shipped)

The intake flow is the product. `/dashboard/monitors/new` asks for one
thing — a URL — and then:

1. **Analyses the page.** JSON-LD, microdata, OpenGraph, and (for
   storefronts with no structured data) token-matched price and stock
   elements. Every value is stored with the method that read it and the
   raw text it came from.
2. **Classifies it** as product / pricing / features / changelog /
   careers / … and **discovers** the other same-origin pages worth
   watching. Each suggestion states the observable signal behind it.
3. **Activates** them in one click, or lets the user pick a recipe
   (Pricing, Product, Feature, Marketing, SEO, Hiring, E-commerce,
   Everything) or hand-pick pages.
4. **Tracks product data** on the product page: price, list price,
   discount, currency, availability, stock status, variants, sizes,
   colours, images, rating, review count, badges, bundles, shipping and
   specifications.
5. **Explains every change** as what changed / why it may matter / what
   to check, with severity, the rule that classified it, the source URL
   and the detection time.

Two design decisions worth knowing:

- **A product watch costs no extra request.** The HTTP worker already
  downloads the page for the content hash; product extraction runs on
  those same bytes. No second fetch, no browser slot.
- **No model call on this path.** Every explanation is produced by a
  named, tested rule in `intelligence/services/product_diff.py`. Optional
  AI narration layers on top of exactly these records in Phase 3 and
  never replaces them.

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /api/intelligence/analyze/` | user | Analyse a URL, cache the result, return facts + discovered targets |
| `POST /api/intelligence/public/analyze/` | none (throttled by `PUBLIC_ANALYZE_RATE`) | Homepage demo. Redacted, never persisted, no user reference |
| `POST /api/intelligence/activate/` | user | Create monitors from selected targets or a recipe |
| `POST /api/intelligence/quick-monitor/` | user | Feature 7 one-shot: analyse + activate. Idempotent |
| `GET /api/intelligence/recipes/` | user | Recipe catalogue |
| `GET /api/intelligence/product-watches/` | user | List tracked products |
| `GET /api/intelligence/product-watches/{id}/` | user | Watch + current snapshot + timeline + explanation |
| `GET /api/intelligence/product-watches/{id}/timeline/` | user | Field-change timeline, filterable by severity/category |
| `GET /api/intelligence/monitors/{id}/product/` | user | Product state for one monitor (404 when there is none) |

"Monitor this page" works today as a bookmarklet with **no token in the
browser**: `frontend/public/sitemyra-bookmarklet.js` only opens Sitemyra
with the current URL, and sign-in happens in the app. A Chromium
extension is designed in Phase 6 of the roadmap.

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

The production Sitemyra domain is configurable through environment variables. Before going live, update these values (see `.env.example`) — no application code changes are needed:

* `FRONTEND_URL` — public app URL (also used for OAuth fallbacks/email links)
* `NEXT_PUBLIC_SITE_URL` — public website origin used for canonical URLs,
  OpenGraph, sitemap, robots, and structured data
* `NEXT_PUBLIC_CONTACT_EMAIL` — optional verified public contact mailbox; leave
  blank until a monitored support address is confirmed
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

* `EMAIL_REPLY_TO` — optional Reply-To address for transactional alert and
  digest messages; configure only after verifying that it is monitored

Provider-console checklists (Google, GitHub, Stripe) and DNS/mailbox setup
are manual deployment steps — see the final verification report.

### Public website routes

The public Next.js surface includes `/`, `/how-it-works`, `/pricing`, `/faq`,
`/about`, `/contact`, `/security`, `/privacy`, `/terms`, and `/cookies`. These
pages use a marketing-only shell and do not alter the dashboard `AppShell`.
`/opengraph-image`, `/robots.txt`, and `/sitemap.xml` are generated by the
frontend. Do not add analytics or a contact form without updating the privacy,
cookie, security, and backend review notes first.

## Authentication

The API uses short-lived JWT access tokens (15 minutes) and refresh tokens (7 days) in the `Authorization: Bearer <access-token>` header. The frontend should keep tokens in memory and use the refresh endpoint when an access token expires; do not put tokens in `localStorage` or expose Django secrets to frontend environment variables. Refresh tokens are not rotated in this phase and should be treated as sensitive credentials.

Google/GitHub SSO is available at `POST /api/auth/oauth/` (JWT is still returned, so the frontend flow is unchanged). The backend exchanges the OAuth `code` server-side against `GOOGLE_/GITHUB_CLIENT_ID+SECRET`; there is no bridge/fallback identity path — without those credentials configured the exchange fails, so SSO requires the provider credentials.

## Enterprise SaaS modules

- **Team Workspaces & RBAC** (`/api/workspaces/`): create workspaces, invite members as `owner`/`admin`/`viewer`, accept invites via token, and attach monitors to a workspace. Owner/Admin permissions are enforced on the main management paths; the action-level RBAC gaps are tracked in `docs/SECURITY-REVIEW-TODO.md` before making a strict read-only claim.
- **Stripe billing** (`/api/billing/`): `plans/`, `subscription/`, `checkout/` (Checkout), `portal/` (Customer Portal), `webhook/` (dunning → `past_due`, cancel → graceful downgrade to Free with excess monitors paused, never deleted). Without configured Stripe keys, checkout and portal return an unavailable response (the explicit development stub is opt-in). Plan limits enforced: Free 3 URLs / 15m / 1 channel / 7d history, Pro $19 → 25 URLs / 5m / 5 channels / 30d, Business $49 → 100 URLs / 1m / 50 channels / 90d.
- **Staff telemetry** (`/api/admin/metrics/`, `/api/admin/diagnostics/`, staff-only): MRR, active subscribers, 24h checks, queue latency, churn risk, plus Redis/Celery/Playwright health checks. Frontend: `/admin/metrics`.
- **Onboarding & retention**: 3-step wizard (`/dashboard/onboarding`, state at `/api/auth/onboarding/`) and a weekly digest email (`notifications.tasks.send_weekly_digests`, scheduled weekly via Celery beat). The digest has an Account settings opt-out.
- **Security & compliance**: third-party secrets (alert channels) encrypted at rest with Fernet (`common.crypto.EncryptedTextField`); 1-click compliance CSV/PDF export (`/api/monitors/export/compliance/?type=csv|pdf`, UI at `/dashboard/compliance`); developer Bearer tokens (`apeiro_…`) at `/api/auth/api-keys/` (UI at `/dashboard/api-keys`), hash-only storage, workspace RBAC enforced.
