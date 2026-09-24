# Browser worker — architecture, guarantees, and residual risks

Owner doc for the dedicated Chromium worker introduced by the optimization
mission (`docs/OPTIMIZATION-PLAN.md`, Phases A–G). Everything here was
verified in-container; where a number is quoted it is **measured**, not
estimated (measurement method: `docker stats --no-stream`, dev compose
stack, 2026-09-23 — see `docs/RESOURCE-BUDGET.md`).

## 1. Why a separate worker

Only three of nineteen features need a DOM engine (`dom`, `price`,
`screenshot`). Chromium is by far the largest and most expensive
dependency in the stack, so it is isolated:

| Guarantee | How it is enforced |
|---|---|
| The API container has no Playwright/Chromium/pixelmatch | Multi-stage `backend/Dockerfile` target `api`; gate: `python -c "import config.wsgi"` with Playwright blocked by a `sys.meta_path` blocker |
| The HTTP worker never runs browser tasks | Queues are exact: `celery_http`, `celery_notifications`, `celery_browser`; routing is per-queue `Exchange` + `routing_key` in `monitors/routing.py`; HTTP worker consumes only `celery_http,celery_notifications` |
| Browser tasks never land on the HTTP queue | `monitors.advanced_tasks.run_advanced_monitor` → `celery_browser` (verified by name-based routing test; the API/beat never import `advanced_tasks` — they `send_task` by name) |
| Only the browser service imports Playwright | `CELERY_IMPORTS=monitors.advanced_tasks` is set **only** on the `celery-browser-worker` service env, never in the shared env file |

Image facts (measured): API image **289 MB** (no `/ms-playwright`, no
chromium binary, `import playwright` → `ModuleNotFoundError`); browser
image **1.47 GB** (playwright 1.63.0, `chromium-1243`,
`chromium_headless_shell-1243`, `ffmpeg-1011`, pixelmatch). Both run as
uid **10001** (non-root) with an explicit `PLAYWRIGHT_BROWSERS_PATH=/ms-playwright`.

## 2. Celery process model

- Service command: `celery -A config worker -Q celery_browser
  --concurrency=1 --prefetch-multiplier=1 --max-tasks-per-child=50`
  (knobs: `BROWSER_WORKER_CONCURRENCY` is pinned to 1 in prod,
  `BROWSER_MAX_TASKS_PER_CHILD` default 50).
- Prefork pool, **concurrency 1, prefetch 1**: at most one check is in
  flight per container; a task is only dispatched when the child is free.
- Task limits (env-driven, `config/settings/base.py`): soft **180 s** /
  hard **240 s** (`CELERY_BROWSER_TASK_SOFT_TIME_LIMIT`,
  `CELERY_BROWSER_TASK_TIME_LIMIT`). The hard limit is the kill switch
  for anything Playwright cannot bound on its own.
- `acks_late` + `reject_on_worker_lost`: a killed child re-queues the
  task instead of losing it. `CELERY_TASK_IGNORE_RESULT` keeps result
  traffic out of Redis.
- Compose: `init: true`, `stop_grace_period: 60s`, healthcheck, and the
  shared `artifact_data` named volume (prod) for screenshot writes.

## 3. Browser lifecycle (`monitors/services/browser_pool.py`)

- **One browser per prefork child**, started **lazily** on the first
  check that needs it (a fresh worker idles at ~89 MB container RSS with
  zero Chromium processes — measured).
- **Fresh incognito `BrowserContext` per check** (1440×900), closed
  unconditionally in a `finally`. Cookies/localStorage/sessionStorage
  are never shared between checks, monitors, or users.
- **Recycle** between checks by job count (`BROWSER_MAX_TASKS`, default
  50) and optionally by process-tree RSS (`BROWSER_MAX_RSS_MB`, default
  1024; `0` disables). RSS is summed from `/proc/<pid>/statm` for the
  whole Chromium tree; if `/proc` is unreadable the RSS recycle is
  **skipped with one warning** (fail-safe: task-count recycling and the
  Celery hard limit still bound the browser) — it never fails a check.
- **Crash auto-restart**: `is_connected()` is checked at the start of
  each check; a dead browser is relaunched transparently. A crash
  mid-check tears the browser down immediately so nothing stale survives.
- Launch args always include `--disable-dev-shm-usage` (Chromium writes
  to `/tmp`; Docker caps `/dev/shm` at 64 MB — verified in-container).

### 3.1 The driver thread (Phase G live discovery — read this before changing the pool)

**Symptom found by the first live end-to-end check:** the browser fetch
succeeded, then *every* Django query in the task raised
`SynchronousOnlyOperation('You cannot call this from an async context…')`
— the `MonitorCheck` row was never written and Celery logged an
unexpected error.

**Root cause (verified with an in-container probe):** Playwright's *sync*
API parks an asyncio event loop as **running** in the thread that calls
`sync_playwright().start()`. The registry entry is only cleared by
`stop()`:

```
0-before        -> no running loop
1-after-start   -> LOOP RUNNING
… goto/content/ctx-close/browser-close … -> LOOP RUNNING
6-after-stop    -> no running loop
```

