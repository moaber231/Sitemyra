# Sitemyra — Competitive Intelligence Roadmap

**Status:** PLAN + Phase 1 implemented.
**Scope:** evolve Sitemyra from "tell me when a webpage changes" into
"give me a URL and continuously understand what that business is doing".
**Basis:** read-only audit of the repository (monitoring engine, diff
engines, models, auth, billing, alerts, frontend) — see §0 for what already
exists and what does not.

**Design rules that apply to every phase**

1. **Evidence before interpretation.** Every change record carries source
   URL, timestamp, before, after and the raw snippet that produced the
   value. No feature may ship that cannot show its evidence.
2. **No invented scores.** Descriptive states only ("Pricing changed",
   "No significant change detected"). Relevance numbers in Phase 1 are a
   documented *ranking heuristic* for link ordering, never a business or
   health score.
3. **Reuse the engine, do not fork it.** All fetching goes through
   `monitors.services.fetcher` (SSRF validation) or
   `monitors.services.browser_fetcher`. All scheduling goes through the
   existing `Monitor` / `next_check_at` fan-out. New capabilities are
   derived data attached to an existing `Monitor`, never a second crawler.
4. **Public pages only.** No login flows, no paywall bypass, no private
   APIs, no credential capture. Documented in `docs/SECURITY-REVIEW-TODO.md`.
5. **Graceful when partial.** Every new endpoint degrades to a truthful
   "not detected" rather than a guess.

---

## 0. Audit — what already exists (reused as-is)

| Capability | Where | Reused for |
|---|---|---|
| SSRF-hardened HTTP fetch (DNS resolve, per-hop revalidation, 10 MiB cap, redirect limit) | `monitors/services/fetcher.py` | every Phase 1 fetch |
| Browser fetch with CDP request interception, per-check context, RSS/task recycling | `monitors/services/browser_fetcher.py`, `browser_pool.py` | Phase 1 visual recipes (unchanged) |
| Content normalization + SHA-256 hash change detection | `monitors/services/normalizer.py`, `change_detector.py` | content signals |
| DOM text diff | `monitors/services/dom_diff.py` | feature/content signals |
| Visual pixel diff + artifact keys (local/S3) | `monitors/services/screenshot_diff.py`, `common/artifact_storage.py` | evidence screenshots |
| Price extraction (single CSS selector) | `monitors/services/price_extractor.py` | kept as-is; superseded by structured extraction below |
| `Monitor` / `MonitorCheck` / `ChangeDiff` / `PricePoint` | `monitors/models.py` | the substrate; unchanged |
| Scheduler fan-out + queue routing by name | `monitors/services/scheduler.py`, `routing.py`, `config/settings/base.py` | new work rides the existing 60 s tick |
| Artifact retention sweep | `monitors/tasks.py::cleanup_expired_artifacts` | extended to product history |
| Notification dispatch with per-channel failure isolation | `notifications/services.py::dispatch_monitor_event` | intelligence alerts reuse the same fan-out |
| Slack / Discord / generic webhook channels, encrypted at rest | `notifications/models.py` | Phase 1 alerting |
| Plan limits (`max_monitors`, `min_interval_seconds`, `max_alert_channels`, `history_days`) | `billing/models.py` | Phase 1 activation respects them |
| Workspace RBAC (`owner`/`admin`/`viewer`) | `workspaces/permissions.py` | Phase 5 agency |
| Developer API keys (`apeiro_…`, SHA-256, hashed) | `accounts/api_key_auth.py` | exports, API |
| Compliance CSV/PDF export | `monitors/views.py::compliance_export` | Phase 4 report template |

**What does not exist (confirmed by exhaustive grep):** JSON-LD /
schema.org / OpenGraph / microdata extraction (the normalizer *deletes*
`<script>` before anything can read it), any product or competitor entity,
any LLM/AI integration or API key, any organization/agency entity, any
paginated feed, any digest schedule preference, any market-signal model.
These are all greenfield and are introduced by the phases below.

