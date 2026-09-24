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

Do not add SOC 2, ISO, GDPR, penetration-test, or uptime/security guarantees to
the public site unless they have actually been completed and verified.
