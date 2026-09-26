"""Competitive intelligence reports and living battlecards (Phase 4).

A **report** is a dated snapshot of what changed for a set of competitors in
a period, composed into the section order the brief specifies:
Executive Summary → Competitors → Pricing / Product / Feature / Marketing
Changes → Timeline → Evidence → Source links. Every claim keeps its source
URL and timestamp, so a report a client receives is auditable.

A **battlecard** is the *living* version: a competitor profile assembled
from the competitor record, its latest product snapshots and its recent
signals. It records the ids of the rows it was built from, so when one of
those rows changes the card can be labelled stale instead of quietly
becoming wrong — which is the failure mode that would make a battlecard
worse than no battlecard.
"""

import hashlib
import logging

from django.db import transaction
from django.utils import timezone

from . import exporters
from .feed import ACTIVE_WINDOW_DAYS, pulse_for_competitor
from .product_diff import SEVERITY_LABELS, discount_percent

# `discount_percent` is a serializer-derived convenience field, not a
# column, so the report recomputes it from the stored list/current price
# rather than reading a non-existent attribute. It is rounded to a float so
# the battlecard and the report JSON stay serialisable.

logger = logging.getLogger(__name__)

REPORT_KIND_INTELLIGENCE = "intelligence"
REPORT_KIND_BATTLECARD = "battlecard"
REPORT_KINDS = (
    (REPORT_KIND_INTELLIGENCE, "Competitive intelligence"),
    (REPORT_KIND_BATTLECARD, "Battlecard"),
)

STATUS_PENDING = "pending"
STATUS_READY = "ready"
STATUS_FAILED = "failed"
STATUS_CHOICES = (
    (STATUS_PENDING, "Generating"),
    (STATUS_READY, "Ready"),
    (STATUS_FAILED, "Failed"),
)

MAX_PERIOD_DAYS = 366
DEFAULT_PERIOD_DAYS = 30
# A report is never silently truncated: it is capped and says so.
MAX_ROWS = 5000

SECTION_LABELS = [
    ("pricing", "Pricing changes"),
    ("products", "Product changes"),
    ("features", "Feature changes"),
    ("marketing", "Marketing changes"),
    ("content", "Content changes"),
    ("hiring", "Hiring changes"),
    ("other", "Other changes"),
]


# --------------------------------------------------------------------------
# Report composition
# --------------------------------------------------------------------------


def _visible_filter(user):
    from django.db.models import Q

    from ..views_phase2 import _workspace_ids

    if user.is_superuser:
        return Q()
    visible = Q(user=user)
    workspace_ids = _workspace_ids(user)
    if workspace_ids:
        visible |= Q(workspace_id__in=workspace_ids)
    return visible


def collect_events(user, competitor_ids=(), monitor_ids=(), period_start=None, period_end=None, limit=MAX_ROWS):
    from ..models import SignalEvent

    queryset = SignalEvent.objects.filter(_visible_filter(user))
    if competitor_ids:
        queryset = queryset.filter(competitor_id__in=list(competitor_ids))
    if monitor_ids:
        queryset = queryset.filter(monitor_id__in=list(monitor_ids))
    if period_start:
        queryset = queryset.filter(detected_at__gte=period_start)
    if period_end:
        queryset = queryset.filter(detected_at__lte=period_end)
    total = queryset.count()
    rows = list(
        queryset.select_related("competitor", "monitor").order_by("-detected_at")[:limit]
    )
    return rows, total


def _collect_competitors(user, competitor_ids=()):
    from ..models import Competitor

    queryset = Competitor.objects.filter(_visible_filter(user))
    if competitor_ids:
        queryset = queryset.filter(id__in=list(competitor_ids))
    return list(queryset.order_by("name"))


