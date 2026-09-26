# Deploy note — Phase 1 competitive intelligence

**Commit:** `faec447` · **Base:** `1bfe8c0` · **Status:** pushed to `origin/main`, **not yet deployed to production**

This is the handoff for whoever runs the deploy (INSTRUCTION.md §4). Every
step below is required; if one fails, stop and report rather than working
around it.

---

## 1. What is shipping

The URL-intelligence intake flow and product tracking. The user journey is
now: paste a competitor or product URL → see what Sitemyra understood and
discovered → click "Monitor everything" (or pick a recipe) → get an alert
that says what changed, why it might matter, and where the evidence is.

- New `intelligence` Django app and 5 tables.
- `/dashboard/monitors/new` rewritten as the intake flow. The previous
  name/interval/timeout form is preserved behind an "Advanced" disclosure.
- A new **Product** tab on the monitor detail page, shown only for monitors
  that track a product.
- New public homepage demo endpoint (unauthenticated, throttled).
- Homepage repositioned to "Know when your competitors move."

**Nothing existing was removed or renamed.** No existing test was modified.
The 221 pre-existing tests are unchanged; 138 new ones were added.

---

## 2. Before you pull

### 2.1 Database backup — REQUIRED

This release includes a migration, so the §4 backup step is not optional.

```sh
docker compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > backup_$(date +%F_%H%M).sql.gz
```

### 2.2 New environment variable — REQUIRED to add to the server's `.env`

One new variable. It has a working default, so the deploy will succeed
without it, but add it explicitly so the marketing demo rate is deliberate
rather than accidental.

```sh
# Rate limit for the unauthenticated homepage demo
# (POST /api/intelligence/public/analyze/). One view only; no other
# endpoint is throttled. DRF format: <n>/<period>.
PUBLIC_ANALYZE_RATE=12/hour
```

Place it next to `SCHEDULER_BATCH_SIZE`. Confirm afterwards:

```sh
grep -c PUBLIC_ANALYZE_RATE .env    # expect 1
```

Nothing else changed. No new secrets, no changed secret names, no new
services, no new ports, no new volumes, no compose changes.

---

## 3. Deploy

```sh
git status                                  # expect clean — local edits are a red flag
git log --oneline -3
git fetch
git diff --stat HEAD origin/main            # expect only faec447
git pull --ff-only origin main
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec backend python manage.py migrate
```

**Expected migrate output:** exactly one line —
`Applying intelligence.0001_initial... OK`. If you see anything else,
stop and report before continuing.

**Frontend rebuild note.** `NEXT_PUBLIC_API_URL` is baked at build time and
this release changes no frontend env vars, so a plain `build` is correct.
No `NEXT_PUBLIC_*` value changed in `.env.example`.

### Rollback, if verification fails

The migration is **reversible and non-destructive** — verified by applying
it, fingerprinting all 26 pre-existing tables (158 columns), rolling it
back, and confirming the schema was byte-identical:

```sh
git checkout 1bfe8c0
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec backend python manage.py migrate intelligence zero
```

`migrate intelligence zero` drops only the 5 `intelligence_*` tables. It
cannot touch monitor, check, user, billing or notification data, because
the migration creates those 5 tables and modifies nothing else.

---

## 4. Post-deploy checklist (INSTRUCTION.md §4)

- [ ] `/api/health/` returns `503` with **postgres ok, redis ok** and celery ok — or, if a worker heartbeat takes a few seconds to re-register, retry once. A `postgres`/`redis` failure is a real failure.
- [ ] All services `Up (healthy)` — `frontend`, `backend`, `celery-http-worker`, `celery-browser-worker`, `celery-beat`, `postgres`, `redis` (7/7)
- [ ] Frontend loads at the public URL; login works
- [ ] No errors in the last 5 minutes of `backend`, `celery-http-worker`, `celery-browser-worker` logs
- [ ] A monitor check has run (queue depths drain to 0: `exec redis redis-cli LLEN celery_http` / `celery_browser`)
- [ ] Migration applied cleanly: `exec backend python manage.py showmigrations intelligence` → `[X] 0001_initial`

### 4.1 New-endpoint smoke test

