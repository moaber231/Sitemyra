# Sitemyra — Zero-Cost Infrastructure Optimization Plan (Phase 1 Deliverable)

**Status:** PLAN — awaiting approval. No application code has been modified.
**Basis:** four read-only audits (Docker/compose/settings/env, Celery/tasks/DB, Playwright engine, feature/portability) plus direct measurement of the built images.
**Method note:** values marked **[MEASURED]** were read from the actual image/filesystem. Values marked **[EST]** are estimates pending post-implementation measurement (Phase 12 mandates re-measuring with `docker stats` sampling before `docs/RESOURCE-BUDGET.md` is finalized).

---

## 1. Architecture audit (as-built)

### 1.1 Current topology

```
docker-compose.prod.yml (6 services, ONE backend image shared by 3 of them)

frontend   → node:22-alpine, standalone build, non-root, healthcheck "/"
backend    → python:3.12-slim + Chromium  → gunicorn ×3, healthcheck /api/health/
celery-worker → same image                → prefork, --concurrency=4, NO healthcheck
celery-beat   → same image                → beat, NO healthcheck, NO volume for beat schedule
postgres 16-alpine → volume postgres_data, healthcheck
redis 7-alpine    → volume redis_data, requirepass, healthcheck
(+ dev-only: minio)
```

**Measured composition of `apeiro-backend` = 1,815,078,358 B (1.82 GB):**

| Layer | Size [MEASURED] | Actually needed by |
|---|---|---|
| `python:3.12-slim` base + apt layers | ~170 MB | all services |
| `pip install -r requirements.txt` | 314 MB | API needs **~167 MB** (314 − playwright 140 − PIL 6.9 − pixelmatch 0.08) |
| `COPY . .` | **328 MB** | **0 MB — this is `backend/.venv-linux` (339 MB) leaking in.** Real source = **484 KB** |
| `RUN playwright install --with-deps chromium` | **1.05 GB (58%)** | **browser worker only** (658 MB browsers in `/root/.cache/ms-playwright` + apt deps + 21 MB apt lists never cleaned) |

Sub-packages inside site-packages (354 MB total): `playwright` 140 MB (incl. bundled Node driver 121 MB), `stripe` 18 MB, `Pillow` 6.9 MB, `boto3` 1.6 MB, `pixelmatch` 76 KB.

**Root cause of the 328 MB leak:** `backend/.dockerignore` contains `__pycache__ / *.pyc / .venv / .git` — it ignores `.venv`, but the directory on disk is `.venv-linux` (git-ignored at `.gitignore:10`, not tracked). `COPY . .` therefore ships a full local virtualenv, including a second Playwright/Node driver copy, into every build of every backend-derived image.