**Known technical constraints carried into the plan**

- The API image has **no Playwright** (`monitors/advanced_tasks` is imported
  only by the browser worker via `CELERY_IMPORTS`). New code must never
  import it from `monitors/tasks.py` or `config/urls.py`.
- `AdvancedMonitorConfig.mode != http` routes to `celery_browser` at
  concurrency 1. Phase 1 therefore creates **only `http` monitors** and
  does structured extraction from the bytes the HTTP worker already
  downloaded — zero extra requests, zero browser cost.
- Tests run under `config.settings.development` with
  `CELERY_TASK_ALWAYS_EAGER = True`, so `.delay()` executes inline. A
  Phase 1 capture hook inside `check_monitor` therefore runs inside the
  existing monitor tests; it must be wrapped so it can never fail a check.
- `workspaces/` has no test file; Phase 5 adds the first one.

---

## PHASE 1 — URL onboarding and Product Watch  ✅ implemented

**Goal.** A user pastes one URL and immediately understands the page, sees
what Sitemyra found, and starts monitoring with one click. A tracked
product page produces field-level price/availability/variant history with
an explainable alert.

**User story.** *"I paste `https://competitor.com/products/pro-x`. Sitemyra
tells me it is a product page, shows me the current price, availability and
rating, finds 11 more pages worth watching, and starts monitoring all of it
in one click. When the price moves I get a message that says what changed,
why it might matter, and links to the source."*

**Database changes** (new app `intelligence`, migration `0001_initial`)

- `UrlAnalysis` — cached, per-user analysis of a submitted URL
  (`user`, `url`, `normalized_url`, `status`, `page_kind`, `facts` JSON,
  `fetched_at`, `status_code`, `response_time_ms`, `error`, `expires_at`).
  Caching exists so re-analysing the same URL costs no request.
- `DiscoveredTarget` — one monitoring suggestion
  (`analysis`, `url`, `kind`, `label`, `why`, `confidence`, `relevance`,
  `is_product`).
- `ProductWatch` — first-class product tracking, `OneToOne` to `Monitor`
  (`name`, `brand`, `currency`, `first_seen_at`, `last_seen_at`).
  Cascades with the monitor; no orphan cleanup needed.
- `ProductSnapshot` — the observed product state for one check
  (`product_watch`, `monitor_check`, `captured_at`, `name`, `brand`, `sku`,
  `price`, `list_price`, `currency`, `availability`, `rating`,
  `review_count`, `description`, `badges`/`variants`/`images`/`bundles`/
  `specs`/`shipping` JSON, `source_url`, `evidence` JSON, `extraction`
  JSON, `changed_fields` JSON).
- `ProductChange` — the timeline row
  (`product_watch`, `previous_snapshot`, `current_snapshot`, `monitor_check`,
  `field`, `label`, `before`, `after`, `severity`, `category`, `evidence`
  JSON, `created_at`).

No existing model is altered. No existing column changes type. Migrations
are additive and reversible.

**Backend changes**

- `intelligence/services/page_facts.py` — **pure** HTML → `PageFacts`.
  Reads JSON-LD (`Product`, `Offer`, `AggregateOffer`, `aggregateRating`,
  `additionalProperty`, `hasVariant`, `shippingDetails`, `@graph` and array
  wrappers), microdata (`itemtype`/`itemprop`), OpenGraph
  (`og:*`, `product:price:*`) and a widened heuristic price reader
  (was-price/now-price pairs, `data-*` attributes, class signals). Every
  field records `method` + the raw text that produced it. No network, no
  DB — fully unit-testable.
- `intelligence/services/classify.py` — **pure** page classification
  (product / pricing / features / variants / reviews / faq / docs /
  changelog / blog / careers / promotions / homepage / other) from URL
  shape, JSON-LD `@type`, OpenGraph type and price presence, plus
  same-origin link discovery with a per-kind relevance heuristic and a
  "why this matters" rationale built only from observable facts.