def executive_summary(events, competitors, truncated=False, total=None):
    """A factual summary. Counts and named sources only — no verdicts."""
    if not events:
        return {
            "text": (
                "No changes were recorded for the selected competitors during "
                "this period. Sitemyra checked the monitored pages and found no "
                "published value that differed from the previous check."
            ),
            "counts": {"total": 0},
        }
    by_kind = {}
    by_severity = {}
    for event in events:
        by_kind[event.kind] = by_kind.get(event.kind, 0) + 1
        by_severity[event.severity] = by_severity.get(event.severity, 0) + 1
    most_active = max(by_kind.items(), key=lambda item: item[1])
    busiest = max(
        {event.competitor.name for event in events if event.competitor_id} or {"—"},
        key=lambda name: sum(
            1 for event in events if event.competitor_id and event.competitor.name == name
        ),
    )
    important = by_severity.get("critical", 0) + by_severity.get("important", 0)
    text = (
        f"Sitemyra recorded {len(events)} change(s) across "
        f"{len(competitors)} competitor(s) in this period. The most active area was "
        f"{most_active[0]} ({most_active[1]} change(s)), and the most active competitor was "
        f"{busiest}. {important} change(s) were classified important or critical by "
        f"Sitemyra's fixed thresholds. Every change below lists the page it was read from."
    )
    if truncated:
        text += (
            f" This report shows the most recent {len(events)} of {total} changes."
        )
    return {
        "text": text,
        "counts": {
            "total": len(events),
            "by_kind": by_kind,
            "by_severity": {
                SEVERITY_LABELS.get(key, key): value
                for key, value in by_severity.items()
            },
            "competitors": len(competitors),
            "important_or_critical": important,
            "truncated": truncated,
            "total_available": total,
        },
    }


def compose_report(user, title, competitor_ids=(), monitor_ids=(), period_start=None, period_end=None, branding=None, sheet_name="Intelligence"):
    """Build the full report payload. Pure read; the caller persists it."""
    events, total = collect_events(
        user,
        competitor_ids=competitor_ids,
        monitor_ids=monitor_ids,
        period_start=period_start,
        period_end=period_end,
    )
    competitors = _collect_competitors(user, competitor_ids)
    truncated = total > len(events)
    summary = executive_summary(events, competitors, truncated=truncated, total=total)

    sections = []
    for kind, label in SECTION_LABELS:
        rows = [event for event in events if event.kind == kind]
        if rows:
            sections.append(
                {
                    "kind": kind,
                    "label": label,
                    "count": len(rows),
                    "rows": [exporters.flatten_event(event) for event in rows],
                }
            )

    timeline = [
        {
            "detected_at": event.detected_at.isoformat() if event.detected_at else "",
            "competitor": event.competitor.name if event.competitor_id else "",
            "headline": event.headline,
            "kind": event.kind,
            "severity": event.severity,
            "source_url": event.source_url,
        }
        for event in reversed(events)
    ]

    sources = sorted(
        {event.source_url for event in events if event.source_url}
    )

    competitor_cards = []
    for competitor in competitors:
        pulse = pulse_for_competitor(competitor, window_days=DEFAULT_PERIOD_DAYS)
        competitor_cards.append(
            {
                "id": str(competitor.id),
                "name": competitor.name,
                "domain": competitor.domain,
                "homepage_url": competitor.homepage_url,
                "relationship": competitor.relationship,
                "relationship_reasons": competitor.relationship_reasons or [],
                "states": pulse["states"],
                "state_label": pulse["state_label"],
                "events_in_period": sum(
                    1 for event in events if event.competitor_id == competitor.id
                ),
                "signals": pulse["signals"],
            }
        )

    period_days = DEFAULT_PERIOD_DAYS
    if period_start and period_end:
        period_days = max(1, (period_end - period_start).days)

    return {
        "title": title,
        "generated_at": timezone.now().isoformat(),
        "period_start": period_start.isoformat() if period_start else None,
        "period_end": period_end.isoformat() if period_end else None,
        "period_days": period_days,
        "branding": branding or {},
        "executive_summary": summary,
        "competitors": competitor_cards,
        "sections": sections,
        "timeline": timeline,
        "sources": sources,
        "note": exporters.GENERATED_NOTE,
        "truncated": truncated,
        "rows": [exporters.flatten_event(event) for event in events],
    }


def _period_bounds(days, end=None):
    end = end or timezone.now()
    start = end - timezone.timedelta(days=max(1, min(int(days or DEFAULT_PERIOD_DAYS), MAX_PERIOD_DAYS)))
    return start, end


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------


def _discount_float(list_price, price):
    percent = discount_percent(list_price, price)
    if percent is None:
        return None
    return float(round(percent, 1))


def _slugify(value, fallback="report"):
    import re

    cleaned = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return (cleaned or fallback)[:60]