**Layer-order flaw:** `RUN playwright install` (line 16) sits *after* `COPY . .` (line 12), so any code change re-runs the 1.05 GB Chromium download + apt install (the repo's own docs call this "slow/heavy layer", ~5–10 min).

### 1.2 Who needs what (dependency matrix)

| Dependency | API (gunicorn) | beat | HTTP worker | Browser worker |
|---|---|---|---|---|
| Django/DRF/celery/httpx/bs4/cryptography/redis | ✅ | ✅ | ✅ | ✅ |
| `stripe` (lazy import) | ✅ | ❌ | ❌ | ❌ |
| `reportlab` (function-local, has fallback) | ✅ | ❌ | ❌ | ❌ |
| `boto3` (artifact storage; API presigns, worker writes) | ✅ if s3 | ❌ | ❌ | ✅ if s3 |
| `playwright` + Chromium binary | ❌ | ❌ | ❌ | ✅ |
| `Pillow`, `pixelmatch` | ❌ | ❌ | ❌ | ✅ |
| `python-dotenv`, `django-anymail` — **never imported anywhere** | ❌ | ❌ | ❌ | ❌ |

**Critical blocker for the split (verified import chain):**
```
config/urls.py:70 → monitors/urls.py:4 → advanced_api.py:19  from .advanced_tasks import run_advanced_monitor
monitors/views.py:16 → tasks.py:192       from .advanced_tasks import run_advanced_monitor   (module-level re-export)
advanced_tasks.py:16,25 → browser_fetcher.py:4 (playwright) + screenshot_diff.py:3 (PIL/pixelmatch)
```
⇒ **gunicorn and beat cannot start without `playwright`, `Pillow`, `pixelmatch` installed today.** Chromium itself is only ever executed by the worker, but the packages must import at process start. This must be decoupled before the image can split. (`ops/views.py:54` also imports `browser_fetcher` lazily inside the diagnostics endpoint — needs an import guard.)

### 1.3 Celery configuration (all defaults, nothing tuned)

`config/celery.py:7-9` reads only `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` (same Redis DB as broker), `CELERY_TIMEZONE`, `CELERY_BEAT_SCHEDULE`. **Absent:** `task_routes`, `task_queues`, `acks_late`, `reject_on_worker_lost`, `prefetch_multiplier`, `time_limit`/`soft_time_limit`, `track_started`, `result_expires`, `ignore_result`. Zero matches for `queue=`/`apply_async` — **one implicit queue `celery`** (confirmed by `ops/views.py:163` `llen("celery")`).

- 8 tasks total; **2 have no callers** (`send_notification_email`, `deliver_monitor_event`); `monitors/services/scheduler.py` is dead code.
- No `AsyncResult`/`ResultSet` anywhere → results are written and never read; the only `.get()` is a local `.apply()` EagerResult inside `ops/views.py:223`.
- Prod concurrency: `--concurrency=4` prefork; dev: CPU count. No `--max-tasks-per-child`.
- Beat: 60 s scheduler tick, 7-day digest (a float interval, *not* the `crontab` its comment claims), daily 00:00 artifact cleanup.

### 1.4 Playwright engine (per-check launch, no reuse)

- `browser_fetcher.py:51-52`: **new `sync_playwright()` + new `chromium.launch()` per call**, no launch args (no `--disable-dev-shm-usage` → Docker's 64 MB `/dev/shm` crash hazard unmitigated), no context reuse (creates `browser.new_page()` directly, not `new_context()`), no route interception, `wait_until="networkidle"`, `full_page=True` screenshot with no timeout, no `set_default_timeout` anywhere.
- Cleanup: `finally: browser.close()` covers normal exceptions, but leaks exist on (a) mid-launch failure, (b) `close()` hang (no timeout, and no Celery time limit to break the wedge), (c) **SIGKILL/OOM — `finally` never runs, no reaper exists**. The catch-all marks every generic exception `retryable=True` → up to 5 fresh Chromium launches per doomed check (~28 min of retries).
- `ops/views.py:59` reports *"pool lazily created per check"* — **there is no pool object at all**; the string is aspirational.
- **SSRF:** `validate_url` **is** called pre-navigation (`browser_fetcher.py:34-45`) and blocks private/loopback/metadata IPs, credentials, non-80/443 ports. Residual gaps: (1) Chromium follows redirects natively — **no per-hop revalidation** (HTTP engine does revalidate every hop), (2) **no subresource filtering** (page can fetch `127.0.0.1`, metadata IPs), (3) DNS-rebinding TOCTOU (self-acknowledged in code), (4) `parsed.port` raises `ValueError` for `:99999` → **escapes uncaught**, task dies with no `MonitorCheck` row, (5) IPv4-mapped IPv6 (`[::ffff:127.0.0.1]`) untested.
- **Screenshot memory:** `compare_screenshots` holds **3 full-page RGBA buffers** = `3 × 1440 × H × 4` B: 15.6 MB at viewport, 173 MB at H=10k, **864 MB at H=50k** — and it runs *inside* `transaction.atomic()` (`advanced_tasks.py:163`), holding a DB transaction across image decode + temp-file I/O.
- **Uncaught `ValueError`s:** CSS-selector misses (`dom_diff.py:24`, `price_extractor.py:32`) raised from `advanced_tasks.py:140` (outside any handler → task dies silently) and `:299` (inside the transaction → rollback orphans an already-written artifact object).

### 1.5 Artifact storage growth (unbounded despite the retention task)

- Retention task exists and is idempotent (storage objects deleted before rows), daily 00:00, driven **only** by plan `history_days` (7/30/90) — **no `ARTIFACT_RETENTION_DAYS` env var exists**, no byte accounting, no logging (`totals` returned into the unread result backend), empty-dir pruning only removes the immediate check dir (never `artifacts/<monitor_id>/`).
- **Four orphan paths the task cannot see** (it only walks keys referenced by live `ChangeDiff` rows):
  1. `save_artifact(html)` runs on **every** advanced check (`advanced_tasks.py:193`) but the key is linked to a diff **only `if changed`** → unchanged checks' HTML is referenced by nothing, forever. Business plan: 100 monitors × 60 s ≈ **144k orphan files/day**.
  2. Screenshots likewise saved every check, linked only when changed or on first check.
  3. `Monitor` deletion cascades `ChangeDiff` rows **without deleting objects** (no `pre_delete`/signal anywhere).
  4. Transaction rollback after a storage write (price-selector miss).
- HTTP checks save no artifacts (`save_artifact` appears only in `advanced_tasks.py`).
- Prod compose has **no volume** for `/app/storage` → local artifacts are also ephemeral today.

### 1.6 Database & query profile

- **Well-indexed hot paths:** `(active, next_check_at)` for the scheduler, `(monitor, -checked_at)` for check history, unique `(monitor_check, event_type)` for notification dedupe. No Django signals → no hidden write fan-out.
- **Missing indexes:** `MonitorCheck.checked_at` (admin metrics does 3 sequential scans over the largest table per request), `Subscription.status` + `updated_at` + `stripe_subscription_id`/`stripe_customer_id` (Stripe webhook: up to 4 sequential scans).
- **N+1s:** monitor list = **2 queries per monitor** (`Monitor.status` property `models.py:109` + `MonitorSerializer.get_last_response_time_ms` `serializers.py:49`) with **no DRF pagination anywhere**; weekly digest = `1 + U×2 + U×M×4` queries + U SMTP sends in one unlimited task (10k users × 5 monitors = **100,002 queries**); compliance export = 5 queries per monitor synchronously in-request; admin metrics `_disk_usage()` does a full `rglob` disk walk per request.
- **Scheduler:** unbounded due-ID list, then per monitor `SELECT FOR UPDATE` + `UPDATE` + **one Redis publish**, and `dispatch_monitor_check` publishes a **second** message (2 messages + 2 task executions per actual check). Runs synchronously inside `POST /api/admin/diagnostics/` too.
- **Notifications run inline in check tasks** (`monitors/tasks.py:67-76`, `advanced_tasks.py:344-352` → `dispatch_monitor_event`): per event ≈5–6 queries + 1 SMTP (with inline 0.5 s retry sleep) + K webhooks, each up to 3 attempts × 8 s + backoff sleeps + DNS per delivery ≈ **25.5 s/channel worst case, holding a worker slot**. The async task `deliver_monitor_event` exists and is never called.
- Migration risk: `notifications/0002` does `SET NOT NULL` + unique-index build on the hot `notificationevent` table (already applied — noted only for restored production DBs).

### 1.7 Portability baseline (Phase 13 inputs)

- **Good:** all Docker-DNS hostnames (`postgres`, `redis`, `backend`) are env-overridable defaults; ports overridable; frontend needs exactly one var (`NEXT_PUBLIC_API_URL`, **baked at build time**); no rewrites/proxy → browser→API direct (CORS via `CORS_ALLOWED_ORIGINS`); auth is Bearer + `sessionStorage` (no same-origin assumption); `/api/health/` reports postgres/redis/celery.
- **Gaps:** hardcoded `/app/storage` in `ops/views.py:79-85`, `artifacts.py:20`, default `artifact_storage.py:37`; gunicorn binds `0.0.0.0:8000` hardcoded (free-tier platforms inject **`$PORT`**); no SIGTERM handling anywhere; Docker default 10 s `stop_grace_period` vs 120 s monitor timeout + gunicorn 120 s; **frontend has no health route** (only `/`); no `SECURE_PROXY_SSL_HEADER` behind edge TLS; beat has no volume for its schedule file; no `mem_limit` anywhere.

### 1.8 Feature inventory (Phase 16 protection — 19 features mapped)

Browser-dependent (**[B]**): DOM, screenshot, price (all via `advanced_tasks.py` → `browser_fetcher.py`).
Chromium-free: HTTP monitoring, scheduling, change detection, notifications (email/Slack/Discord/webhook), weekly digest, workspaces/RBAC, API keys, OAuth, Stripe, compliance export, admin metrics/diagnostics, onboarding, artifact download, health endpoint, monitor CRUD, plan limits.
Explicitly *not* implemented (unchanged by this work): SMS/Telegram delivery.

---

## 2. Resource bottleneck analysis (ranked)

| # | Bottleneck | Evidence | Impact | Cost to fix |
|---|---|---|---|---|
| B1 | Chromium + Playwright baked into the single image used by API, worker **and** beat | `Dockerfile:16`, 1.05 GB layer [MEASURED] | 1.82 GB image on every service; ~58% dead weight on API/beat | S (image split) |
| B2 | `.venv-linux` (339 MB) shipped by `COPY . .` | `.dockerignore` misses `.venv-linux`; layer = 328 MB [MEASURED] | +328 MB on **every** backend image, every build | XS (one line) |
| B3 | Chromium launched **per check** (0.5–1 GB transient RAM [EST] + ~1–3 s startup) | `browser_fetcher.py:51-52` | Peak RAM ×N checks, check latency, OOM risk | M (lifecycle) |
| B4 | **No queue separation** — browser/HTTP/email/digest share one queue, 4 slots | 0 matches for routing; `ops/views.py:163` | Browser backlog **starves HTTP monitoring** (the product's core) | S |
| B5 | **No Celery time limits** — a wedged `browser.close()` or hung network call occupies a slot forever; 4 wedges stop *all* monitoring | no `task_time_limit` anywhere | Total monitoring outage from one bad page | S |
| B6 | **Notifications inline in check tasks** (≈25.5 s/channel worst case) | `tasks.py:67-76`; async task uncalled | Worker slots held by SMTP/webhook retries | S |
| B7 | Screenshot diff: 3 full-page RGBA buffers **inside a DB transaction** (864 MB at H=50k) | `screenshot_diff.py:13-25`, `advanced_tasks.py:163` | OOM → SIGKILL → **orphaned Chromium** (no reaper) + long row locks | S |
| B8 | Unbounded artifact growth via 4 orphan paths; no retention env, no byte logging, no dir prune | `advanced_tasks.py:193,214`; no delete signal | Disk fills → free-tier quota death | M |
| B9 | Result backend writes every result to the broker Redis DB; never read | no `AsyncResult`; `base.py:120` | Wasted Redis memory/CPU on the most constrained service | XS |
| B10 | Scheduler double-hop + unbounded fan-out (1+2N queries, 2N Redis ops/min) | `tasks.py:20-52,229` | Wasted broker+worker cycles at scale | S |
| B11 | Digest N+1 (100k queries) + monitor-list 2N + unindexed `checked_at`/`status` scans | `notifications/tasks.py:62-109`, `ops/views.py:147` | CPU/IO on DB slot during peak | M |
| B12 | Gunicorn ×3 + Next standalone always-on, no `CONN_MAX_AGE`, no graceful-shutdown config | settings audit | Baseline RAM floor; connection churn per request | S |

### Direct answers to the 13 audit questions

1. **RAM consumers:** browser worker (Chromium [EST 0.5–1 GB peak/check]) > gunicorn ×3 [EST 150–300 MB] > http worker prefork ×4 [EST 200–400 MB] > frontend Node [EST 40–120 MB] > postgres [EST 50–150 MB] > beat [EST 30–60 MB] > redis [EST 10–40 MB].
2. **CPU consumers:** screenshot pixel diff + PNG encode (spiky), Chromium render (spikic), BS4 parse of ≤10 MB, digest aggregates; frontend build (build-time only).
3. **Must be continuously running:** frontend, API, redis, postgres, beat (60 s tick). **http worker** should be always-on (product core). **Browser worker** must be running for advanced monitors but can be *scaled to zero* when no browser monitors exist — architecturally independent.
4. **Can be asynchronous:** notifications (currently inline — B6), artifact cleanup, digests, compliance export (already request-time but small-scale acceptable), all browser checks (already async).
5. **Movable to separate workers:** browser checks → browser worker; email/webhook dispatch → notifications queue.
6. **Playwright-only deps:** `playwright` (140 MB incl. Node driver), Chromium (658 MB on disk), `Pillow` (6.9 MB), `pixelmatch` (76 KB), plus Chromium apt deps. `bs4` is shared (HTTP normalizer uses it too).
7. **Unnecessary in prod:** `python-dotenv`, `django-anymail` (never imported); Chromium on API/beat; `.venv-linux` in the image; tests could be excluded but are kept deliberately so the prod image stays testable (they total ~1 MB).
8. **Oversized layers:** `playwright install` 1.05 GB (mis-ordered, uncleaned) + `COPY . .` 328 MB (venv leak) = **1.38 GB of the 1.82 GB image is avoidable on the API**.
9. **Independently deployable:** all 7 services — frontend (own build/`$PORT`), API (`$PORT`), http worker, browser worker, beat, postgres, redis. Only coupling is shared DB/Redis/broker + env config.
10. **Needs real disk:** postgres_data, redis_data, artifacts (named volume in prod, added by this plan), beat schedule (small), frontend build cache (build-time).
11. **Leak points:** SIGKILL/OOM mid-check (no reaper), `launch()` failure, `close()` hang, retry×5 amplification, orphaned artifact objects (4 paths), orphaned empty dirs.
12. **Concurrency today:** dev = CPU count (unbounded-ish), prod = 4 prefork shared by *everything*. Not appropriate: browser needs **1**, http wants 4, notifications want isolation.
13. **Queues today:** one (`celery`). **After: `celery_http`, `celery_browser`, `celery_notifications`.**

---

## 3. Proposed zero-cost architecture

```
Cloudflare (edge: DNS + TLS + CDN for frontend assets)
   │
   ├── frontend            Next.js standalone        port $PORT (3000)
   ├── backend-api         gunicorn (2 workers)      port $PORT (8000)   [NO Chromium, NO playwright]
   ├── celery-http-worker  prefork, Q=celery_http,celery_notifications   [NO Chromium]
   ├── celery-beat         scheduler only            [NO Chromium, NO playwright]
   ├── celery-browser-worker  prefork c=1, Q=celery_browser   [ONLY service with Chromium]
   ├── postgres            managed or container + volume
   └── redis               broker only (results disabled)
```

### Service matrix

| Service | Image target | Queues consumed | Concurrency | New env knobs (defaults) | Independent deploy |
|---|---|---|---|---|---|
| frontend | `frontend:production` | — | 1 Node proc | `PORT=3000`, `NEXT_PUBLIC_API_URL` (build-arg) | ✅ |
| backend-api | `backend:api` | — | `GUNICORN_WORKERS=2` [EST], `PORT=8000` | ✅ |
| celery-http-worker | `backend:api` | `celery_http` + `celery_notifications` | `HTTP_WORKER_CONCURRENCY=4`, `--prefetch-multiplier 4` | ✅ |
| celery-beat | `backend:api` | publishes only | 1 | beat schedule on volume/tmpfs | ✅ |
| celery-browser-worker | `backend:browser` | `celery_browser` | **`BROWSER_WORKER_CONCURRENCY=1`**, `--prefetch-multiplier 1`, `--max-tasks-per-child $BROWSER_RECYCLE_TASKS` | ✅ |
| postgres / redis | upstream | — | — | unchanged | ✅ |

### Key decisions (with rationale)

- **D1 — Two images, one multi-stage Dockerfile.** Stage `api` = base + `requirements.txt` (minus browser deps). Stage `browser` = `FROM api` + `requirements-browser.txt` (playwright/Pillow/pixelmatch) + `RUN playwright install --with-deps chromium` **placed before `COPY . .`** and followed by apt/`/root/.cache` cleanup, `PLAYWRIGHT_BROWSERS_PATH=/ms-playwright` (chowned to a non-root user). Fix `.dockerignore` (`.venv-linux`, `storage`, `celerybeat-schedule`, `.env`). Result: API image drops the 1.05 GB Chromium layer + 140 MB pip package + 328 MB venv → **[EST] ~310 MB vs 1.82 GB today** (re-measured after build); only one service carries ~1.5 GB [EST].
- **D2 — Three queues** exactly as scoped: `celery_http` (HTTP checks, dispatch, artifact cleanup), `celery_browser` (`run_advanced_monitor`), `celery_notifications` (digest + async email/webhook dispatch). Routing via `CELERY_TASK_ROUTES` by task name (no call-site churn for `.delay`, but the browser task's call sites get an explicit `queue=` too for clarity). Beat publishes; http worker consumes `celery_http,celery_notifications` (keeps process count at the free-tier minimum while preserving the ability to split later **without code changes**); browser worker consumes `celery_browser` only → **browser jobs can never starve HTTP jobs.**
- **D3 — Browser lifecycle: controlled single-browser-per-child, not a cross-process pool.** Playwright's sync API is greenlet-bound (safe only when one task at a time runs in the process that created it), so a shared pool across threads/processes would be a correctness hazard. Design: prefork, concurrency 1 → per-child singleton browser, **fresh incognito `new_context()` per check** (complete cookie/localStorage isolation between users/monitors), `context.close()` in `finally`, browser launched lazily with `--disable-dev-shm-usage`, recycled after `BROWSER_MAX_TASKS` jobs **or** RSS > `BROWSER_MAX_RSS_MB` (via `/proc/self/status` + child pids), auto-restart on `TargetClosedError`/crash with bounded attempts, `launch(timeout=…)` + `set_default_timeout` + `set_default_navigation_timeout`, hard/soft Celery time limits as the outer kill switch, `init: true` + `stop_grace_period: 180s` so orphans are reaped and in-flight checks can finish. A crash kills only the browser child, never the worker. `docs/BROWSER-WORKER.md` will document why a multi-context shared pool was rejected. *(If a "pool" is wanted later: multiple contexts on the same browser inside the single child is already the shape — N contexts, 1 browser.)*
- **D4 — SSRF parity for the browser engine (Phase 14).** Keep pre-navigation `validate_url`; add `page.route`/`context.route` interception validating **every request URL** (scheme, credentials, port, hostname blocklist, DNS→blocked-IP check with a 60 s per-host cache and a per-check validation cap) → this closes the redirect gap *and* the subresource gap; re-check the final URL after `goto`; fix the `parsed.port` `ValueError` bug in `fetcher.py:106` (→ `SecurityError`); add tests for IPv4-mapped IPv6, decimal IPs, `:99999`, redirect-to-private, subresource-to-metadata. Residual DNS-rebinding TOCTOU documented (needs an egress proxy to close fully). Auth, RBAC, API-key scopes, webhook encryption, Stripe verification, OAuth, Django prod security settings: untouched.
- **D5 — Per-mode resource policy (accuracy-preserving).** `screenshot` → **no blocking** (pixel-exact output required). `dom`/`price` → block images/media/fonts (keep HTML/CSS/JS/XHR so JS-rendered DOM and prices still work) via env `BROWSER_BLOCK_RESOURCES=images,media,fonts` (settable to `none` to disable). This is what makes DOM/price checks cheap without touching screenshot fidelity.
- **D6 — Every workload gets a time limit:** browser soft 180 / hard 240 s (`BROWSER_TASK_SOFT_TIME_LIMIT`/`BROWSER_TASK_TIME_LIMIT`, must exceed `monitor.timeout` ≤120 + launch + diff), http soft 150 / hard 180, notifications soft 90 / hard 120, digest & cleanup soft 600 / hard 900, scheduler soft 50 / hard 60. `task_acks_late=True` + `reject_on_worker_lost=True` + prefetch 1 (browser) so a killed browser worker **re-delivers instead of silently skipping the check** (today `next_check_at` advances pre-dispatch → crash = skipped interval).
- **D7 — Notifications off the critical path.** Check tasks call the existing-but-unused `deliver_monitor_event.delay(...)` routed to `celery_notifications`; `CELERY_TASK_ALWAYS_EAGER=True` in development settings keeps test behavior synchronous (tests currently rely on inline execution). Email/webhook work no longer holds an HTTP or browser slot. Worst-case webhook cost moves to its own queue with its own time limit.
- **D8 — Artifact retention, implemented as specified.** New `ARTIFACT_RETENTION_DAYS` env acts as a **cap**: `effective_days = min(plan history_days, ARTIFACT_RETENTION_DAYS)` when set. Cleanup task extended to: (1) existing DB-driven delete (objects before rows — already correct), (2) **orphan sweep** — walk storage keys, delete those whose `ChangeDiff`/`MonitorCheck` row is gone or stale, (3) prune empty dirs up to and including `artifacts/<monitor_id>/`, (4) `logger.info` reclaimed **bytes** + counts, (5) idempotent (safe re-run). Plus a `post_delete` signal on `Monitor` removing its artifact prefix (fixes orphan path 3), moving image-diff I/O **outside** `transaction.atomic()`, and only writing the HTML artifact when a diff will reference it or as the monitor's latest snapshot key (stops the 144k-files/day orphan). **No S3 requirement** — local named volume in prod compose (fixes the "no volume" High finding); S3 stays an optional backend.
- **D9 — DB/Celery efficiency where justified:** indexes migration (`MonitorCheck.checked_at`, `Subscription(status, updated_at, stripe_subscription_id, stripe_customer_id)`), single-subquery prefetch to kill the monitor-list 2N (response shape unchanged — **no pagination change** to protect the frontend), digest rewritten to one aggregate per monitor + `.iterator()` (email body byte-identical), scheduler caps per tick (`SCHEDULER_BATCH_SIZE`, default 500, reusing the dead `get_due_monitors`) and enqueues the target task **directly** (1 message/check instead of 2), `CELERY_TASK_IGNORE_RESULT=True` (verified: nothing reads results; diagnostics uses local `.apply()`), `CONN_MAX_AGE=60` in production.
- **D10 — Portability (Phase 13):** gunicorn binds `0.0.0.0:${PORT:-8000}` via entrypoint; frontend already honors `$PORT`; add `frontend/app/health/route.ts` → `200`; `ARTIFACT_LOCAL_ROOT` used consistently (removes hardcoded `/app/storage` from `ops/views.py` + `artifacts.py`); `init: true`, `stop_grace_period`, gunicorn `--graceful-timeout`; healthchecks for both workers (`celery inspect ping`); all hostnames/ports remain env-defaults. No provider chosen — docs describe *classes* of service only.

### Resource budget preview (to be finalized in `docs/RESOURCE-BUDGET.md` post-implementation)

| Component | RAM | Basis |
|---|---|---|
| frontend | [EST] 40–120 MB | single Node standalone proc |
| backend-api | [EST] 150–300 MB | gunicorn 2 workers + Django |
| celery-http-worker | [EST] 200–400 MB | 4 children, ≤10 MB body buffers |
| celery-beat | [EST] 30–60 MB | timer process |
| postgres | [EST] 50–150 MB | small-schema SaaS workload |
| redis | [EST] 10–40 MB | broker, results now disabled |
| **celery-browser-worker + Chromium** | **[EST] 700 MB–1.2 GB peak** | Chromium ~300–500 MB [EST] + driver + Python + 3-buffer screenshot transient at typical page heights (173 MB at 10k px [MEASURED math]) |
| **Total (all-in-one)** | **[EST] ~1.2–2.4 GB peak** | dominated by the browser worker |

- **Minimum deployment:** one Docker host with ≥2 GB for frontend+api+http-worker+beat+redis+postgres **at low monitor counts**, browser worker co-located only if total stays <2 GB — *not recommended*; safe minimum is a split: ~1 GB app slot + ~2 GB browser slot.
- **Recommended free-tier deployment:** frontend → static/edge or tiny container slot; API + http worker + beat + redis → one container slot (~1 GB); postgres → free managed DB (or container + volume); **browser worker → separate container slot with ≥1.5–2 GB** (concurrency 1).
- **Upgrade threshold:** browser worker RSS >80% of its quota for sustained periods, need for `BROWSER_WORKER_CONCURRENCY > 1` (≈>20–30 browser checks/interval), >~500 monitors (scheduler/DB), artifact volume nearing free-tier disk quota, or API p95 degraded by CPU saturation.

*(Honesty constraint per the brief: these are estimates until Phase 12 measurement. The architecture will not be declared "free-tier capable" in the docs unless the measured numbers support it.)*

---

## 4. Exact files to modify

### New files

| File | Purpose | Phase |
|---|---|---|
| `backend/requirements-browser.txt` | playwright, Pillow, pixelmatch | D1 |
| `backend/entrypoint.sh` | `$PORT`-aware gunicorn start (exec, signal-safe) | D10 |
| `backend/monitors/browser_pool.py` | per-child browser lifecycle: lazy start, context-per-check, recycle (jobs/RSS), crash restart, health stats | D3 |
| `backend/monitors/routing.py` | lazy task-import helpers (`enqueue_advanced_check`) so API/beat never import Playwright | D1 |
| `backend/monitors/migrations/0005_*.py` | index: `MonitorCheck(checked_at)` | D9 |
| `backend/billing/migrations/0003_*.py` | indexes: `Subscription(status, updated_at)`, `(stripe_subscription_id)`, `(stripe_customer_id)` | D9 |
| `backend/monitors/tests_browser_worker.py` | pool lifecycle, context isolation, recycle, restart, time-limit config, resource blocking, screenshot-mode no-blocking | D3/15 |
| `backend/monitors/tests_routing.py` | queue routing map, browser-never-on-http-queue, concurrency defaults | D2/15 |
| `backend/monitors/tests_ssrf_browser.py` | redirect-to-private, subresource-to-metadata, `:99999`, mapped-IPv6, decimal IP | D4/15 |
| `backend/monitors/tests_retention.py` (or extend `tests_artifacts.py`) | env cap, orphan sweep, empty-dir prune, byte logging, monitor-delete cleanup, idempotent re-run | D8/15 |
| `frontend/app/health/route.ts` | `GET /health` → 200 for platform probes | D10 |
| `docs/RESOURCE-BUDGET.md`, `docs/FREE-TIER-DEPLOYMENT.md`, `docs/BROWSER-WORKER.md` | mandated deliverables | final |
| `docs/OPTIMIZATION-PLAN.md` | this document | done |

### Modified files

| File | Change | Phase |
|---|---|---|
| `backend/.dockerignore` | add `.venv-linux`, `storage`, `celerybeat-schedule`, `.env`, `*.log` | B2 |
| `backend/Dockerfile` | multi-stage (`api` / `browser`), reorder Playwright layer before `COPY`, apt+cache cleanup, non-root + `PLAYWRIGHT_BROWSERS_PATH`, `$PORT` entrypoint, healthcheck | D1 |
| `frontend/Dockerfile` | minor: `npm ci` in dev stage, keep multi-stage | D1 |
| `backend/requirements.txt` | remove `python-dotenv`, `django-anymail`, move browser trio out | D1 |
| `backend/config/settings/base.py` | `CELERY_TASK_ROUTES/QUEUES`, `IGNORE_RESULT`, time limits, `acks_late`, `reject_on_worker_lost`, beat entries (digest → real `crontab`), `ARTIFACT_RETENTION_DAYS`, `SCHEDULER_BATCH_SIZE`, browser knobs | D2/D6/D8 |
| `backend/config/settings/development.py` | `CELERY_TASK_ALWAYS_EAGER=True` (keeps tests synchronous after D7) | D7 |
| `backend/config/settings/production.py` | `CONN_MAX_AGE=60`; optional `SECURE_PROXY_SSL_HEADER` (env-gated) | D9/D10 |
| `backend/monitors/tasks.py` | remove module-level `advanced_tasks` import (→ lazy via `routing.py`); scheduler batching + direct single-hop enqueue; cleanup: env cap, orphan sweep, dir prune, byte logging, `logger` | D1/D9/D8 |
| `backend/monitors/advanced_tasks.py` | use `browser_pool`; move image-diff/artifact I/O **outside** the transaction; guard `ValueError` (selector misses) into a recorded failed check; conditional HTML artifact write | D3/D8 |
| `backend/monitors/advanced_api.py` | lazy import of `run_advanced_monitor` (function-local) | D1 |
| `backend/monitors/views.py` | lazy import path clean; (deletion cleanup handled by signal) | D1/D8 |
| `backend/monitors/services/browser_fetcher.py` | pool-backed contexts, per-mode resource blocking, route-interception SSRF, post-nav URL check, all timeouts set, `--disable-dev-shm-usage`, deterministic close, recycle hooks | D3/D4/D5 |
| `backend/monitors/services/fetcher.py` | fix `parsed.port` `ValueError` → `SecurityError`; export shared subresource policy helper | D4 |
| `backend/monitors/services/screenshot_diff.py` | context-managed image loads (`.close()`), keep 3-buffer semantics (documented) or stream-safe compare; unchanged threshold math | D7/B7 |
| `backend/monitors/services/artifacts.py`, `backend/common/artifact_storage.py` | `list_keys()`, `delete_prefix()`, recursive empty-dir prune, `BASE_DIR` from env only | D8/D10 |
| `backend/monitors/models.py` | `post_delete` receiver wiring (in app config `ready()` if preferred) for artifact prefix cleanup | D8 |
| `backend/notifications/services.py` / `tasks.py` | check tasks dispatch via `deliver_monitor_event.delay`; digest → aggregate queries + `.iterator()`, same email output; add `logger` on swallowed failures | D7/D9 |
| `backend/ops/views.py` | diagnostics browser check import-guarded (`ImportError` → "not available in this image"); disk usage via `ARTIFACT_LOCAL_ROOT` | D1/D10 |
| `docker-compose.yml` (dev) | split workers (`celery-http-worker` on api target, new `celery-browser-worker` on browser target, both with `-Q`), env knobs | D2 |
| `docker-compose.prod.yml` | `celery-http-worker`, `celery-browser-worker` (c=1, `--max-tasks-per-child`, `--prefetch-multiplier 1`), healthchecks for workers, `stop_grace_period` (180 s browser), `init: true`, **artifact named volume**, beat schedule path, `$PORT` wiring, resource-limit examples | D1–D3/D8/D10 |
| `.env.example` | all new knobs documented (`BROWSER_WORKER_CONCURRENCY`, `BROWSER_MAX_TASKS`, `BROWSER_MAX_RSS_MB`, task time limits, `HTTP_WORKER_CONCURRENCY`, `ARTIFACT_RETENTION_DAYS`, `SCHEDULER_BATCH_SIZE`, `BROWSER_BLOCK_RESOURCES`, `SCREENSHOT_MAX_HEIGHT_PX`, `GUNICORN_WORKERS`, `PORT`, `CONN_MAX_AGE`) | all |
| `README.md`, `SYSTEM_DOCUMENTATION.md`, `INSTRUCTION.md` | topology, deploy procedure, healthchecks, verification numbers | final |

---

## 5. Migration plan (ordered; each step gated by verification)

| Step | Content | Depends on | Gate before proceeding |
|---|---|---|---|
| **A. Config-only** | Celery queues/routing/time limits/`ignore_result`/`acks_late`/prefetch; env knobs; `.dockerignore` fix; requirements cleanup | — | 122 backend tests green; `docker compose config` valid |
| **B. Import decoupling** | `routing.py` lazy imports; remove `tasks.py:192` module-level import; guard `ops/views.py` diagnostics | A | API boots in a container **without** playwright installed (`python -c "import config.wsgi"` + test run) |
| **C. Image & compose split** | multi-stage Dockerfile (`api`/`browser`), entrypoint `$PORT`, dev+prod compose services, healthchecks, `init`, stop-grace, artifact volume | B | both images build; `compose config` valid; API image size re-measured; stack boots; `/api/health/` 200 |
| **D. Browser engine** | `browser_pool.py`, `browser_fetcher` refactor (contexts, timeouts, blocking, route-SSRF), `fetcher.py` port fix, screenshot diff out of transaction | C | new browser tests green; full suite green; manual DOM/screenshot/price checks verified end-to-end |
| **E. Async notifications + scheduler + DB** | `deliver_monitor_event.delay` + eager test setting; scheduler batching/single-hop; digest aggregates; index migrations; monitor-list prefetch | A (independent of C/D, but sequenced here) | full suite green; migration applies cleanly; digest email output unchanged (test asserts body) |
| **F. Artifact retention** | env cap, orphan sweep, dir prune, byte logging, monitor-delete signal, conditional HTML artifact | C (needs volume) | retention tests green; repeat-run idempotency proven; disk reclaimed logged |
| **G. Verification & docs** | full backend suite, `tsc --noEmit`, `next build`, both Docker builds, `compose config` prod validation, `docker stats` measurement pass → write the three docs + final report | A–F | **all gates green** |

Rollback story: steps A/B/E are code-only (git revert); C/D/F are compose/Dockerfile (previous compose file restores service topology); migrations are additive indexes only (reverse-migratable).

---

## 6. Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Playwright sync API used from wrong greenlet/thread if someone later changes the pool | Med | High (corruption) | Concurrency 1 + prefork only; `--pool prefork` pinned in compose; documented prohibition in `docs/BROWSER-WORKER.md`; no threads/gevent |
| R2 | `acks_late` re-delivery after worker kill → duplicate `MonitorCheck` row (and a second notification, since dedupe is per-check) | Low | Low/Med | Duplicate check rows are harmless; notification dedupe covers same-check redelivery; document residual (new check row = new event) |
| R3 | Route interception changes page behavior or slows checks (DNS validation per subresource) | Med | Med | 60 s host cache + per-check cap; screenshot mode unblocked (accuracy); `BROWSER_BLOCK_RESOURCES=none` escape hatch; perf test in D |
| R4 | Blocking images/fonts in dom/price mode affects a JS site that renders text after image load | Low | Low | Env override per deployment; screenshots unaffected; documented trade-off |
| R5 | `ALWAYS_EAGER` in dev changes how retry/timing tests behave | Med | Med | Run full 122-test suite at step E gate; adjust only tests that assert broker-side behavior |
| R6 | API boots without playwright but some code path still imports it at runtime | Med | High (500s) | Step B gate = boot test in a playwright-free container; diagnostics `ImportError` guard; grep gate for module-level browser imports |
| R7 | Moving image-diff out of the transaction creates artifact/row skew | Low | Low | Orphan sweep (D8) deletes unreferenced objects; ordering keeps objects-before-rows invariant |
| R8 | Prod artifacts on a named volume survive rebuilds but not host loss | Med | Med | Documented; retention caps growth; S3 remains the documented upgrade path (not required now) |
| R9 | Beat schedule file resets intervals on restart | Med | Low | Schedule file on a small volume (or documented reset semantics) |
| R10 | Health endpoint flips to 503 if only some workers run | Med | Med | `/api/health/` needs ≥1 responsive worker (unchanged semantics); worker healthchecks added; docs state browser worker optional **only** if no browser monitors exist |
| R11 | Screenshot-mode accuracy drifts if any blocking leaks in | Low | High (core feature) | Explicit no-blocking assertion test for screenshot mode (Phase 15) |
| R12 | Frontend `NEXT_PUBLIC_API_URL` baked at build → free-tier rebuild-per-env friction | Certain | Low | Documented in `FREE-TIER-DEPLOYMENT.md` as a build-time contract (unchanged behavior) |
| R13 | New indexes lock tables on a restored large production DB | Low | Med | Additive, small tables at current scale; noted for restore-from-backup scenarios |

**Feature-preservation guard (Phase 16):** the 19-feature inventory in §1.8 is the regression checklist; every gate runs the full suite (122 tests + new browser/routing/SSRF/retention tests), `tsc --noEmit`, `next build`, both image builds, and `docker compose -f docker-compose.prod.yml config` validation.

---

*Prepared from measured image inspection and four read-only code audits. All RAM figures are estimates until the Phase 12 measurement pass; the plan deliberately makes no provider choices (Phase 13).*
