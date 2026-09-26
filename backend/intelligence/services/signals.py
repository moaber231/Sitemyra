"""Deriving the market feed from rows that already exist.

This module **never detects a change**. It only turns changes the
monitoring engine already recorded into feed rows:

  ProductChange            → a product/pricing/features/marketing signal
  MonitorCheck(changed)    → a content/marketing/hiring signal for the page
  ChangeDiff(type=price)   → a pricing signal

Idempotency is by `source_key`, a deterministic string derived from the
source row. Re-running the beat tick, a Celery retry, or a manual trigger
cannot duplicate a feed entry — that property is what makes it safe to run
this on a 15-minute schedule.

The feed is a *chronological intelligence feed*, not a notification log:
headlines are written for a human, and every row keeps the source URL so a
click lands on the page that changed.
"""

import hashlib
import logging

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from . import competitors as competitor_service
from .classify import (
    BLOG,
    CAREERS,
    CHANGELOG,
    DOCS,
    FAQ,
    FEATURES,
    HOMEPAGE,
    PRICING,
    PRODUCT,
    PROMOTIONS,
    REVIEWS,
    SUPPORT,
)


logger = logging.getLogger(__name__)

# Page kind → feed kind. A changelog is a feature signal; careers is hiring.
PAGE_KIND_TO_FEED = {
    PRODUCT: "products",
    PRICING: "pricing",
    PROMOTIONS: "pricing",
    FEATURES: "features",
    CHANGELOG: "features",
    DOCS: "features",
    "variants": "products",
    REVIEWS: "content",
    FAQ: "content",
    BLOG: "content",
    HOMEPAGE: "marketing",
    SUPPORT: "other",
    CAREERS: "hiring",
    "other": "other",
    "legal": "other",
}

# ProductChange category → feed kind.
CATEGORY_TO_FEED = {
    "pricing": "pricing",
    "product": "products",
    "features": "features",
    "marketing": "marketing",
    "content": "content",
    "reviews": "content",
    "availability": "products",
}

# Emphatic verbs for the feed headline. The emoji set is intentionally small
# and fixed so the feed reads consistently.
_KIND_ICON = {
    "pricing": "🔥",
    "products": "🛍",
    "features": "🚀",
    "marketing": "📣",
    "content": "📝",
    "hiring": "🧑‍💼",
    "other": "•",
}

_SEVERITY_LABEL = {
    "critical": "critical",
    "important": "important",
    "minor": "minor",
    "informational": "informational",
}


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:32]


def _source_key(prefix: str, *parts) -> str:
    return f"{prefix}:{_fingerprint('|'.join(str(part) for part in parts))}"


def feed_kind_for_page_kind(page_kind: str) -> str:
    return PAGE_KIND_TO_FEED.get(page_kind, "other")


def icon_for(kind: str) -> str:
    return _KIND_ICON.get(kind, _KIND_ICON["other"])


def _relative_label(detected_at, now=None):
    now = now or timezone.now()
    seconds = max(0, int((now - detected_at).total_seconds()))
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days < 30:
        return f"{days}d ago"
    return f"{days // 30}mo ago"


# --------------------------------------------------------------------------
# Product changes
# --------------------------------------------------------------------------


def _product_headline(competitor_name, change, product_name=""):
    """Name the product when we know it.

    "Competitor changed price" is weak; "Acme cut the price of Acme Pro
    Widget" is the sentence an SMB user can act on. The competitor name
    always comes first, because the feed is grouped by competitor.
    """
    subject = competitor_name
    if product_name and product_name.strip() and product_name.strip() != competitor_name:
        subject = f"{competitor_name} · {product_name.strip()}"
    label = change.label
    if change.field == "availability":
        before = (change.before or "").replace("_", " ")
        after = (change.after or "").replace("_", " ")
        return f"{subject} availability: {before} → {after}"
    if change.field == "price":
        return f"{subject} changed {label.lower()}"
    if change.field == "variants":
        return f"{subject} changed its variant list"
    if change.field == "badges":
        return f"{subject} changed its promotional badges"
    if change.field == "review_count":
        return f"{subject} published a new review count"
    if change.field in ("name", "description", "brand", "sku", "specs", "shipping"):
        return f"{subject} updated its {label.lower()}"
    return f"{subject}: {label.lower()} changed"