The pool deliberately keeps the driver alive between checks (that is the
whole point of reuse), so the loop stays "running" in that thread for the
child's lifetime — and Django refuses sync ORM access anywhere it sees a
running loop. Every check does its DB work *after* the browser returns.

**Fix (now structural, in `BrowserPool.run`):** all Playwright work runs
on one dedicated `ThreadPoolExecutor(max_workers=1,
thread_name_prefix="browser-driver")` thread; the Celery main thread does
all DB work and never enters Playwright.

- `fetch_with_browser` wraps its entire browser section (recycle →
  context → navigation → reads → screenshot) in `pool.run(_browser_work)`;
  URL validation stays on the main thread *before* a browser exists.
- `max_workers=1` gives both required properties at once: one persistent
  thread for the driver's whole lifetime (Playwright's greenlet/driver
  affinity) and naturally serialized checks (worker concurrency is 1
  anyway).
- `pool.shutdown()` stops the driver *on its own thread*, then retires
  the thread.
- Regression tests: `monitors/tests_browser_worker.py::BrowserDriverThreadTests`
  (dedicated thread, exception propagation, a parked loop on the driver
  thread never reaching the main thread's ORM, and
  `fetch_with_browser` routing everything through `pool.run`).

## 4. Timeouts and wait strategy

Every Playwright operation is explicitly bounded — no operation may
block until the Celery hard limit:

| Budget | Knob | Default |
|---|---|---|
| Navigation | monitor's `timeout` field × 1000 ms (min 1000) | per-monitor (≤30 s plan cap) |
| Page operations (evaluate/screenshot/CDP) | `BROWSER_PAGE_OP_TIMEOUT_MS` | 30000 |
| Browser launch | `BROWSER_LAUNCH_TIMEOUT_MS` | 30000 |
| Idle settle (below) | `BROWSER_IDLE_SETTLE_MS` | 3000 |
| Whole task | `CELERY_BROWSER_TASK_SOFT_TIME_LIMIT` / `CELERY_BROWSER_TASK_TIME_LIMIT` | 180 / 240 s |

**Wait strategy — `wait_until="load"` plus a bounded best-effort
networkidle settle, never blind `networkidle`.** Reasoning: `networkidle`
is unbounded on pages with long-polling, analytics beacons, or streaming
— Chromium may never reach it and the check would hang until the task
limit on every run. `load` has a hard browser-side bound; after it we
spend *at most* `BROWSER_IDLE_SETTLE_MS` waiting for network quiescence,
which captures most SPA hydration without ever risking an unbounded wait.

## 5. SSRF for the browser (fail-closed)

`validate_url` runs on the main thread **before any browser starts**:
scheme must be http/https, no credentials, ports only 80/443 (out-of-range
ports like `:99999` raise `SecurityError`, never a raw `ValueError`), no
loopback/private/link-local/multicast/reserved IPs (including
IPv4-mapped-IPv6 like `::ffff:127.0.0.1` and decimal/octal IPv4 forms),
no cloud-metadata hosts (`169.254.169.254`, `metadata.google.internal`, …).

**Every request the page makes is re-validated**, not just the main URL:

- Interception is installed on the **CDP `Fetch` domain** for the whole
  context, before the first navigation. `context.route()` does **not**
  fire for HTTP-3xx redirect hop targets (upstream
  `microsoft/playwright#34994`, verified in-container) — CDP does.
- Each intercepted URL (main frame, every subresource, every redirect
  hop) is statically validated and, for hostnames, DNS-resolved and
  IP-checked, with an in-check DNS cache (`BROWSER_DNS_CACHE_TTL_S=60`)
  and a hard lookup budget (`BROWSER_MAX_DNS_LOOKUPS=200`; `0` fails
  closed). Blocked requests are **aborted**, not merely hidden.
- The **final URL after redirects is re-validated** before content is read.
- Counters (`ssrf_blocked`, `cost_blocked`) are recorded per check.

### Residual risks (documented, not fixed — fixing them would weaken nothing but is not free)

1. **WebSocket handshakes bypass `Fetch` interception** (CDP does not
   pause them). A page could open a WS to a private host. Mitigation
   today: the initial page and all HTTP subresources are validated, and
   monitors run untrusted-page content only in this sandboxed worker with
   no cloud metadata access from the container network policy we control.
   Honest status: **open residual**.
2. **DNS-rebinding TOCTOU**: we resolve and validate an IP, then the
   browser resolves the same name again for the actual connection; a
   fast-rebinding DNS answer could differ between the two lookups.
   Honest status: **open residual**, inherent to validate-then-connect
   without a pinning proxy. Bounding it needs a local DNS-pinning proxy
   (future work).
3. The SSRF policy is **fail-closed**: an unreadable DNS result or
   exhausted budget blocks the request rather than allowing it.

## 6. Resource blocking

- **Screenshot mode never blocks anything** — hard requirement, enforced
  at the policy level and covered by
  `test_screenshot_mode_never_blocks_any_resource` (a hostile
  `BROWSER_BLOCK_RESOURCES=images,media,fonts` still blocks nothing).
  Blocking would change what the screenshot shows; accuracy wins.
