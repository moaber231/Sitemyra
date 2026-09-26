"""Product capture — turn one monitoring check into product history.

This module is called from ``monitors.tasks.check_monitor`` with the bytes
the HTTP worker **already downloaded** for the content hash. Nothing here
issues a request, opens a browser, or touches a queue.

It is also the only place that writes ``ProductSnapshot`` /
``ProductChange`` rows, and it is written to be idempotent per check: a
retried Celery task for the same check updates the existing snapshot
rather than duplicating history.
"""

import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.utils import timezone

from .page_facts import extract_page_facts
from .product_diff import (
    diff_snapshots,
    discount_percent,
    explain,
    severity_of,
    summarize,
)

logger = logging.getLogger(__name__)

# Facts from the extractor that map 1:1 onto snapshot columns.
_SNAPSHOT_FIELDS = (
    "name",
    "brand",
    "sku",
    "price",
    "list_price",
    "currency",
    "availability",
    "condition",
    "rating",
    "review_count",
    "description",
    "badges",
    "variants",
    "images",
    "bundles",
    "specs",
    "shipping",
    "price_valid_until",
)

_PRICE_MAX = Decimal("9999999999.99")
_RATING_MAX = Decimal("99.99")

_CURRENCY_CLEAN = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _clean_currency(value) -> str:
    if not value:
        return ""
    letters = "".join(character for character in str(value).upper() if character in _CURRENCY_CLEAN)
    return letters[:8]


def _clean_money(value):
    if value in (None, ""):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if amount < 0 or amount > _PRICE_MAX:
        return None
    try:
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None


def _clean_rating(value):
    if value in (None, ""):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if amount < 0 or amount > _RATING_MAX:
        return None
    try:
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None


def _clean_int(value):
    if value in (None, ""):
        return None
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return number


def _clean_text(value, limit: int) -> str:
    if value in (None, ""):
        return ""
    return str(value)[:limit]


def _clean_list(value, limit: int = 40):
    if value in (None, "", [], {}):
        return []
    if isinstance(value, dict):
        value = list(value)
    if not isinstance(value, (list, tuple)):
        value = [value]
    return [item for item in list(value)[:limit]]


def _clean_map(value, limit: int = 40):
    if not isinstance(value, dict):
        return {}
    return {str(key)[:80]: str(item)[:200] for key, item in list(value.items())[:limit]}


def snapshot_values(facts: dict) -> dict:
    """Map an extraction result onto snapshot column values.

    Out-of-range or unparseable values become ``None`` (field not
    observed) rather than raising — a product page is untrusted input.
    """
    values = {}
    for field in _SNAPSHOT_FIELDS:
        entry = facts.get(field) or {}
        raw_value = entry.get("value") if isinstance(entry, dict) else entry
        if field in ("price", "list_price"):
            values[field] = _clean_money(raw_value)
        elif field == "rating":
            values[field] = _clean_rating(raw_value)
        elif field == "review_count":
            values[field] = _clean_int(raw_value)
        elif field == "currency":
            values[field] = _clean_currency(raw_value)
        elif field in ("name", "brand", "sku", "availability", "condition", "price_valid_until"):
            values[field] = _clean_text(raw_value, 250 if field == "name" else 150)
        elif field == "description":
            values[field] = _clean_text(raw_value, 4000)
        elif field in ("badges", "variants", "images", "bundles"):
            values[field] = _clean_list(raw_value)
        elif field in ("specs", "shipping"):
            values[field] = _clean_map(raw_value)
        else:
            values[field] = raw_value
    return values


def facts_from_snapshot(snapshot) -> dict:
    """Rebuild the ``{field: {value, method, raw}}`` shape for diffing."""
    extraction = snapshot.extraction or {}
    evidence = snapshot.evidence or {}
    facts = {}
    for field in _SNAPSHOT_FIELDS:
        value = getattr(snapshot, field, None)
        if value is None:
            continue
        if isinstance(value, Decimal):
            value = format(value, "f")
        facts[field] = {
            "value": value,
            "method": (extraction or {}).get(field, ""),
            "raw": (evidence or {}).get(field, ""),
        }
    return facts