def derive_from_product_change(change, competitor, page_kind=""):
    """Build a feed payload for one ProductChange. Returns ``None`` to skip."""
    from ..models import SignalEvent

    if competitor is None:
        return None
    kind = CATEGORY_TO_FEED.get(change.category, "other")
    detected_at = change.created_at
    key = _source_key("pc", change.id)
    currency = ""
    watch = getattr(change, "product_watch", None)
    if watch is not None:
        currency = watch.currency or ""
        currency = f"{currency} " if currency else ""

    before = f"{currency}{change.before}" if change.field in ("price", "list_price") and change.before else change.before
    after = f"{currency}{change.after}" if change.field in ("price", "list_price") and change.after else change.after

    return {
        "source_key": key,
        "user": competitor.user,
        "workspace": competitor.workspace,
        "competitor": competitor,
        "monitor_id": watch.monitor_id if watch is not None else None,
        "monitor_check_id": change.monitor_check_id,
        "product_change_id": change.id,
        "kind": kind,
        "headline": _product_headline(competitor.name, change, watch.name if watch else ""),
        "summary": change.basis or "",
        "before": (before or "")[:300],
        "after": (after or "")[:300],
        "severity": _SEVERITY_LABEL.get(change.severity, "informational"),
        "source_url": change.source_url or "",
        "detected_at": detected_at,
        "evidence": {
            "field": change.field,
            "rule": change.rule,
            "basis": change.basis,
            "severity_label": change.severity,
            "detected_content": change.evidence.get("raw", "") if isinstance(change.evidence, dict) else "",
        },
        "_icon": icon_for(kind),
        "_model": SignalEvent,
    }


# --------------------------------------------------------------------------
# Plain content changes
# --------------------------------------------------------------------------


def _content_headline(competitor_name, page_kind, monitor):
    label = {
        PRODUCT: "product page",
        PRICING: "pricing page",
        PROMOTIONS: "promotions page",
        FEATURES: "features page",
        CHANGELOG: "changelog",
        DOCS: "documentation",
        REVIEWS: "reviews page",
        FAQ: "FAQ page",
        BLOG: "blog",
        HOMEPAGE: "homepage messaging",
        CAREERS: "careers page",
    }.get(page_kind, "page")
    return f"{competitor_name} changed its {label}"


def derive_from_changed_check(check, competitor, page_kind="other"):
    """Feed payload for a changed check that produced no product change."""
    from ..models import SignalEvent

    if competitor is None:
        return None
    kind = feed_kind_for_page_kind(page_kind)
    return {
        "source_key": _source_key("chk", check.id),
        "user": competitor.user,
        "workspace": competitor.workspace,
        "competitor": competitor,
        "monitor_id": check.monitor_id,
        "monitor_check_id": check.id,
        "product_change_id": None,
        "kind": kind,
        "headline": _content_headline(competitor.name, page_kind, check.monitor),
        "summary": (
            f"The normalized page content changed and Sitemyra could not read a "
            f"specific field from it. Open the source to see what moved."
        ),
        "before": "",
        "after": "",
        "severity": "minor",
        "source_url": check.monitor.url,
        "detected_at": check.checked_at,
        "evidence": {
            "content_hash": check.content_hash[:16],
            "response_time_ms": check.response_time_ms,
            "page_kind": page_kind,
        },
        "_icon": icon_for(kind),
        "_model": SignalEvent,
    }


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------


def _page_kind_for_monitor(monitor, analysis_cache):
    from ..models import DiscoveredTarget

    if monitor.id in analysis_cache:
        return analysis_cache[monitor.id]
    target = (
        DiscoveredTarget.objects.filter(url=monitor.url, is_primary=True)
        .order_by("-created_at")
        .values_list("kind", flat=True)
        .first()
    )
    if target is None:
        target = (
            DiscoveredTarget.objects.filter(url=monitor.url)
            .order_by("-created_at")
            .values_list("kind", flat=True)
            .first()
        )
    kind = target or "other"
    analysis_cache[monitor.id] = kind
    return kind