- `intelligence/services/product_diff.py` — **pure** snapshot→snapshot
  field diff with deterministic severity (`informational` / `minor` /
  `important` / `critical`) and a structured explanation
  (what changed / why it may matter / what to check / basis / confidence)
  that names the rule that fired.
- `intelligence/services/recipes.py` — recipe registry (pricing, product,
  features, marketing, seo, hiring, ecommerce, everything) → target kinds,
  interval and product-watch flag.
- `intelligence/services/analysis.py` — orchestrates fetch → extract →
  classify → persist; the only module that touches the network.
- `intelligence/services/product_capture.py` — called from
  `monitors/tasks.py::check_monitor` with the bytes the HTTP worker already
  downloaded. Wrapped in `try/except` at the call site so a capture bug can
  never fail or delay a check.
- `monitors/tasks.py` — one guarded call to the capture hook; `_notify`
  now also fires when product fields changed but the page hash did not.
- `monitors/tasks.py::cleanup_expired_artifacts` — also prunes
  `ProductSnapshot` / `ProductChange` past the plan's history window.
- `notifications/services.py::_build_subject_message` — prepends the top
  product changes to the alert body when a product watch exists. Purely
  additive: monitors without a product watch produce the byte-identical
  message as before.
- `config/settings/base.py` + `INTALLED_APPS` + new beat entry
  (`intelligence.tasks.expire_url_analyses`, daily).
- `config/urls.py` — mounts `/api/intelligence/`.

**Frontend changes**

- `lib/api/intelligence.ts` — typed client, modern style (token read from
  `sessionStorage` by `apiFetch`, no token argument).
- `app/dashboard/monitors/new/page.tsx` — rewritten as the paste-a-URL
  flow: input → analyse → "We found N things worth monitoring" → recipe
  chips → target checklist → **Monitor everything** / **Customize**.
- `components/intelligence/manual-monitor-form.tsx` — the previous manual
  form, extracted verbatim and kept behind an "Advanced" disclosure, so no
  existing capability is lost.
- `components/intelligence/analysis-result.tsx`,
  `components/intelligence/target-checklist.tsx`,
  `components/intelligence/recipe-picker.tsx`,
  `components/intelligence/product-watch-panel.tsx`,
  `components/intelligence/change-explanation.tsx`,
  `components/intelligence/facts-grid.tsx`.
- `app/dashboard/monitors/[id]/page.tsx` — a fifth **Product** tab that
  appears only when the monitor has a product watch: current snapshot,
  field-change timeline, evidence links, severity badges.
- `app/page.tsx` — headline becomes "Know when your competitors move",
  primary CTA becomes "Paste a competitor or product URL", and the demo
  block runs a real analysis through the public endpoint.