def _extraction_map(facts: dict) -> dict:
    return {
        field: (facts.get(field) or {}).get("method", "")
        for field in _SNAPSHOT_FIELDS
        if isinstance(facts.get(field), dict)
    }


def _evidence_map(facts: dict) -> dict:
    return {
        field: ((facts.get(field) or {}).get("raw", "") or "")[:400]
        for field in _SNAPSHOT_FIELDS
        if isinstance(facts.get(field), dict)
    }


def product_name_from_facts(facts: dict, fallback: str) -> str:
    name = (facts.get("name") or {}).get("value")
    if name:
        return str(name)[:250]
    return _clean_text(fallback, 250) or "Unnamed product"


def build_watch_from_facts(monitor, facts: dict) -> "object":
    """Create or update the ``ProductWatch`` for a monitor.

    The watch name follows the product's own published name so the UI and
    alerts read like the competitor's page, not like our internal id.
    """
    from ..models import ProductWatch

    watch, _created = ProductWatch.objects.get_or_create(
        monitor=monitor,
        defaults={
            "name": product_name_from_facts(facts, monitor.name),
            "brand": _clean_text((facts.get("brand") or {}).get("value"), 150),
            "currency": _clean_currency((facts.get("currency") or {}).get("value")),
            "product_detected": bool(facts.get("product_detected")),
            "detection_note": _detection_note(facts),
        },
    )
    changed = False
    name = product_name_from_facts(facts, watch.name)
    if name and name != watch.name:
        watch.name = name
        changed = True
    brand = _clean_text((facts.get("brand") or {}).get("value"), 150)
    if brand and brand != watch.brand:
        watch.brand = brand
        changed = True
    currency = _clean_currency((facts.get("currency") or {}).get("value"))
    if currency and currency != watch.currency:
        watch.currency = currency
        changed = True
    detected = bool(facts.get("product_detected"))
    if detected != watch.product_detected:
        watch.product_detected = detected
        changed = True
    note = _detection_note(facts)
    if note and note != watch.detection_note:
        watch.detection_note = note
        changed = True
    if changed:
        watch.save(
            update_fields=[
                "name",
                "brand",
                "currency",
                "product_detected",
                "detection_note",
                "updated_at",
            ]
        )
    return watch


def _detection_note(facts: dict) -> str:
    if facts.get("product_detected"):
        methods = ", ".join(facts.get("extraction_methods") or [])
        return f"Product data read from: {methods}." if methods else "Product data detected."
    if facts.get("price"):
        return (
            "A price was published on this page but no product structure was "
            "detected. Observations are recorded as unconfirmed."
        )
    return (
        "No product structure or price was detected on this page. "
        "Observations are recorded as unconfirmed."
    )


