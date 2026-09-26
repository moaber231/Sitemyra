"""The market feed and the competitor pulse board.

Two read models, both built on the indexed columns of ``SignalEvent``.

**Design rule: descriptive states, never scores.** A competitor is
"changed recently", "no significant change detected", "multiple changes
detected" or "pricing changed". It is never given a health, threat or
opportunity number, because nothing in public page data supports one and a
fabricated score would be the single most damaging thing this product
could do.

**Cursor pagination.** The feed is ordered by ``(detected_at, id)`` and
paginates on that pair, so a new event arriving mid-scroll can never
duplicate or skip a row the way an offset would.
"""

import logging

from django.db.models import Count, Max, Q
from django.utils import timezone

from .signals import icon_for

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 25
MAX_LIMIT = 100

# "Active" means "something happened in this window". It is a recency
# statement, not a judgement.
ACTIVE_WINDOW_DAYS = 30
MULTIPLE_CHANGES_THRESHOLD = 3


def _visible(user, queryset):
    from workspaces.models import WorkspaceMembership

    if user.is_superuser:
        return queryset
    workspace_ids = list(
        WorkspaceMembership.objects.filter(user=user).values_list("workspace_id", flat=True)
    ) + list(user.owned_workspaces.values_list("id", flat=True))
    workspace_ids = [value for value in workspace_ids if value]
    if workspace_ids:
        return queryset.filter(
            Q(user=user) | Q(workspace_id__in=workspace_ids)
        )
    return queryset.filter(user=user)


def feed_queryset(user, kind=None, competitor=None, severity=None, monitor=None, since=None):
    from ..models import SignalEvent

    queryset = _visible(user, SignalEvent.objects.all())
    if kind:
        kinds = [item.strip() for item in str(kind).split(",") if item.strip()]
        if kinds and "all" not in kinds:
            queryset = queryset.filter(kind__in=kinds)
    if severity:
        severities = [item.strip() for item in str(severity).split(",") if item.strip()]
        if severities and "all" not in severities:
            queryset = queryset.filter(severity__in=severities)
    if competitor:
        queryset = queryset.filter(competitor_id=competitor)
    if monitor:
        queryset = queryset.filter(monitor_id=monitor)
    if since:
        queryset = queryset.filter(detected_at__gte=since)
    return queryset.select_related("competitor", "monitor").order_by("-detected_at", "-id")


def _encode_cursor(row) -> str:
    return f"{row.detected_at.isoformat()}|{row.id}"


def _decode_cursor(cursor: str):
    from django.utils.dateparse import parse_datetime

    if not cursor:
        return None
    raw_detected, _, raw_id = str(cursor).partition("|")
    detected = parse_datetime(raw_detected)
    if detected is None or not raw_id:
        return None
    if timezone.is_naive(detected):
        detected = timezone.make_aware(detected, timezone.utc)
    return detected, raw_id


def get_feed(user, kind=None, competitor=None, severity=None, monitor=None, cursor=None, limit=None, since=None):
    """One page of the chronological feed plus a stable next cursor."""
    try:
        page_size = max(1, min(MAX_LIMIT, int(limit or DEFAULT_LIMIT)))
    except (TypeError, ValueError):
        page_size = DEFAULT_LIMIT

    queryset = feed_queryset(
        user, kind=kind, competitor=competitor, severity=severity, monitor=monitor, since=since
    )
    after = _decode_cursor(cursor)
    if after is not None:
        detected, last_id = after
        queryset = queryset.filter(
            Q(detected_at__lt=detected)
            | Q(detected_at=detected, id__lt=last_id)
        )

    rows = list(queryset[: page_size + 1])
    has_more = len(rows) > page_size
    rows = rows[:page_size]
    return {
        "results": [serialize_event(row) for row in rows],
        "count": len(rows),
        "has_more": has_more,
        "next_cursor": _encode_cursor(rows[-1]) if has_more and rows else None,
    }


def serialize_event(row) -> dict:
    competitor = getattr(row, "competitor", None)
    return {
        "id": str(row.id),
        "kind": row.kind,
        "icon": icon_for(row.kind),
        "headline": row.headline,
        "summary": row.summary,
        "before": row.before,
        "after": row.after,
        "severity": row.severity,
        "source_url": row.source_url,
        "detected_at": row.detected_at,
        "competitor_id": str(competitor.id) if competitor else None,
        "competitor_name": competitor.name if competitor else None,
        "monitor_id": str(row.monitor_id) if row.monitor_id else None,
        "monitor_name": row.monitor.name if row.monitor_id else None,
        "product_change_id": str(row.product_change_id) if row.product_change_id else None,
        "monitor_check_id": str(row.monitor_check_id) if row.monitor_check_id else None,
        "evidence": row.evidence or {},
        "has_evidence": bool(row.product_change_id or row.monitor_check_id),
    }


# --------------------------------------------------------------------------
# Pulse
# --------------------------------------------------------------------------