**API changes** (all new, none removed)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/intelligence/analyze/` | user | analyse a URL, cache, return facts + targets |
| POST | `/api/intelligence/public/analyze/` | none (scoped throttle) | homepage demo; redacted, never persisted |
| POST | `/api/intelligence/activate/` | user | create monitors from selected targets / recipe |
| POST | `/api/intelligence/quick-monitor/` | user | Feature 7 one-shot: analyse + activate |
| GET | `/api/intelligence/recipes/` | user | recipe catalogue |
| GET | `/api/intelligence/product-watches/` | user | list product watches |
| GET | `/api/intelligence/product-watches/{id}/` | user | watch + current snapshot |
| GET | `/api/intelligence/product-watches/{id}/timeline/` | user | field-change timeline |
| GET | `/api/intelligence/monitors/{id}/product/` | user | product state for a monitor (404 when none) |

**Tests** — `intelligence/tests_page_facts.py`, `tests_classify.py`,
`tests_product_diff.py`, `tests_api.py`, `tests_capture.py` (≈70 cases,
no network: fixtures + mocked `fetch_url`).

- extractor: JSON-LD product/offer/aggregateOffer/rating/variants/specs,
  malformed JSON-LD, `@graph`, microdata, OpenGraph, was/now price pairs,
  EU vs US decimals, currency inference, missing-everything page
- classifier: each page kind, cross-origin links rejected, cart/login/
  privacy paths excluded, dedupe, cap, relevance ordering monotonic
- diff: price up/down thresholds, discount computation, availability
  transitions, variant add/remove, review-count drop, no-change
- API: auth required, 404 (never 403) for another tenant's analysis or
  product watch, viewer cannot activate, plan limit clamping, interval
  clamped to plan minimum, SSRF URL rejected, throttle on the public
  endpoint
- capture: snapshot written on first check, changes on second, no change
  when identical, capture failure never breaks `check_monitor`

**Potential failure modes**

| Failure | Handling |
|---|---|
| JS-rendered storefront, no structured data | report `product_detected: false` with the reason; the URL is still monitorable as a content page. Never guess. |
| Site blocks the crawler / 403 | analysis returns `status: failed` with the HTTP code; the user is told plainly and offered the manual monitor. |
| Extremely large page | 10 MiB fetcher cap and a 20-link discovery cap; analysis is O(links) not O(page). |
| `activate` would exceed the plan limit | creates up to the limit, returns `limit_reached: true` and the skipped URLs with a reason. Never a 500, never a silent partial success. |
| Duplicate analysis rows | unique `(user, normalized_url, fetched_at-bucket)`-style reuse: a live analysis under the TTL is returned with `cached: true` instead of re-fetched. |
| Public endpoint abuse | scoped DRF throttle (per IP), no persistence, no cookies, and the response is redacted to non-identifying public facts. |
| Extraction drift between checks | snapshots record the `method` per field, so a change caused by a different extraction path is visible rather than silently reported as a product change. |

**Security considerations**

- Fetches reuse `validate_url` (DNS-resolving SSRF guard) — no new egress
  path exists. Redirect hops are re-validated by the existing fetcher.
- The public endpoint exposes nothing that is not already public at the
  submitted URL, and never links the result to a user.
- Cross-tenant access returns **404**, never 403 (no existence oracle),
  matching the existing monitor convention.
- `activate` enforces the same `require_role(..., minimum="admin")` gate
  as monitor writes for workspace monitors.
- No prompt/credential handling, no HTML rendering of fetched content
  (React escapes; the evidence text is passed as text, never
  `dangerouslySetInnerHTML`).

---

## PHASE 2 — Competitor Pulse and Market Feed

**Goal.** A chronological intelligence feed and a per-competitor pulse
board. This is the "reason to come back" surface.

**User story.** *"I open Sitemyra and see that three competitors moved this
week, filtered to pricing. I click one and see exactly which competitor,
what changed, and when."*

**Database changes**

- `Competitor` — a tracked business: (`user`, `workspace`, `name`,
  `homepage_url`, `domain`, `relationship` = self/direct/adjacent/alternative,
  `status_note`, `first_seen_at`, `last_activity_at`). OneToMany
  `Monitor`s. A monitor created by Phase 1 gets a Competitor when its
  domain is new, so existing rows are enriched, not migrated.
- `CompetitorCandidate` — Feature 2 discovery output
  (`competitor`, `url`, `domain`, `relationship`, `reasons` JSON list of
  factual signals, `confidence`, `approved` bool). Candidates are never
  monitored until approved.
- `SignalEvent` — the feed row, derived not duplicated:
  (`workspace`, `competitor`, `monitor`, `check`, `kind` = pricing /
  products / features / marketing / content / hiring / other, `headline`,
  `summary`, `before`/`after` JSON, `severity`, `source_url`, `detected_at`,
  `evidence` JSON). Backfilled from `ProductChange` + `ChangeDiff` +
  `MonitorCheck(changed=True)`.
- `CompetitorRelationship` — factual "why we think they are a competitor"
  provenance: (`competitor`, `signal`, `value`, `source_url`).

**Backend changes**

- `intelligence/services/feed.py` — paginated, filtered, cursor-stable feed
  query. Single indexed query, no N+1; `detect_changes` flag on the viewset.
- `intelligence/services/pulse.py` — per-competitor descriptive states
  derived from `SignalEvent` counts in a window:
  `changed_recently` / `no_significant_change_detected` /
  `multiple_changes_detected` / `pricing_changed` / `new_product_detected`
  / `feature_change_detected`. **No numeric health score.**
- `intelligence/services/discovery.py` — Feature 2. Same-domain product
  catalogue + public "alternatives" pages already linked from the user's own
  site, classified into direct / adjacent / alternatives with a `reasons`
  list of *observable* signals (product category, target audience,
  capability keywords, positioning). Requires user approval before any
  monitor is created. Documented limitation: no paid data broker, no
  search-API dependency in v1 — candidates come from the user's own pages.
- Beat entry `intelligence.tasks.derive_signals` (every 15 min) that
  mints `SignalEvent` rows from new `ProductChange` / `ChangeDiff` /
  changed `MonitorCheck` rows, idempotently via a content hash on the source
  row id.

**Frontend changes**

- `app/dashboard/feed/page.tsx` — chronological feed with the filter row
  (All / Pricing / Products / Features / Marketing / Content / Hiring /
  Other), relative timestamps and severity chips.
- `app/dashboard/pulse/page.tsx` — competitor cards with descriptive
  state, last activity, sparkline of change counts, drill-through.
- `sidebar.tsx` — add Pulse and Feed (Feed first).
- `lib/api/feed.ts`, `lib/api/competitors.ts`.
- `app/dashboard/page.tsx` — overview becomes a compact pulse + latest feed.

**API changes**

- `GET /api/intelligence/feed/?kind=&competitor=&severity=&cursor=&limit=`
- `GET /api/intelligence/competitors/` + detail / `activity/`
- `POST /api/intelligence/competitors/discover/` → `CompetitorCandidate` list
- `POST /api/intelligence/competitors/{id}/approve/` → creates the monitors
- `GET /api/intelligence/pulse/`

**Tests** — feed ordering/filtering/cursor stability, N+1 query-count
assertions, severity derivation from real rows, candidate reason
provenance, approval creating monitors within plan limits, tenant
isolation on every endpoint.

**Failure modes** — empty feed on a brand-new account (empty state that
points back at the intake flow, never a blank screen); feed query cost as
`SignalEvent` grows (index + cursor pagination + `history_days` pruning);
discovery returning nothing (say so plainly — "we could not find public
signals for this site" — instead of inventing candidates).

**Security** — candidates are proposals, never monitors, until approved.
Feed rows inherit monitor visibility. Discovery reads only the user's own
submitted URLs.

---

## PHASE 3 — AI change explanation and market signals

**Goal.** Move from "what changed" to "why it may matter" and from
individual changes to cross-competitor patterns — while keeping every
sentence anchored to a stored observation.

**User story.** *"The feed tells me three competitors added AI features in
30 days, shows me the exact pages that prove it, and tells me what to
check next — without claiming to know their revenue."*

**Database changes**

- `ChangeExplanation` — (`signal_event`, `what_changed`, `why_it_may_matter`,
  `what_to_check`, `confidence`, `model`, `evidence` JSON, `generated_at`,
  `is_fallback`). Phase 1's deterministic explanation is the `is_fallback`
  row; the LLM version is a second row, so the deterministic text is never
  lost.
- `MarketSignal` — (`workspace`, `kind`, `headline`, `statement`,
  `interpretation`, `window_days`, `evidence` JSON (list of
  `{competitor, signal_event, source_url, detected_at}`), `confidence`,
  `created_at`, `status` = new/reviewed/dismissed).
- `User.ai_narration_enabled` (default **off** — opt-in, per the trust
  rules), `User.ai_provider`.

**Backend changes**

- `intelligence/services/narration.py` — sends only a **derived evidence
  packet** (already-stored before/after, source URLs, timestamps) to the
  provider; requires the response to cite each claim with an evidence id
  that exists in the packet; a citation that does not resolve is discarded
  and the deterministic fallback is used instead. Provider secrets read
  from env only, never from the database, never sent to the browser.
- `intelligence/services/signals.py` — cross-competitor detectors:
  price-increase cluster, feature-parity cluster, feature-removal,
  new-category entry, new product page, hiring-for-a-function. Each emits a
  `MarketSignal` with the evidence list attached and an `interpretation`
  written as a possibility, not a prediction.
- `intelligence/services/severity.py` — promotes Phase 1's deterministic
  severity into a user-visible ladder (`informational` / `minor` /
  `important` / `critical`) with per-category thresholds the user can tune.
- `intelligence/services/digest.py` — daily/weekly digest assembly from
  `SignalEvent` + `MarketSignal`, replacing the current monitor-only digest.

**Frontend changes**

- `app/dashboard/feed/[id]/page.tsx` — the alert deep link required by the
  final product test: what changed, why it may matter, what to check,
  source, before/after, detected-at, confidence, evidence list, export
  buttons.
- `app/dashboard/signals/page.tsx` — market signals with expandable evidence.
- `app/dashboard/settings/page.tsx` — narration toggle, severity thresholds,
  digest cadence (immediate / daily / weekly).

**API changes**

- `GET /api/intelligence/signals/`
- `POST /api/intelligence/signals/{id}/review/`
- `GET /api/intelligence/events/{id}/` (the deep link above)
- `PATCH /api/notifications/preferences/` — extended with digest cadence
  and a per-category minimum severity

**Tests** — citation validation (a fabricated citation is dropped and the
fallback is used), provider timeout/failure returns the fallback text,
narration off means no outbound call at all (asserted with a mock that
fails the test if called), each market-signal detector against a fixture
corpus, digest cadence routing.

**Failure modes** — provider outage (deterministic fallback, alert still
sends, nothing blocks the check); a hallucinated citation (dropped, logged,
fallback shown); a market signal that is technically true but trivial
(minimum evidence threshold of 2 competitors and 1 shared observable
attribute, otherwise not emitted).

**Security** — no competitor content is sent to a third party beyond the
text already public at the source URL; prompts carry no user identity; keys
are env-only; narration is opt-in and every generated sentence is stored
next to the deterministic text it may replace.

---

## PHASE 4 — Exports, reports and battlecards

**Goal.** Turn the intelligence into something an agency can send to a
client.

**User story.** *"I generate a branded competitive intelligence report for
a client: executive summary, competitors, pricing/product/feature/marketing
changes, a dated timeline, screenshots, and source links."*

**Database changes**

- `Report` — (`workspace`, `user`, `title`, `kind` = intelligence /
  compliance / battlecard, `period_start`, `period_end`, `competitors` M2M,
  `status`, `format`, `storage_key`, `generated_at`, `error`).
- `Battlecard` — (`competitor`, `sections` JSON, `positioning` Text,
  `sources` JSON, `generated_at`, `is_stale`). Regenerated when any
  contributing `SignalEvent` changes, tracked by `source_event_ids` so a
  stale card is labelled rather than silently wrong.

**Backend changes**

- `intelligence/services/exporters/` — `csv`, `xlsx`, `json`, `markdown`,
  `html`, `xml`, `pdf`. PDF reuses the existing `reportlab` dependency and
  the working fallback path in `monitors/views.py`. `xlsx` is a minimal
  writer (no new dependency) unless openpyxl is accepted.
- `intelligence/services/reports.py` — the report composition described
  above, always including source URL and timestamp per row.
- `intelligence/services/battlecards.py` — living competitor profile
  assembled from `Competitor` + latest snapshots + recent `SignalEvent`s.
- Every export includes source URLs, timestamps and the evidence id, so a
  downloaded file is self-auditing.

**Frontend changes**

- `app/dashboard/reports/page.tsx` — report builder (competitors, period,
  format) and history.
- `app/dashboard/competitors/[id]/battlecard/page.tsx` — the battlecard with
  a "last updated / evidence" footer and a stale badge.
- `app/dashboard/feed/page.tsx` — export controls for the current filter.

**API changes**

- `POST /api/intelligence/reports/` → queued generation
- `GET /api/intelligence/reports/` / `{id}/` / `{id}/download/`
- `GET /api/intelligence/competitors/{id}/battlecard/`
- `GET /api/intelligence/export/?format=&kind=&competitor=&from=&to=`

**Tests** — each format round-trips and contains a source URL per row; PDF
falls back correctly without reportlab; report generation is idempotent for
the same inputs; battlecard marks itself stale when a source event changes;
tenant isolation on every report row.

**Failure modes** — reportlab absent (fallback, as today); generation
timeout (status `failed` with a retry, no partial download offered);
a very large period (row cap with an explicit "truncated" marker rather
than a silent cut).

**Security** — export rows are filtered by the same visibility rules as the
feed; a report never contains another workspace's data; white-label
branding is stored as plain text and escaped on render.

---

## PHASE 5 — Agency mode

**Goal.** One account, many client workspaces, branded deliverables.

**User story.** *"My agency has 12 clients. Each client has its own
competitors, monitors, alerts, reports and users — and the PDF carries my
logo, not Sitemyra's."*

**Database changes**

- `Organization` — (`owner`, `name`, `slug`, `plan`, `mrr_cents`,
  `branding` JSON: logo asset key, primary colour, agency name, footer).
- `OrganizationMembership` — (`organization`, `user`, `role` =
  owner/admin/analyst/viewer, unique per pair).
- `Workspace.organization` — nullable FK (an existing personal workspace
  simply stays null; no data migration required).
- `Subscription.organization` — nullable OneToOne so billing moves from
  per-user to per-agency without a breaking change; `get_plan_for_user`
  resolves org plan first, then the personal subscription.
- Limits gain `max_client_workspaces`, `max_seats`, `white_label` — added
  to `PLAN_LIMITS` with defaults equal to current behaviour, so no existing
  account changes entitlement.

**Backend changes**

- `workspaces/views.py` — organisation CRUD, client-workspace creation,
  seat management, cross-workspace reporting.
- `billing` — organisation-level checkout, seat-based proration, and a
  migration path that keeps personal subscriptions valid.
- `intelligence/services/reports.py` — white-label rendering from
  `Organization.branding` with a Sitemyra credit line that the agency can
  disable on paid plans.
- `accounts/views.py` — organisation-scoped invitations that reuse the
  existing `WorkspaceInvite` flow (no second invite system).

**Frontend changes**

- `app/dashboard/organization/page.tsx` — agency settings, seats, billing.
- `app/dashboard/clients/page.tsx` — the agency client list (this is the
  `Agency → Client A/B/C` view).
- `app/dashboard/clients/[id]/page.tsx` — a client workspace with its own
  feed, competitors, reports and members.
- `sidebar.tsx` — switcher between personal and agency contexts.

**API changes**

- `/api/organizations/` CRUD + `/members/` + `/workspaces/` (client
  creation) + `/branding/`
- `/api/billing/organization/checkout/`, `/portal/`

**Tests** — the first test file in `workspaces/`; org isolation (a user in
two orgs sees only what their membership allows); a viewer cannot create a
client workspace; a plan downgrade pauses, never deletes, client monitors;
white-label output contains the agency brand and no Sitemyra logo; a
personal-only account behaves exactly as before.

**Failure modes** — an org is deleted while client workspaces still have
monitors (cascade is explicit and a dry-run report is shown first); a seat
is removed from a user who owns monitors (ownership is transferred or the
removal is blocked, never orphaned); a partial Stripe failure mid-migration
(the idempotent `StripeWebhookEvent` ledger already covers redelivery).

**Security** — org membership is the new authorisation root; every existing
`user_role_in_workspace` check is extended to resolve the org first;
cross-org reads return 404; the personal workspace of a user in an org is
still reachable by that user alone.

---

## PHASE 6 — Browser extension and bookmarklet

**Goal.** "Monitor with Sitemyra" from any competitor page.

**User story.** *"I am on a competitor's product page and click the Sitemyra
icon. It asks nothing, creates the monitor, and shows me what it found."*

**Database changes**

- `BrowserSession` — (`user`, `token_hash`, `label`, `created_at`,
  `last_used_at`, `revoked_at`, `scopes`). A short-lived, revocable,
  user-minted token for the extension. Hash-only storage, mirroring
  `ApiKey`.
- No other schema change: the extension creates exactly the same
  `Monitor` / `ProductWatch` rows the dashboard creates.

**Backend changes**

- `POST /api/intelligence/quick-monitor/` is reused as-is (already Phase 1).
- `POST /api/auth/extension-sessions/` mints a scoped, expiring token
  (monitor read/write only — no billing, no channels, no exports).
- CORS: the extension's origin is added explicitly; no wildcard.
- `intelligence/services/quick_monitor.py` — idempotent "monitor this page":
  if the user already monitors that URL, return the existing monitor rather
  than creating a duplicate.

**Frontend / extension**

- `frontend/public/bookmarklet.js` — a ~20-line bookmarklet that POSTs the
  current URL to the app's intake route. Ships in Phase 1's file layout so
  the marketing page can link it from day one.
- `extension/` — a separate MV3 Chromium package (`manifest.json`,
  `service-worker.js`, `popup/`):
  - "Monitor this page" → quick-monitor
  - "Monitor this product" → quick-monitor + product watch
  - "Track price" → quick-monitor, product watch, pricing recipe
  - "Track content" → quick-monitor, content recipe
  - "Open in Sitemyra" → deep link to the monitor
  - Storage is `chrome.storage.local`, holding only the scoped token.
- The extension stores **no** Stripe keys, no SMTP credentials, no raw
  `DJANGO_SECRET_KEY`, and no long-lived JWT. The token is revocable from
  `/dashboard/api-keys`-style settings and is invalidated server-side on
  revoke.

**API changes**

- `POST /api/auth/extension-sessions/` → `{ token, expires_at }`
- `DELETE /api/auth/extension-sessions/{id}/` → revoke
- reuse `POST /api/intelligence/quick-monitor/`

**Tests** — token mint/revoke/expiry, scope enforcement (an extension token
cannot call billing or channel endpoints), duplicate quick-monitor is
idempotent, rate limiting, and a CORS assertion for the extension origin.

**Failure modes** — no token in the browser (the popup opens the app to
mint one); expired token (clear in-extension message that links to the
login page); the page requires JavaScript (quick-monitor still works on the
URL, the browser engine is what needs Chromium).

**Security** — this is the highest-risk surface in the product. Invariants:
no private key ever reaches the browser; the extension token is scoped,
expiring, revocable and hash-only at rest; every extension call is subject
to the same plan limits, SSRF validation and tenant rules as the dashboard;
no competitor page content is sent anywhere by the extension.

---

## Cross-cutting notes

**Why the extraction is deterministic first.** Phase 1 ships product
"intelligence" with zero LLM calls. Every explanation is generated from the
stored observation by a named, testable rule, and the output includes the
rule that fired. Phase 3 adds narration *on top of that* and keeps the
deterministic text as the fallback. A competitive-intelligence product that
hallucinates a competitor's price is worse than one that says "not
detected".

**Why Phase 1 adds no new crawler.** The HTTP worker already downloads the
page for the content hash. Product extraction runs on those same bytes. A
product watch therefore costs no additional request, no additional queue
time and no browser slot — which is what makes it viable on a Free plan.

**Cost per monitored product page (measured expectation)**: one HTTP GET
(the existing check) plus ~1–3 ms of parsing. A 14-target "monitor
everything" activation on the Free plan's 3-URL limit creates 3 monitors
and reports the remaining 11 with a reason, rather than failing.

**Documentation deliverables per phase:** `SYSTEM_DOCUMENTATION.md`
(models, endpoints, limits, known gaps), `README.md` (what's in the box),
`.env.example` (every new variable), and this roadmap's status line.
