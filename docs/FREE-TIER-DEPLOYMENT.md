# Free-tier deployment — honest status

**We do not claim this stack runs on any provider's free tier.** A claim
like that requires provider-specific measurements on that provider's
actual limits; we have not picked a provider and have not run the stack
there. This document records what we *can* stand behind, separates it
from what we cannot, and lists what a real free-tier verdict would need.

Labels used below:

- **[M]** measured on our dev host (Docker Compose, 2026-09-23) — see
  `docs/RESOURCE-BUDGET.md` for method.
- **[E]** estimated from [M] inputs.
- **[P]** provider-dependent — unknowable until a provider is chosen and
  measured there.

## 1. What is true today [M]

- The full stack (API, HTTP worker, browser worker, beat, Postgres,
  Redis, frontend) idles at roughly **1.1–1.3 GiB RSS total** with
  Chromium resident, ~**0 CPU** at idle.
- Image sizes: API **289 MB**, browser worker **1.47 GB**, frontend
  **941 MB**. The browser image is the expensive one — it is also the
  one you could choose *not* to deploy if you only need the 16
  Chromium-free features (but then `dom`/`price`/`screenshot` checks
  will queue forever — that degrades the product, so it is not a
  recommended configuration).
- Worst measured single check: full-page screenshot of a request-heavy
  page → **~2.2 CPU cores peak, ~418 MiB** browser-worker RSS.
- Chromium RSS stays **flat** across repeated checks (327 → 328 MiB over
  12 checks) — no slow leak observed in the measurement window.
- Postgres default `max_connections=100`; idle usage is 6. Concurrent
  `/api/health/` probes used to wedge its old celery check and pin one
  connection per wedged request; since the heartbeat fix that check is a
  sub-ms Redis scan (~20 ms end-to-end, concurrency-safe — measured,
  see `docs/RESOURCE-BUDGET.md` §6).

## 2. What makes a provider a candidate [P]

Before "free tier" can even be discussed, a provider must satisfy all of
these; each is provider-dependent and unverified:

| Requirement | Why | Typical free-tier failure mode |
|---|---|---|
| ≥ 2 GB RAM (comfortable: 2.5 GB) | Idle ~1.3 GiB + a 418 MiB browser check + page cache | 512 MB–1 GB instances OOM with Chromium resident |
| ≥ 2 vCPU (comfortable) | API burst peaked ~1.3 + 1.6 cores (API+Postgres); chatty screenshot ~2.2 cores | Throttled 0.5–1 vCPU → checks time out, page cache thrash |
| Persistent disk ≥ 5–10 GB | Images (2.7 GB combined) + build cache (can double that during builds) + Postgres + artifacts | Ephemeral/full disk → Postgres panic, image pull failures |
| Outbound egress generous | Every check downloads a page; chatty pages are multi-MB; 1 check/5 min × N monitors adds up | Free tiers with 10–100 GB/mo caps burn fast |
| Docker allowed, root/Egress on build | Building the 1.47 GB browser image needs RAM (≥ 2 GB) and time | Serverless/edge platforms cannot build or run Chromium |
| Long-lived containers | Celery workers must persist (stateful browser child, beat schedule) | FaaS/sandbox platforms kill idle workers, lose beat state |
| Self-hosted Postgres + Redis allowed | Stack requires both; no managed-free-tier assumption | Some free tiers only allow SQLite or cap connections < 100 |
| No per-request CPU throttling during builds | `playwright install chromium` is CPU/RAM heavy | Build-time OOM is the most common free-tier failure |

## 3. What we would need to measure for a real verdict

For a chosen provider P:

1. Deploy the **prod** compose (`docker-compose.prod.yml`) on P's free
   instance.
2. Record: idle RSS/CPU for 24 h, API burst numbers, one chatty
   screenshot check duration/CPU/RSS, Postgres `max_connections` headroom,
   disk fill rate over a week, egress consumed over a week.
3. Confirm: no OOM-kill events, no build-time OOM, browser worker recycles
   cleanly under P's kernel/`/dev/shm`.
4. Compute monthly egress at a realistic monitor count and compare to
   P's cap.
5. Only then — and only if every number fits inside P's limits with
   headroom — may we say "runs on P's free tier," with the measurements
   attached.

Until steps 1–5 are done for a specific provider, the honest answer to
"does this run on a free tier?" is: **not verified — likely only on free
tiers offering ≥ 2 GB RAM / ≥ 2 vCPU with Docker support; many popular
free tiers (512 MB–1 GB) will not run the browser worker.**

## 4. Cost-free dependencies (independent of provider) [M]

These were verified keyless in CI/dev and do not require paid accounts:

- **Stripe** — endpoints run in stub mode without `STRIPE_SECRET_KEY`
  (billing/demo flows work keyless).
- **SMTP** — dev uses the console email backend; alerts are not lost,just
  not delivered externally, until SMTP credentials are configured.
- **S3/MinIO** — artifacts default to the local named volume
  (`ARTIFACT_STORAGE=local`); S3 is optional.
- **OAuth (Google/GitHub)** — optional; without client credentials SSO
  simply fails closed (no bridge fallback).

No paid cloud dependency exists in the codebase by construction:
Postgres + Redis are self-hosted in compose, Chromium is bundled in the
browser image.

## 5. Recommendations if you must stay on a free tier

1. Pick a free tier that meets §2 (≥ 2 GB RAM, ≥ 2 vCPU, Docker, ≥ 5 GB
   disk). Anything smaller: run the API+HTTP-only subset **and accept** that
   `dom`/`price`/`screenshot` monitors will not execute — or don't launch
   those features to users.
2. Pre-build images elsewhere (or use a registry) to avoid build-time OOM;
   the browser image is the one that kills free builders.
3. Keep `--max-tasks-per-child`/`BROWSER_MAX_TASKS` at defaults (50) so
   Chromium RSS stays bounded on a small box; consider lowering
   `BROWSER_MAX_RSS_MB` to 768 on a 2 GB instance.
4. Set `ARTIFACT_RETENTION_DAYS` aggressively (e.g. 7) to bound disk.
5. `/api/health/` probes are concurrency-safe since the heartbeat fix
   (`docs/RESOURCE-BUDGET.md` §6) — no sequencing constraint.
6. Re-run the measurements **on that provider** (§3) before telling
   anyone it "works on free tier."
