# Sitemyra analytics recommendation

## Current state

No analytics provider or client-side tracking integration was found in the
frontend or backend repository. The application currently uses essential
authentication storage and does not need an analytics dependency to function.

## Recommendation

Do not add a large analytics stack for the first campaign. If measurable
funnel data becomes necessary, choose one privacy-conscious, self-hostable or
minimal provider and document it in the Privacy and Cookie policies before
enabling it. Collect aggregate events rather than page content, monitor URLs,
email addresses, credentials, or free-form customer data.

Suggested event names, only after a provider and consent/retention decision are
approved:

- `landing_page_view`
- `signup_started`
- `signup_completed`
- `first_monitor_created`
- `first_monitoring_job`
- `first_alert_sent`
- `pricing_page_view`
- `upgrade_started`
- `upgrade_completed`

These events should be emitted only at the corresponding successful product
milestones. No analytics code was added in this change.