@transaction.atomic
def create_report(
    user,
    title,
    competitor_ids=(),
    monitor_ids=(),
    period_days=DEFAULT_PERIOD_DAYS,
    formats=("html", "pdf"),
    branding=None,
    workspace=None,
    organization=None,
    kind=REPORT_KIND_INTELLIGENCE,
    sheet_name="Intelligence",
):
    from ..models import Report

    period_start, period_end = _period_bounds(period_days)
    payload = compose_report(
        user,
        title,
        competitor_ids=competitor_ids,
        monitor_ids=monitor_ids,
        period_start=period_start,
        period_end=period_end,
        branding=branding,
        sheet_name=sheet_name,
    )
    report = Report.objects.create(
        user=user,
        workspace=workspace,
        organization=organization,
        title=title[:200],
        slug=_slugify(title),
        kind=kind,
        period_start=period_start,
        period_end=period_end,
        competitor_ids=[str(value) for value in competitor_ids],
        status=STATUS_READY,
        formats=list(formats),
        payload=payload,
        meta={
            "rows": len(payload["rows"]),
            "competitors": len(payload["competitors"]),
            "truncated": payload["truncated"],
            "sources": len(payload["sources"]),
        },
        branding=payload["branding"],
        generated_at=timezone.now(),
    )
    return report


def render_report(report, fmt):
    """Render a stored report payload in one of the supported formats."""
    key = (fmt or "html").strip().lower()
    title = report.title
    meta = {
        "period_days": report.payload.get("period_days"),
        "competitors": report.meta.get("competitors", 0),
        "changes": report.meta.get("rows", 0),
        "generated_by": "Sitemyra",
    }
    rows = report.payload.get("rows") or []
    sheet = _slugify(title, "Intelligence").title()[:31]
    return exporters.render(
        key,
        rows,
        title=title,
        meta=meta,
        branding=report.branding,
        sheet_name=sheet,
    )


# --------------------------------------------------------------------------
# Battlecards
# --------------------------------------------------------------------------


def _fingerprint(value) -> str:
    return hashlib.sha256(str(value).encode()).hexdigest()[:32]


def compose_battlecard(competitor, window_days=ACTIVE_WINDOW_DAYS):
    """A living competitor profile, assembled from stored rows.

    Structure follows the brief: Competitor, Website, Products, Pricing,
    Features, Recent changes, Positioning, Sources. Every section says
    either what was observed or that nothing was observed — it never fills
    a gap with an assumption.
    """
    from ..models import ProductWatch, SignalEvent

    pulse = pulse_for_competitor(competitor, window_days=window_days)

    watches = list(
        ProductWatch.objects.filter(
            monitor__user=competitor.user, monitor__url__icontains=competitor.domain
        ).select_related("monitor")[:25]
    )
    products = []
    pricing = []
    features = []
    source_event_ids = []

    for watch in watches:
        snapshot = watch.latest_snapshot
        if snapshot is None:
            products.append(
                {
                    "name": watch.name,
                    "url": watch.monitor.url,
                    "state": "No product data read yet — the first check has not completed.",
                    "product_detected": watch.product_detected,
                    "detection_note": watch.detection_note,
                }
            )
            continue
        products.append(
            {
                "name": snapshot.name or watch.name,
                "url": watch.monitor.url,
                "brand": snapshot.brand,
                "sku": snapshot.sku,
                "availability": (snapshot.availability or "").replace("_", " ")
                or "not published",
                # Decimal/int columns must be JSON scalars, not Decimals:
                # sections is a JSONField.
                "rating": str(snapshot.rating) if snapshot.rating is not None else None,
                "review_count": snapshot.review_count,
                "variants": len(snapshot.variants),
                "badges": snapshot.badges,
                "bundles": snapshot.bundles,
                "product_detected": watch.product_detected,
                "captured_at": snapshot.captured_at.isoformat(),
                "source_url": snapshot.source_url,
            }
        )
        if snapshot.price is not None:
            pricing.append(
                {
                    "name": snapshot.name or watch.name,
                    "price": str(snapshot.price),
                    "list_price": str(snapshot.list_price) if snapshot.list_price else "",
                    "discount_percent": _discount_float(
                        snapshot.list_price, snapshot.price
                    ),
                    "currency": snapshot.currency,
                    "source_url": snapshot.source_url,
                    "captured_at": snapshot.captured_at.isoformat(),
                }
            )
        if snapshot.specs:
            features.append(
                {
                    "name": snapshot.name or watch.name,
                    "specs": snapshot.specs,
                    "source_url": snapshot.source_url,
                }
            )

    since = timezone.now() - timezone.timedelta(days=window_days)
    recent = list(
        SignalEvent.objects.filter(competitor=competitor, detected_at__gte=since)
        .select_related("monitor")
        .order_by("-detected_at")[:25]
    )
    for event in recent:
        source_event_ids.append(str(event.id))

    positioning = _positioning_note(competitor, pricing, products, features)

    sources = sorted(
        {
            entry.get("source_url")
            for entry in products + pricing + features
            if entry.get("source_url")
        }
        | {competitor.homepage_url}
    )

    fingerprint = _fingerprint(
        "|".join(
            sorted(
                source_event_ids
                + [str(entry.get("captured_at", "")) for entry in pricing]
            )
        )
    )

    return {
        "competitor": {
            "id": str(competitor.id),
            "name": competitor.name,
            "domain": competitor.domain,
            "website": competitor.homepage_url,
            "relationship": competitor.relationship,
            "relationship_reasons": competitor.relationship_reasons or [],
            "first_seen_at": competitor.first_seen_at.isoformat()
            if competitor.first_seen_at
            else None,
        },
        "window_days": window_days,
        "state": pulse["state_label"],
        "states": pulse["states"],
        "products": products,
        "pricing": pricing,
        "features": features,
        "recent_changes": [
            {
                "id": str(event.id),
                "detected_at": event.detected_at.isoformat(),
                "headline": event.headline,
                "kind": event.kind,
                "severity": event.severity,
                "source_url": event.source_url,
            }
            for event in recent
        ],
        "positioning": positioning,
        "sources": sources,
        "source_event_ids": source_event_ids,
        "fingerprint": fingerprint,
        "note": exporters.GENERATED_NOTE,
    }