- `dom` and `price` block **images, media, fonts only** (HTML/CSS/JS/XHR
  always load so the DOM stays correct).
- Env override: `BROWSER_BLOCK_RESOURCES` — comma list of
  `images,media,fonts,scripts,xhr,styles`; `none` disables all blocking;
  unknown values are ignored with a warning; values are clamped to the
  safe set per mode.
- Screenshot cap: `SCREENSHOT_MAX_HEIGHT_PX` (default `0` = no cap).
  When exceeded the check **fails explicitly with a recorded error** —
  it never silently truncates.

## 7. Errors, artifacts, transactions

- Known `ValueError` sources (invalid port strings, DOM selector
  mismatch, price extraction failure, screenshot height overflow) are
  caught and turned into **recorded monitor failures**
  (`_record_advanced_failure`) — never an unhandled Celery exception.
  Verified live: selector mismatch and HTTP-404 attempts each produced a
  clean recorded-failure row.
- Screenshot/image and diff I/O happen **outside** any
  `transaction.atomic()` (object writes commit first, then DB rows; the
  two atomic blocks in `advanced_tasks.py` contain no file I/O), so a
  rolled-back transaction can never leave a dangling DB pointer to a
  half-written file — at worst an orphan object, which the retention
  sweep removes.
- Pillow resources are closed after use.

## 8. Measured resource profile (dev compose, this host)

| Scenario (single check) | Browser-worker peak CPU | Browser-worker peak RSS | Check duration |
|---|---|---|---|
| Idle, no Chromium yet | ~0.1 % | 89 MiB (container) | — |
| DOM, books.toscrape.com (warm) | 22.6 % | 260 MiB | 2767 ms |
| Price, book detail page | 34.5 % | 309 MiB | 1725 ms |
| Screenshot, books.toscrape.com | 53.4 % | 291 MiB | 2507 ms |
| DOM, bbc.com/news (chatty, blocking on) | 182.7 % | 354 MiB | 2592 ms |
| Screenshot, bbc.com/news (chatty, never blocked) | 217.8 % | 418 MiB | 6479 ms |

Chromium RSS progression (recycling working): **0** before the first
check → **327 MiB / 6 processes** after 5 checks → **328 MiB** after
+1 → **328 MiB** after +11 more (flat — fresh contexts close; recycle
by count/RSS keeps growth bounded). Steady container RSS with Chromium
resident: ~320–350 MiB.

Note: peaks are per-`docker stats` sample (~1 s window), i.e. **lower
bounds** on instantaneous CPU.

## 9. Operational notes

- **`/api/health/` is safe to probe concurrently:** its celery check
  reads a Redis worker-heartbeat registry (`config/worker_heartbeat.py`)
  instead of the old `control.inspect()` broadcast, which wedged under
  concurrency (measured 3/20 completing at 40 s, one pinned Postgres
  connection per wedged request). After the fix: ~20 ms per probe,
  20 concurrent probes all answered < 1 s, `pg_stat_activity` flat.
  See `docs/RESOURCE-BUDGET.md` §6.
- Queue depth sanity:
  `docker compose exec redis redis-cli LLEN celery_browser`.
- The dev stack runs workers against `config.settings.development`
  (eager notifications); production never sets `CELERY_TASK_ALWAYS_EAGER`.
- Tests: `monitors/tests_browser_worker.py` (60 tests — SSRF matrix,
  blocking matrix, lifecycle/recycle/crash fakes, driver-thread
  regressions, error-recording, and real-Chromium integration tests that
  auto-skip where Chromium is absent).

## 10. Environment knobs (browser-related)

| Knob | Default | Meaning |
|---|---|---|
| `BROWSER_MAX_TASKS` | 50 | Browser recycle after N checks (per child) |
| `BROWSER_MAX_TASKS_PER_CHILD` | 50 | Celery child process recycle (`--max-tasks-per-child`) |
| `BROWSER_MAX_RSS_MB` | 1024 | Recycle when Chromium tree RSS exceeds this; `0` disables; skip+warn if `/proc` unreadable |
| `BROWSER_LAUNCH_TIMEOUT_MS` | 30000 | Chromium launch budget |
| `BROWSER_PAGE_OP_TIMEOUT_MS` | 30000 | In-page operation budget |
| `BROWSER_IDLE_SETTLE_MS` | 3000 | Max extra wait for network quiescence after `load` |
| `BROWSER_BLOCK_RESOURCES` | `images,media,fonts` | dom/price blocking set; `none` disables; screenshot ignores it |
| `BROWSER_MAX_DNS_LOOKUPS` | 200 | Per-check DNS budget, fail-closed |
| `BROWSER_DNS_CACHE_TTL_S` | 60 | Per-check DNS cache TTL |
| `SCREENSHOT_MAX_HEIGHT_PX` | 0 (no cap) | Overflow → explicit recorded failure |
| `CELERY_BROWSER_TASK_SOFT_TIME_LIMIT` / `_TIME_LIMIT` | 180 / 240 | Celery soft/hard task kill |
| `BROWSER_WORKER_CONCURRENCY` | 1 | Prefork children (keep 1) |
