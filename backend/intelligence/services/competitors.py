"""Grouping monitors into competitors.

A competitor is a registrable domain, not a URL. That is the unit a
business competes at, and it is the unit that makes a feed entry
("Acme cut prices") comparable to another ("BetaSoft added integrations").

`ensure_competitor_for_monitor` is the only writer. It is called from
activation and lazily by the signal derivation, which means monitors that
predate this phase are enriched instead of migrated.
"""

import logging

from django.db import transaction
from django.utils import timezone

from .urls import display_host, registrable_domain

logger = logging.getLogger(__name__)

# Label heuristics. These only name a competitor for the user; they never
# assert a relationship. A wrong name is cosmetic and the user can rename.
_NAME_HINTS = (
    ("pricing", "Pricing"),
    ("plans", "Plans & pricing"),
    ("changelog", "Changelog"),
    ("careers", "Careers"),
    ("jobs", "Careers"),
    ("blog", "Blog"),
    ("features", "Features"),
    ("products", "Store"),
    ("shop", "Store"),
)


def name_for_domain(domain: str, fallback: str = "") -> str:
    """A human label for a domain, derived only from the URL itself."""
    host = display_host(f"https://{domain}") if domain else ""
    if not host:
        return fallback or "Competitor"
    label = host.split(".")[0]
    if not label or label in ("www", "shop", "store", "app", "www2"):
        parts = host.split(".")
        return parts[1] if len(parts) > 2 else host
    return label.replace("-", " ").replace("_", " ").strip().title() or host


def kind_label_for_domain(domain: str) -> str:
    return next((label for token, label in _NAME_HINTS if token in domain), "")


def _competitor_name_from_monitor(monitor) -> str:
    domain = registrable_domain(monitor.url)
    if not domain:
        return monitor.name[:200]
    # A product page tells us more than the bare host: "Store" reads better
    # than a bare wordmark when the user tracks a shop subdomain.
    label = kind_label_for_domain(domain)
    if label and registrable_domain(monitor.url) != registrable_domain(f"https://{domain}"):
        return label
    return name_for_domain(domain, fallback=monitor.name)[:200]


@transaction.atomic
def ensure_competitor_for_monitor(monitor, relationship=None, reasons=None):
    """Get or create the Competitor owning this monitor's domain.

    Returns ``(competitor, created)``. Concurrent activation of two monitors
    on the same domain can race the unique constraint, so that case is
    caught and retried rather than surfaced as a 500.
    """
    from ..models import Competitor

    domain = registrable_domain(monitor.url)
    if not domain:
        # An IP-literal or unusable host: group under a stable synthetic key
        # so the feed still works instead of dropping the event.
        domain = f"host:{monitor.url[:200]}"

    existing = Competitor.objects.filter(user=monitor.user, domain=domain).first()
    now = timezone.now()
    if existing is not None:
        changed = []
        if existing.first_seen_at is None:
            existing.first_seen_at = now
            changed.append("first_seen_at")
        if relationship and existing.relationship == Competitor.RELATIONSHIP_TRACKED:
            existing.relationship = relationship
            changed.append("relationship")
        if reasons:
            merged = list(existing.relationship_reasons or [])
            for reason in reasons:
                if reason not in merged:
                    merged.append(reason)
            if merged != list(existing.relationship_reasons or []):
                existing.relationship_reasons = merged
                changed.append("relationship_reasons")
        if changed:
            existing.save(update_fields=[*changed, "updated_at"])
        return existing, False

    try:
        competitor = Competitor.objects.create(
            user=monitor.user,
            workspace=monitor.workspace,
            name=_competitor_name_from_monitor(monitor),
            homepage_url=f"https://{domain}",
            domain=domain,
            relationship=relationship or Competitor.RELATIONSHIP_TRACKED,
            relationship_reasons=list(reasons or []),
            first_seen_at=now,
            last_activity_at=None,
        )
    except Exception:
        # Lost a race on the unique constraint — the other writer won, which
        # is the outcome we wanted anyway.
        competitor = Competitor.objects.filter(user=monitor.user, domain=domain).first()
        if competitor is None:
            logger.exception(
                "intelligence competitor create failed [monitor_id=%s]", monitor.id
            )
            return None, False
        return competitor, False

    return competitor, True


def ensure_competitors_for_monitors(monitors):
    """Batch variant used by the derivation task. One query to read, N writes."""
    created = []
    for monitor in monitors:
        competitor, was_created = ensure_competitor_for_monitor(monitor)
        if competitor is not None:
            created.append(competitor)
    return created


def record_activity(competitor, when) -> None:
    """Bump a competitor's last-activity stamp (no-op when older)."""
    if competitor is None or when is None:
        return
    if competitor.last_activity_at is None or when > competitor.last_activity_at:
        competitor.last_activity_at = when
        competitor.save(update_fields=["last_activity_at", "updated_at"])


def merge_target_signals(competitor, signals) -> None:
    """Store the verbatim URL/metadata signals a battlecard will show."""
    if competitor is None or not signals:
        return
    merged = list(competitor.signals or [])
    for signal in signals:
        if signal not in merged:
            merged.append(signal)
    if len(merged) > 40:
        merged = merged[:40]
    if merged != list(competitor.signals or []):
        competitor.signals = merged
        competitor.save(update_fields=["signals", "updated_at"])