def _positioning_note(competitor, pricing, products, features):
    """Describe what the evidence shows, and admit what it does not.

    Deliberately not a summary of adjectives. It states the observable
    facts and, where nothing was observed, says so.
    """
    lines = []
    if competitor.relationship_reasons:
        lines.append(
            "Sitemyra classified this company as a "
            f"{competitor.relationship} competitor because: "
            + " ".join(competitor.relationship_reasons)
        )
    else:
        lines.append(
            "Sitemyra has no recorded reason for this classification — the "
            "company was added as a plain monitor."
        )
    if pricing:
        currencies = sorted({item["currency"] for item in pricing if item["currency"]})
        discounted = [item for item in pricing if item.get("discount_percent")]
        lines.append(
            f"{len(pricing)} product price(s) observed"
            + (f" in {', '.join(currencies)}" if currencies else "")
            + (
                f"; {len(discounted)} of them are published with a discount."
                if discounted
                else "; none are published with a discount."
            )
        )
    else:
        lines.append("No product price has been read from this company's pages yet.")
    if features:
        lines.append(
            f"{len(features)} product page(s) publish a structured specification list."
        )
    else:
        lines.append("No structured specification list has been read yet.")
    lines.append(
        "Positioning language is not inferred by Sitemyra: it is only recorded when a "
        "monitored page publishes it as a signal."
    )
    return " ".join(lines)


def upsert_battlecard(competitor, window_days=ACTIVE_WINDOW_DAYS):
    from ..models import Battlecard

    payload = compose_battlecard(competitor, window_days=window_days)
    existing = Battlecard.objects.filter(competitor=competitor).first()
    if existing is None:
        return Battlecard.objects.create(
            competitor=competitor,
            sections={
                "products": payload["products"],
                "pricing": payload["pricing"],
                "features": payload["features"],
                "positioning": payload["positioning"],
            },
            positioning=payload["positioning"],
            sources=payload["sources"],
            source_event_ids=payload["source_event_ids"],
            fingerprint=payload["fingerprint"],
            generated_at=timezone.now(),
        )
    if existing.fingerprint != payload["fingerprint"]:
        existing.sections = {
            "products": payload["products"],
            "pricing": payload["pricing"],
            "features": payload["features"],
            "positioning": payload["positioning"],
        }
        existing.positioning = payload["positioning"]
        existing.sources = payload["sources"]
        existing.source_event_ids = payload["source_event_ids"]
        existing.fingerprint = payload["fingerprint"]
        existing.generated_at = timezone.now()
        existing.save()
    return existing


def is_battlecard_stale(battlecard) -> bool:
    """True when a source event changed after the card was generated.

    A stale card is labelled, never silently served: a battlecard that
    looks current but is not is the worst outcome this feature has.
    """
    from ..models import SignalEvent

    from django.db.models import Max

    if battlecard.generated_at is None:
        return False
    # "Stale" means a newer change exists for this competitor than the one
    # the card was built from. It is NOT about the card's own rows (those
    # are necessarily older than the card) — that would be unreachable.
    latest = (
        SignalEvent.objects.filter(competitor=battlecard.competitor)
        .aggregate(latest=Max("created_at"))["latest"]
    )
    if latest is None:
        return False
    return latest > battlecard.generated_at
