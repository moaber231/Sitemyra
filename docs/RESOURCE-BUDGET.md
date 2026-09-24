# Resource budget — measured numbers, method, and limits

All figures were collected on 2026-09-23 during Phase G of
`docs/OPTIMIZATION-PLAN.md`. Labels:

- **[M]** measured on this host (Docker Compose dev stack, WSL2/Linux,
  7.7 GiB VM visible to the engine, internet egress available).
- **[E]** estimated / reasoned from [M] inputs — not directly measured.
- **[P]** provider-dependent — cannot be known without picking a provider
  and measuring there.

CPU% is `docker stats` per-sample CPU over ~1 s windows (multi-core
percentages; 100 % = one core). Peaks are therefore **lower bounds** on
instantaneous CPU. Memory is container RSS as reported by Docker.

## 1. Image sizes (build artifacts)

| Image | Target | Size [M] | Contents |
|---|---|---|---|
| `apeiro-backend`, `apeiro-celery-http-worker`, `apeiro-celery-beat` | `api` | **289 MB** | Django + DRF + Pillow (reportlab dep) — **no** Playwright, **no** pixelmatch, **no** `/ms-playwright`, no chromium binary; uid 10001 |
| `apeiro-celery-browser-worker` | `browser` | **1.47 GB** | everything in `api` + playwright 1.63.0 + chromium-1243 + headless shell + ffmpeg + pixelmatch; uid 10001 |
| `apeiro-frontend` | dev/prod | **941 MB** | Next.js 15 (multi-stage) |
| *(before, stale)* `apeiro-celery-worker` | all-in-one | **1.82 GB** | pre-split image: API + workers + Chromium in one layer set |

Effect of the split: the container that serves API traffic dropped from
**1.82 GB → 289 MB** (−84 %) because Chromium now exists only in the
browser worker image.

## 2. Idle / steady state [M]

After the stack was up and quiescent (no checks in flight):

| Container | CPU | RSS |
|---|---|---|
| `backend` (runserver, dev) | ~4 % (autoreload/sampler noise) | 221–242 MiB |
| `celery-http-worker` (concurrency 4) | ~0.2 % | 279 → 306 MiB (post-load steady) |
| `celery-browser-worker`, **no browser yet** | ~0.1 % | **89 MiB** |
| `celery-browser-worker`, Chromium resident | ~0.1 % | 319–350 MiB |
| `celery-beat` | ~0 % | 75–82 MiB |
| `postgres` | ~0–0.8 % | 19.8–21.5 MiB |
| `redis` | ~0.5 % | 8 MiB |
| `frontend` (Next dev — prod is smaller) | ~0.1 % | 339–344 MiB |
| `minio` (optional S3 for artifacts, dev only) | ~0.2 % | 98–103 MiB |

Dev-stack idle total ≈ **1.1–1.3 GiB** with Chromium resident
(excluding MinIO) **[M]**; production gunicorn replaces `runserver` and
the frontend runs a standalone build (smaller), so the same order
applies **[E]**.

## 3. Loaded scenarios [M]

### API — `GET /api/monitors/` × 1500, concurrency 20 (JWT auth + Prefetch list)

| Container | Peak CPU | Peak RSS |
|---|---|---|
| backend | **131.5 %** | 243 MiB |
| postgres | **157.6 %** | 56 MiB (20 MiB idle) |
| redis | 4.1 % | 8 MiB |

### API — `GET /api/health/` × 15 sequential (pre-fix; §6 since resolved)

| Container | Peak CPU | Peak RSS |
|---|---|---|
| backend | 5.3 % | 242 MiB |
| redis | 4.1 % | 8 MiB |

Per-request cost ≈ **2.1–2.2 s** (dominated by the celery `inspect`
broadcast with `timeout=2`) **[M]**. After the §6 fix (2026-09-24) the
same probe costs **~17–20 ms** **[M]** — re-measured sequential peaks
are no longer meaningful (the check is now a sub-ms Redis key scan).

### HTTP worker — 40 checks against example.com (concurrency 4)