```sh
# Public demo endpoint (no account). Must NOT be 404 and must NOT be 429
# on a fresh server, and must not 500 on a real page.
curl -sS -X POST https://api.<your-domain>/api/intelligence/public/analyze/ \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"}' \
  | python3 -m json.tool | head -20
```

Expected: `product_detected: true`, a `price` in `facts`, a
`classification_rationale` string. That page publishes no structured data,
so this specifically exercises the heuristic path.

```sh
# Auth-required endpoints. Substitute a real JWT.
curl -sS https://api.<your-domain>/api/intelligence/recipes/ \
  -H "Authorization: Bearer $ACCESS" | python3 -m json.tool | head
```

Expected: 8 recipes (`pricing`, `product`, `features`, `marketing`, `seo`,
`hiring`, `ecommerce`, `everything`).

### 4.2 Full journey (the acceptance test)

1. Open `/dashboard/monitors/new`, paste a competitor product URL, click
   **Analyze**.
2. Confirm the result names the page kind, shows a price/availability card
   if a product was detected, and lists the discovered targets **with a
   reason each**.
3. Click **Monitor everything**.
4. Confirm the summary lists the created monitors, and — on Free — that any
   skipped page says *"Your 'free' plan allows 3 active URLs"* rather than
   showing an error.
5. Open the first monitor → the **Product** tab. Confirm the current state
   card shows a price and a source link, and that the timeline says
   *"No changes recorded yet"* (correct on a first observation — a
   brand-new watch must never alert "everything changed").
6. Force a check (**Test now**), wait one interval, and confirm a snapshot
   is stored. To see the change path end to end, monitor a page whose price
   you control, change the price, and wait for the next check.
7. Confirm the alert email/Slack message contains `PRODUCT INTELLIGENCE`,
   `WHAT CHANGED`, `WHY IT MAY MATTER`, `EVIDENCE`, the source URL and
   `rule:price`.

### 4.3 Worth eyeballing

- The **Product** tab must be **absent** on a monitor created through the
  manual form. A tab that appears and then errors is a regression.
- The homepage demo must work logged out. If it 429s immediately for a
  real visitor, `PUBLIC_ANALYZE_RATE` is too tight for the traffic.
- `/dashboard/monitors` and the existing monitor detail tabs must be
  unchanged.

---

## 5. Operational notes

**New beat entry:** `intelligence.tasks.expire_url_analyses` at 03:20 and
15:20 UTC. It deletes cached URL analyses older than 12 hours. It is
bounded by the cleanup time limits and idempotent.

**New storage:** 5 small tables. `UrlAnalysis` holds one JSON blob per
analysis and is pruned twice daily. `ProductSnapshot` and `ProductChange`
obey the plan's `history_days` via the existing daily retention task, which
was extended to prune them (always keeping each watch's newest snapshot).
Monitor disk as normal — these are far smaller than screenshot artifacts.

**Query cost:** one extra PK-indexed lookup per check, on the
`product_watch` one-to-one, and only for monitors that could have one. A
product watch adds no outbound request.

**Not enabled by this release (deliberately):** any AI/LLM call. Phase 3 of
`docs/INTELLIGENCE-ROADMAP.md` layers optional narration on top of the
stored change records. Nothing to configure now.

**Open security items** are tracked in `docs/SECURITY-REVIEW-TODO.md` under
"Competitive-intelligence surface". The one worth a decision before or
shortly after launch: the public demo endpoint performs a synchronous
outbound fetch from an anonymous request, bounded at 30 s and rate limited
per IP. If the API origin sees bot traffic, lower `PUBLIC_ANALYZE_RATE` or
put a concurrency limit on that view.

---

## 6. Definition-of-done state

Per INSTRUCTION.md §9:

- [x] Code merged to `main` with tests passing (359: 221 pre-existing + 138 new) and `npx tsc --noEmit` clean
- [x] Documentation updated (`SYSTEM_DOCUMENTATION.md` §3.6, `README.md`, `.env.example`, `docs/INTELLIGENCE-ROADMAP.md`, `INSTRUCTION.md`)
- [ ] **Deployed and the checklist in §4 reported** — needs the VPS agent
- [ ] **Verified in production and eyeballed by Mo** — needs the VPS agent + Mo
- [ ] **`PUBLIC_ANALYZE_RATE` added to the server's `.env`** — needs the VPS agent