def capture(monitor, check, content, content_type: str = "", source_url: str = ""):
    """Record a product observation for one check.

    Returns a summary dict; it never raises. A failure here must not fail
    or delay the monitor check, so every error is caught and logged.
    """
    from ..models import ProductChange, ProductSnapshot

    summary = {
        "monitor_id": str(monitor.id),
        "product_watch": None,
        "snapshot_id": None,
        "changes": [],
        "status": "skipped",
    }
    try:
        watch = getattr(monitor, "product_watch", None)
        if watch is None:
            summary["status"] = "no_watch"
            return summary

        facts = extract_page_facts(content, content_type, monitor.url)
        captured_at = check.checked_at if check is not None else timezone.now()
        source = source_url or facts.get("canonical_url", {}).get("value") or monitor.url

        if not watch.first_seen_at:
            watch.first_seen_at = captured_at
        watch.last_seen_at = captured_at
        if not watch.currency:
            watch.currency = _clean_currency((facts.get("currency") or {}).get("value"))
        watch.save(
            update_fields=["first_seen_at", "last_seen_at", "currency", "updated_at"]
        )

        values = snapshot_values(facts)

        # Idempotency: one snapshot per (watch, check).
        existing = None
        if check is not None:
            existing = ProductSnapshot.objects.filter(
                product_watch=watch, monitor_check=check
            ).first()

        previous = None
        if existing is not None:
            previous = ProductSnapshot.objects.filter(
                product_watch=watch, id__lt=existing.id
            ).order_by("-captured_at").first()
        else:
            previous = (
                ProductSnapshot.objects.filter(product_watch=watch)
                .exclude(monitor_check=check)
                .order_by("-captured_at")
                .first()
            )
            if check is not None and previous is not None and previous.captured_at >= captured_at:
                previous = ProductSnapshot.objects.filter(product_watch=watch).order_by("-captured_at").first()

        current_facts = {
            field: {"value": values.get(field), "method": (facts.get(field) or {}).get("method", ""), "raw": (facts.get(field) or {}).get("raw", "")}
            for field in _SNAPSHOT_FIELDS
            if values.get(field) is not None
        }
        previous_facts = facts_from_snapshot(previous) if previous is not None else {}

        changes = diff_snapshots(
            previous_facts,
            current_facts,
            source_url=source,
            detected_at=captured_at,
        )

        snapshot_values_row = {
            "captured_at": captured_at,
            "monitor_check": check,
            "source_url": source[:1000],
            "extraction": _extraction_map(facts),
            "evidence": _evidence_map(facts),
            "changed_fields": [change["field"] for change in changes],
        }
        snapshot_values_row.update(values)

        if existing is not None:
            for key, value in snapshot_values_row.items():
                setattr(existing, key, value)
            existing.save()
            snapshot = existing
            ProductChange.objects.filter(current_snapshot=snapshot).delete()
        else:
            snapshot = ProductSnapshot.objects.create(
                product_watch=watch, **snapshot_values_row
            )

        for change in changes:
            ProductChange.objects.create(
                product_watch=watch,
                previous_snapshot=previous,
                current_snapshot=snapshot,
                monitor_check=check,
                field=change["field"],
                label=change["label"],
                before=change["before"],
                after=change["after"],
                severity=change["severity"],
                category=change["category"],
                basis=change["basis"],
                rule=change["rule"],
                source_url=source[:1000],
                evidence={
                    "methods": change.get("methods", {}),
                    "rule": change["rule"],
                    "source_url": source[:1000],
                    "detected_at": change.get("detected_at", ""),
                },
            )

        summary.update(
            {
                "product_watch": str(watch.id),
                "snapshot_id": str(snapshot.id),
                "changes": changes,
                "severity": severity_of(changes),
                "status": "captured",
                "first_observation": previous is None,
            }
        )
        return summary
    except Exception:
        logger.exception(
            "intelligence product capture isolated error [monitor_id=%s]",
            getattr(monitor, "id", "?"),
        )
        summary["status"] = "error"
        return summary


def latest_changes(watch, limit: int = 20):
    """The most recent field changes for a watch, newest first."""
    from ..models import ProductChange

    return list(
        ProductChange.objects.filter(product_watch=watch)
        .order_by("-created_at")[:limit]
    )


def build_explanation(watch, changes):
    """Explanation block for a set of persisted change rows."""
    payload = [
        {
            "field": row.field,
            "label": row.label,
            "before": row.before,
            "after": row.after,
            "severity": row.severity,
            "category": row.category,
            "rule": row.rule,
            "basis": row.basis,
            "source_url": row.source_url,
            "detected_at": row.created_at.isoformat() if row.created_at else "",
        }
        for row in changes
    ]
    return explain(payload, product_name=watch.name)


def describe_changes(watch, changes) -> str:
    currency = watch.currency or ""
    return summarize(
        [
            {
                "field": row.field,
                "label": row.label,
                "before": row.before,
                "after": row.after,
                "severity": row.severity,
                "category": row.category,
            }
            for row in changes
        ],
        currency=currency,
    )


def current_discount(snapshot):
    if snapshot is None:
        return None
    return discount_percent(snapshot.list_price, snapshot.price)