| Container | Peak CPU | Peak RSS |
|---|---|---|
| celery-http-worker | **30.5 %** | 306 MiB |
| postgres | 9.4 % | 28 MiB |

Checks completed at ~67 ms each (network-dependent) **[M]**.

### Browser worker — one check per scenario (concurrency 1)

| Scenario | Peak CPU | Peak RSS | Duration |
|---|---|---|---|
| DOM, books.toscrape.com (warm) | 22.6 % | 260 MiB | 2767 ms |
| Price, book detail page | 34.5 % | 309 MiB | 1725 ms |
| Screenshot, books.toscrape.com | 53.4 % | 291 MiB | 2507 ms |
| DOM, bbc.com/news (chatty; blocking on) | 182.7 % | 354 MiB | 2592 ms |
| **Screenshot, bbc.com/news (chatty; never blocked)** | **217.8 %** | **418 MiB** | 6479 ms |

The worst case measured is a full-page screenshot of a request-heavy
public page: **~2.2 cores peak, ~418 MiB container RSS** **[M]**.
Chatty-DOM with resource blocking is ~16 % cheaper on CPU and ~64 MiB
lighter than the same page unblocked — the value of blocking on
non-screenshot modes **[M]**.

## 4. Chromium lifecycle memory [M]

| Point | Chromium RSS | Processes |
|---|---|---|
| Fresh worker, before first check | 0 (browser not started — lazy) | 0 |
| After 5 checks (scenarios) | 327 MiB | 6 |
| After +1 check | 328 MiB | 6 |
| After +11 checks total | **328 MiB** | 6 |

Flat across repeated checks: fresh incognito context per check +
unconditional close means no per-check accumulation; recycling
(`BROWSER_MAX_TASKS=50`, `BROWSER_MAX_RSS_MB=1024`, Celery
`--max-tasks-per-child`) bounds the long run **[M for the flat
observation, E for long-horizon bounds]**.

## 5. Postgres / Redis connection & memory behavior [M]

- Idle Postgres connection count: **6** (background processes + a
  psql sample). No growth while idle over 25 s of 1 Hz sampling.
- Under the API burst with the health wedge present (§6), connections
  grew **one per wedged request** until `max_connections=100`
  (postgres default — the compose file does not override it) refused
  new clients. After isolating the wedge, the same stack returned to
  baseline with **no leak**. After the §6 fix, two back-to-back
  20-request health bursts left `pg_stat_activity` **flat at 7** —
  zero pinning **[M]**.
- Redis stays ~8 MiB regardless of scenario.

## 6. `/api/health/` celery check — root cause & resolution [M]

Reproduced and measured 2026-09-23 (pre-existing behavior, untouched by
the optimization mission); fixed 2026-09-24 as an isolated post-Phase-G
change.

### Root cause — one mechanism, three symptoms

The celery check ran `control.inspect(timeout=2).ping()` — a live broker
broadcast — on every probe:

1. **~2.1–2.2 s per single probe:** the reply drain always waits out the
   full `timeout=2`, even when workers answer in milliseconds.
2. **Concurrency wedge:** every thread shares one `app.control` → one
   kombu pidbox `Mailbox` (a `cached_property`) → one producer pool. A
   20-thread in-process repro with a `faulthandler` stack dump showed
   **3/20 completing at 40 s** (the racers) and **17 threads blocked in
   `kombu/resource.py queue.get()` with no timeout**, inside
   `pidbox.producer_or_acquire` during `_publish` — i.e. blocked *before*
   the 2 s reply timeout even applied. Over HTTP: **3× 200,
   17× timeout at 45 s**.
3. **DB connection exhaustion:** a wedged request never reaches
   `request_finished`, so its Django connection stays pinned — measured
   `pg_stat_activity` **7 → 24** (+17, exactly the 17 wedged requests).
   Repeated bursts head for Postgres `max_connections=100`
   (`sorry, too many clients already`).

### Resolution — Redis TTL-registry heartbeat

`backend/config/worker_heartbeat.py` (wired in `config/celery.py`):