@transaction.atomic
def persist_payloads(payloads):
    """Insert feed rows, skipping any whose source_key already exists.

    Returns ``(created, skipped)``. Duplicate keys are the normal case on a
    re-run, not an error.
    """
    if not payloads:
        return 0, 0
    model = payloads[0]["_model"]
    keys = [payload["source_key"] for payload in payloads]
    existing = set(
        model.objects.filter(source_key__in=keys).values_list("source_key", flat=True)
    )
    fresh = []
    skipped = 0
    seen = set()
    for payload in payloads:
        key = payload["source_key"]
        if key in existing or key in seen:
            skipped += 1
            continue
        seen.add(key)
        row = {
            field: value
            for field, value in payload.items()
            if not field.startswith("_") and field != "monitor_id"
        }
        row["monitor_id"] = payload["monitor_id"]
        fresh.append(model(**row))
    if fresh:
        model.objects.bulk_create(fresh, ignore_conflicts=True)
    return len(fresh), skipped


def derive_signals(limit_checks: int = 2000, limit_changes: int = 2000):
    """Turn recently recorded changes into feed rows. Idempotent.

    Called from Celery beat every 15 minutes and available as a staff
    trigger. Returns a small summary dict.
    """
    from monitors.models import ChangeDiff, Monitor, MonitorCheck

    from ..models import ProductChange

    now = timezone.now()
    summary = {"feed_created": 0, "feed_skipped": 0, "competitors": 0, "signals": 0}

    # How far back to look: a few minutes of overlap with the last run so a
    # tick that lands mid-check does not skip a row.
    watermark = ProductChange.objects.aggregate(Max("created_at"))["created_at__max"]
    since = (watermark - timezone.timedelta(minutes=30)) if watermark else (now - timezone.timedelta(days=1))

    changes = list(
        ProductChange.objects.filter(created_at__gte=since)
        .select_related("product_watch__monitor", "product_watch__monitor__user")
        .order_by("created_at")[:limit_changes]
    )
    check_watermark = MonitorCheck.objects.filter(changed=True).aggregate(
        Max("checked_at")
    )["checked_at__max"]
    check_since = (
        (check_watermark - timezone.timedelta(minutes=30))
        if check_watermark
        else (now - timezone.timedelta(days=1))
    )
    changed_checks = list(
        MonitorCheck.objects.filter(changed=True, checked_at__gte=check_since, error="")
        .select_related("monitor", "monitor__user")
        .order_by("checked_at")[:limit_checks]
    )

    if not changes and not changed_checks:
        return summary

    monitors = {change.product_watch.monitor for change in changes if change.product_watch_id}
    monitors.update(check.monitor for check in changed_checks)
    monitors = [monitor for monitor in monitors if monitor is not None]

    page_kinds = {}
    for monitor in monitors:
        page_kinds[monitor.id] = _page_kind_for_monitor(monitor, page_kinds)

    competitor_by_monitor = {}
    for monitor in monitors:
        competitor, _created = competitor_service.ensure_competitor_for_monitor(monitor)
        if competitor is not None:
            competitor_by_monitor[monitor.id] = competitor
    summary["competitors"] = len({c.id for c in competitor_by_monitor.values()})

    payloads = []
    touched = {}
    for change in changes:
        watch = getattr(change, "product_watch", None)
        if watch is None:
            continue
        competitor = competitor_by_monitor.get(watch.monitor_id)
        payload = derive_from_product_change(
            change, competitor, page_kinds.get(watch.monitor_id, "")
        )
        if payload:
            payloads.append(payload)
            touched[competitor.id] = change.created_at

    # Only emit a content signal for a check that produced no product
    # change, so one competitor move is not reported twice.
    checks_with_product_changes = {
        change.monitor_check_id for change in changes if change.monitor_check_id
    }
    for check in changed_checks:
        if check.id in checks_with_product_changes:
            continue
        competitor = competitor_by_monitor.get(check.monitor_id)
        payload = derive_from_changed_check(
            check, competitor, page_kinds.get(check.monitor_id, "other")
        )
        if payload:
            payloads.append(payload)
            touched[competitor.id] = check.checked_at

    created, skipped = persist_payloads(payloads)
    summary["feed_created"] = created
    summary["feed_skipped"] = skipped

    for competitor_id, when in touched.items():
        competitor = next(
            (c for c in competitor_by_monitor.values() if c.id == competitor_id), None
        )
        competitor_service.record_activity(competitor, when)

    logger.info(
        "intelligence derived feed events [created=%d skipped=%d competitors=%d]",
        created, skipped, summary["competitors"],
    )
    return summary
