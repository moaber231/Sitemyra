# Sitemyra security review TODO

This is an internal follow-up list, not a security certification or a public
assurance. The Security page only describes controls that are visible in the
current source.

## Before or during launch

- [ ] Run and triage `npm audit --omit=dev` and the Python dependency audit in
      CI. The frontend is currently pinned to Next 15.5.x with a PostCSS
      override; keep that override and re-check it whenever Next is upgraded.
- [ ] Decide whether to add auth endpoint rate limiting, password reset,
      account verification, MFA, refresh-token rotation/revocation, and server
      logout. These are not currently implemented.
- [ ] Review workspace invite acceptance and viewer write permissions against
      the intended RBAC policy.
- [ ] Reconcile the onboarding engine selector with the advanced-monitor
      configuration endpoint before presenting it as a completed setup flow.
- [ ] Decide how non-2xx HTTP responses should affect monitor status and
      alerting; the lightweight checker currently records response status but
      does not classify every HTTP error as a failed check.
- [ ] Make production fail closed when required secrets (especially
      `DJANGO_SECRET_KEY` and database/Redis credentials) are missing.
- [ ] Document the actual TLS/edge provider and certificate renewal process;
      the repository intentionally contains no Nginx configuration.
- [ ] Review residual browser URL-fetch risks (DNS rebinding and WebSocket
      handshakes) and decide whether an egress control is needed.
- [ ] Decide whether to add a privacy-preserving analytics provider and update
      the Privacy and Cookie policies before enabling it.
- [ ] Confirm and, if intended, enforce plan entitlements for advanced modes,
      workspaces, and compliance exports before treating the pricing table as a
      strict product contract.
- [ ] Establish a private security-contact address and a responsible
      disclosure process.

## Competitive-intelligence surface (added with Phase 1)

Reviewed at implementation time; the items marked **open** are the ones that
still need a decision. See `SYSTEM_DOCUMENTATION.md` §3.6 and
`docs/INTELLIGENCE-ROADMAP.md` for the design.

- [x] **The analysis endpoint reuses the SSRF-hardened fetcher.** It calls
      `monitors.services.fetcher.fetch_url`, so DNS-resolving validation,
      per-redirect-hop re-validation, the 10 MiB cap and the port/credential
      rules are identical to a normal check. No new egress path exists.
      Verified by test (`test_a_blocked_url_is_refused_with_a_plain_message`).
- [x] **Cross-tenant reads return 404, never 403**, so the intelligence API
      cannot be used to probe for the existence of another account's
      analyses or product watches (`test_another_users_analysis_is_a_404_not_a_403`,
      `test_another_users_watch_is_a_404`).
- [x] **Workspace writes require admin**, matching the monitor endpoints
      (`test_a_viewer_cannot_activate_into_a_workspace`).
- [x] **The unauthenticated demo endpoint stores nothing, references no
      user, sets no cookie, and returns only facts that were already public
      at the submitted URL.** Asserted by
      `test_public_analyze_persists_nothing_and_names_no_user`.
- [x] **That demo endpoint is rate limited** by a *scoped* DRF throttle
      (`PUBLIC_ANALYZE_RATE`, default `12/hour` per IP). Adding
      `DEFAULT_THROTTLE_RATES` throttles no other view, because no other view
      declares a throttle class. **Open:** decide the production value, and
      whether a stricter per-IP + per-subnet rule is needed once the API
      origin is public.
- [x] **Only public pages are monitored.** No login flow, no paywall bypass,
      no private API, no credential capture. Product extraction reads the
      same public HTML a visitor would.
- [x] **Fetched competitor content is never rendered as HTML.** All values
      are passed to React as text; there is no `dangerouslySetInnerHTML` in
      the intelligence components. `raw` evidence strings are truncated to
      280/400 characters before storage.
- [x] **The bookmarklet holds no credential.** It contains no token, no API
      key and no secret, and never calls the API — it only opens Sitemyra
      with the current URL. Sign-in happens in the app.
- [x] **Captured product content is private to the owner.** `ProductWatch`
      is reachable only through a `Monitor` the caller can already see, and
      there is no code path that publishes it. Phase 5's white-label reports
      must re-check this per client workspace before shipping.
- [x] **Intelligence cannot break monitoring.** The capture hook in
      `check_monitor`, the alert-body block in `notifications.services`, and
      the retention pruner are each wrapped so a failure degrades to "no
      product data" and never fails or delays a check
      (`test_a_capture_failure_never_breaks_the_check`).
- [ ] **Open — the analyze request fetches the page synchronously**, holding
      an API worker for up to `MAX_ANALYSIS_TIMEOUT_SECONDS` (30). Acceptable
      while the endpoint is authenticated, but the *public* endpoint
      combines an anonymous request with a synchronous outbound fetch. Before
      launch, either put a hard concurrency limit on the public path or move
      it behind a queue, and load-test the 12/hour limit against a slow
      origin.
- [ ] **Open — the public endpoint is an open fetch proxy by design.** It
      will fetch any public URL the caller names. The SSRF guard covers
      internal networks, but consider an allow/deny list for very large
      origins, a response-size cap specific to this path, and logging that
      makes abuse attributable without retaining the caller's identity.
- [ ] **Open — `relevance` must never be presented as a business score.**
      It is a link-ordering heuristic capped at 99. Review any future UI that
      surfaces it numerically, and keep Phase 2's competitor states
      descriptive ("pricing changed") rather than scored.
- [ ] **Open — third-party page content becomes part of an email body.**
      Product names, prices and badges from a competitor page are included in
      the alert. `_transactional_html` escapes them, but confirm the plain-text
      and Slack/Discord renderers cannot be used for header injection, and
      that a page with a deliberately hostile product name cannot break the
      email layout.

Do not add SOC 2, ISO, GDPR, penetration-test, or uptime/security guarantees to
the public site unless they have actually been completed and verified.