- Each worker process writes `celery:worker-hb:<nodename>` with a TTL
  (`WORKER_HEARTBEAT_TTL_S`, default 15 s) every TTL/3 s from a daemon
  thread started on Celery's `worker_ready`; `worker_shutdown` stops it
  and deletes the key. A worker killed uncleanly drops out of the health
  response once the TTL lapses (≤ 15 s).
- `_check_celery` merely `SCAN`s that prefix (never `KEYS`) and preserves
  the response contract exactly: `ok` + `workers` / `degraded` +
  `"no workers responded"` / `error` + `error`. No broker round-trip, no
  reply drain, no shared pool, no Celery import on the health path.
- Worker names are identical to the old `inspect()` output
  (`celery@<container-id>`); beat still is not listed (as before).
- Auth/security unchanged; queue architecture untouched; no new
  dependencies (Redis client already in the API image).

### Before / after (same dev stack) [M]

| | Before | After |
|---|---|---|
| Sequential probe latency | 2.07 / 2.11 / 2.11 s | **0.021 / 0.016 / 0.017 s** |
| 20 concurrent probes | 3× 200, 17× timeout at 45 s (wall 45 s) | **20× 200, wall < 1 s** (0.08–0.17 s each) |
| `pg_stat_activity` after burst | 7 → **24** (pinned) | 7 → **7** (flat across two bursts) |
| Worker list in response | `celery@<id>` ×2 | same, from registry ×2 |

Regression tests: `backend/common/tests_health.py` (17 tests — response
shape, no-broadcast guard, 20-concurrent completion, connection-pinning
count, TTL semantics, heartbeat thread lifecycle, signal handlers).
Full suite: **220 tests passing**.

Related behavior left unchanged (by design): the admin-only ops
diagnostics endpoint (`ops/views.py`) still issues a *serial*
`control.inspect(timeout=3)` on an authenticated `POST` — same underlying
kombu behavior, but never per health probe and never under concurrency.

Test-author note: `django.test.client` intentionally disconnects
`close_old_connections` from `request_finished`
(`django/test/client.py`), so tests that spawn request threads must close
those threads' connections themselves (see `common/tests_health.py`);
production keeps the receiver connected (`CONN_MAX_AGE=0`) — verified
live (7 → 7 across 40 requests).

## 7. Sizing guidance [E] / [P]

For a single-stack deployment (API + HTTP worker + browser worker +
beat + Postgres + Redis + frontend):

- **RAM floor (idle)** ≈ 1.1–1.3 GiB measured **[M]**; add headroom for
  page-cache and burst ⇒ **~1.5–2 GiB comfortable floor [E]**.
- **RAM with a browser check in flight** adds the measured 418 MiB worst
  case ⇒ **~2–2.5 GiB for no-swap operation under mixed load [E]**.
- **CPU**: idle ≈ nothing; API bursts peak ~1.3 + 1.6 cores (API +
  Postgres) on this host **[M]**; a chatty screenshot peaks ~2.2 cores
  on the browser worker alone **[M]**. A 2-vCPU host runs everything but
  will queue work during simultaneous bursts **[E]**.
- **Disk**: images 289 MB + 1.47 GB + 941 MB (+ build cache, which can
  double this during image builds **[P]**); artifact growth is bounded by
  `ARTIFACT_RETENTION_DAYS` and plan history (7/30/90 d) — growth rate
  is usage-dependent **[P]**.
- **Egress**: each check downloads the page (chatty pages measured at
  multi-MB transfers implicitly via duration; exact bytes not
  instrumented **[not measured]**) — budget egress per check × checks
  per minute.

## 8. What was *not* measured

- Long-run (hours/days) memory drift of the API/worker processes.
- Production (gunicorn, prod compose) numbers — dev stack only; treat
  §2–§4 as representative, not exact, for prod **[E]**.
- Concurrent multi-check browser load (structurally impossible today:
  concurrency 1 by design).
- Exact per-check network bytes.
- Any specific hosting provider's free tier — see
  `docs/FREE-TIER-DEPLOYMENT.md`.