def pulse_for_competitor(competitor, window_days: int = ACTIVE_WINDOW_DAYS, now=None):
    """Descriptive state for one competitor over a time window.

    Every value returned is countable from the feed. There is no score, no
    rating and no ranking.
    """
    from ..models import SignalEvent

    now = now or timezone.now()
    since = now - timezone.timedelta(days=window_days)
    events = SignalEvent.objects.filter(
        competitor=competitor, detected_at__gte=since
    )
    total = events.count()
    by_kind = {
        row["kind"]: row["total"]
        for row in events.values("kind").annotate(total=Count("id"))
    }
    by_severity = {
        row["severity"]: row["total"]
        for row in events.values("severity").annotate(total=Count("id"))
    }
    last = events.aggregate(Max("detected_at"))["detected_at__max"]

    has_product_watch = _has_product_watch(competitor)
    monitor_count = _monitor_count(competitor)

    states = []
    if total == 0:
        states.append("no_significant_change_detected")
    elif total >= MULTIPLE_CHANGES_THRESHOLD:
        states.append("multiple_changes_detected")
    else:
        states.append("changed_recently")
    if by_kind.get("pricing"):
        states.append("pricing_changed")
    if by_kind.get("products"):
        states.append("product_change_detected")
    if by_kind.get("features"):
        states.append("feature_change_detected")
    if by_kind.get("hiring"):
        states.append("hiring_change_detected")
    if by_kind.get("marketing"):
        states.append("marketing_change_detected")

    # The "most active area" is a plain count, not a judgement.
    dominant = max(by_kind.items(), key=lambda item: item[1])[0] if by_kind else ""

    return {
        "competitor_id": str(competitor.id),
        "name": competitor.name,
        "domain": competitor.domain,
        "homepage_url": competitor.homepage_url,
        "relationship": competitor.relationship,
        "relationship_reasons": competitor.relationship_reasons or [],
        "signals": competitor.signals or [],
        "states": states,
        "state_label": _state_label(states, total),
        "window_days": window_days,
        "events_in_window": total,
        "events_by_kind": by_kind,
        "events_by_severity": by_severity,
        "dominant_kind": dominant,
        "last_activity_at": last or competitor.last_activity_at,
        "monitor_count": monitor_count,
        "tracks_product": has_product_watch,
        "first_seen_at": competitor.first_seen_at,
    }


_STATE_LABELS = {
    "no_significant_change_detected": "No significant change detected",
    "changed_recently": "Changed recently",
    "multiple_changes_detected": "Multiple changes detected",
    "pricing_changed": "Pricing changed",
    "product_change_detected": "New product detected",
    "feature_change_detected": "Feature change detected",
    "hiring_change_detected": "Hiring change detected",
    "marketing_change_detected": "Marketing change detected",
}


def _state_label(states, total):
    if total == 0:
        return _STATE_LABELS["no_significant_change_detected"]
    for key in (
        "multiple_changes_detected",
        "changed_recently",
        "pricing_changed",
        "product_change_detected",
        "feature_change_detected",
        "hiring_change_detected",
        "marketing_change_detected",
    ):
        if key in states:
            return _STATE_LABELS[key]
    return _STATE_LABELS["changed_recently"]


def _has_product_watch(competitor) -> bool:
    from ..models import ProductWatch

    return ProductWatch.objects.filter(monitor__user=competitor.user, monitor__url__icontains=competitor.domain).exists()


def _monitor_count(competitor) -> int:
    from ..models import Competitor  # noqa: F401  (documented dependency)
    from monitors.models import Monitor

    from .urls import registrable_domain

    # Counted in Python over the user's own monitors because the domain is
    # stored on the Competitor, not denormalized onto every Monitor. Bounded
    # by a user's monitor count (max 100 on Business).
    ids = []
    for monitor in Monitor.objects.filter(user=competitor.user).only("id", "url"):
        domain = registrable_domain(monitor.url)
        if domain and domain == competitor.domain:
            ids.append(monitor.id)
    return len(ids)


def get_pulse(user, window_days: int = ACTIVE_WINDOW_DAYS):
    """Pulse board for every competitor the user can see."""
    from ..models import Competitor

    competitors = list(
        _visible(user, Competitor.objects.all()).order_by("-last_activity_at", "name")
    )
    return {
        "window_days": window_days,
        "competitors": [
            pulse_for_competitor(competitor, window_days=window_days)
            for competitor in competitors
        ],
        "totals": {
            "competitors": len(competitors),
            "with_activity": sum(
                1
                for competitor in competitors
                if (competitor.last_activity_at is not None)
            ),
        },
    }


def competitor_summary(user):
    """Compact overview for the dashboard home page."""
    from ..models import Competitor, SignalEvent

    competitors = _visible(user, Competitor.objects.all())
    total_competitors = competitors.count()
    with_activity = competitors.filter(
        last_activity_at__gte=timezone.now() - timezone.timedelta(days=ACTIVE_WINDOW_DAYS)
    ).count()
    week_ago = timezone.now() - timezone.timedelta(days=7)
    return {
        "competitors": total_competitors,
        "active_competitors": with_activity,
        "events_7d": _visible(user, SignalEvent.objects.all()).filter(
            detected_at__gte=week_ago
        ).count(),
        "events_24h": _visible(user, SignalEvent.objects.all()).filter(
            detected_at__gte=timezone.now() - timezone.timedelta(days=1)
        ).count(),
    }
