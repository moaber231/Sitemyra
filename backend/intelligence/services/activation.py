"""Activating an analysis into monitors — the "Monitor everything" button.

Turns a stored :class:`~intelligence.models.UrlAnalysis` into real
``Monitor`` rows (plus a ``ProductWatch`` where the page is a product),
respecting every existing plan limit and tenant rule.

Deliberate decisions, documented because they affect perceived speed:

* **Plan limits clamp, they do not fail.** If a recipe would build 14
  monitors and the plan allows 3, we create 3 and report the rest with a
  reason. A 429 on a one-click button is a bad product experience.
* **At most two first checks are published immediately.** The remaining
  monitors are picked up by the existing 60-second scheduler tick. A
  20-monitor activation must not fire 20 simultaneous outbound requests.
* **Duplicates are detected, not created.** If the URL is already
  monitored by this user, the existing monitor is returned instead.
* **Only ``http`` monitors are created.** The structured extraction runs
  on the bytes the HTTP worker already downloads, so a product watch
  costs no extra request. Visual (browser-worker) monitors are left to the
  existing advanced-mode UI.
"""

import logging

from django.db import transaction
from django.utils import timezone

from billing.models import get_plan_for_user, plan_limits
from workspaces.permissions import require_role

from monitors.models import Monitor

from .targets import target_value
from .urls import normalize_url

logger = logging.getLogger(__name__)

# How many first checks are published immediately on activation. The rest
# are scheduled normally and picked up by the scheduler tick.
IMMEDIATE_FIRST_CHECK_LIMIT = 2

DEFAULT_CHECK_INTERVAL = 3600
MIN_TIMEOUT_SECONDS = 15

# Reasons a target is not created. Returned to the UI verbatim.
REASON_LIMIT = "plan_limit"
REASON_DUPLICATE = "already_monitored"
REASON_INVALID = "invalid_url"
REASON_NO_WORKSPACE = "workspace_forbidden"


def _monitor_name(target, host: str) -> str:
    label = str(target_value(target, "label", "") or "Page").strip()
    name = f"{host} — {label}" if host else label
    return name[:150]


def _clamp_interval(requested, plan) -> int:
    """Clamp to the plan's minimum and to a supported interval choice."""
    limits = plan_limits(plan)
    minimum = int(limits.get("min_interval_seconds") or 60)
    allowed = {choice for choice, _label in Monitor.INTERVAL_CHOICES}
    candidates = sorted(choice for choice in allowed if choice >= minimum)
    if not candidates:
        return max(minimum, DEFAULT_CHECK_INTERVAL)
    if requested:
        try:
            wanted = int(requested)
        except (TypeError, ValueError):
            wanted = DEFAULT_CHECK_INTERVAL
        if wanted < minimum:
            wanted = minimum
        nearest = min(candidates, key=lambda choice: (abs(choice - wanted), choice))
        return nearest
    return candidates[0] if candidates else max(minimum, DEFAULT_CHECK_INTERVAL)


def existing_monitor_ids(user, urls):
    """Existing monitor ids for the given normalized URLs (owned by user)."""
    if not urls:
        return {}
    matches = {}
    for monitor in Monitor.objects.filter(user=user, url__in=list(urls)).values("id", "url"):
        matches[normalize_url(monitor["url"])] = str(monitor["id"])
    return matches


def activate(
    user,
    analysis,
    targets=None,
    recipe=None,
    workspace=None,
    check_interval=None,
    publish_first_checks: bool = True,
):
    """Create monitors for the selected targets of an analysis.

    Returns a dict describing what was created, what was skipped and why,
    and the plan that applied. Never raises for plan/validation problems.
    """
    from ..models import ProductWatch
    from . import recipes as recipe_registry

    plan = get_plan_for_user(user)
    limits = plan_limits(plan)
    max_monitors = int(limits.get("max_monitors") or 0)
    already_active = Monitor.objects.filter(user=user, active=True).count()
    capacity = max(0, max_monitors - already_active)

    if workspace is not None and not require_role(user, workspace, minimum="admin"):
        return {
            "monitors": [],
            "product_watches": [],
            "created": 0,
            "skipped": [],
            "limit_reached": False,
            "plan": plan,
            "error": "workspace_forbidden",
        }

    if recipe:
        selected = recipe_registry.select_targets(targets or [], recipe)
        interval = check_interval or recipe_registry.check_interval_for(recipe)
        wants_product = recipe_registry.wants_product_watch(recipe)
        recipe_slug = recipe_registry.get_recipe(recipe)["slug"]
    else:
        selected = list(targets or [])
        interval = check_interval
        wants_product = False
        recipe_slug = ""

    if not selected:
        return {
            "monitors": [],
            "product_watches": [],
            "created": 0,
            "skipped": [],
            "limit_reached": False,
            "plan": plan,
            "error": "no_targets",
        }

    # The submitted page first so the product watch (when requested) always
    # lands on the URL the user actually pasted.
    ordered = sorted(
        selected,
        key=lambda item: (
            0 if target_value(item, "is_primary", False) else 1,
            -int(target_value(item, "relevance", 0) or 0),
        ),
    )
    normalized_urls = [normalize_url(target_value(item, "url", "") or "") for item in ordered]
    duplicates = existing_monitor_ids(user, [url for url in normalized_urls if url])

    resolved_interval = _clamp_interval(interval, plan)
    host = ""
    created_monitors = []
    product_watches = []
    skipped = []
    limit_reached = False
    published = 0
    now = timezone.now()

    for target, normalized in zip(ordered, normalized_urls):
        label = target_value(target, "label", "") or "Page"
        raw_url = target_value(target, "url", "") or ""
        if not normalized:
            skipped.append({"url": raw_url, "label": label, "reason": REASON_INVALID})
            continue
        if not host:
            from .urls import display_host

            host = display_host(normalized)

        if normalized in duplicates:
            skipped.append(
                {
                    "url": normalized,
                    "label": label,
                    "reason": REASON_DUPLICATE,
                    "monitor_id": duplicates[normalized],
                }
            )
            continue

        if capacity <= 0:
            limit_reached = True
            skipped.append({"url": normalized, "label": label, "reason": REASON_LIMIT})
            continue

        with transaction.atomic():
            monitor = Monitor.objects.create(
                user=user,
                workspace=workspace,
                name=_monitor_name(target, host),
                url=normalized[:1000],
                active=True,
                check_interval=resolved_interval,
                timeout=MIN_TIMEOUT_SECONDS,
                next_check_at=now,
            )
            capacity -= 1

        created_monitors.append(monitor)

        if wants_product and target_value(target, "is_product", False):
            watch = ProductWatch.objects.create(
                monitor=monitor,
                name=str(label)[:250],
                product_detected=bool(analysis.product_detected and normalized == analysis.normalized_url),
                detection_note=(
                    "Product data detected during URL analysis."
                    if normalized == analysis.normalized_url
                    else "Waiting for this page's first check to read its product data."
                ),
                first_seen_at=None,
            )
            product_watches.append(watch)

    if publish_first_checks and created_monitors:
        from monitors.tasks import check_monitor

        for monitor in created_monitors[:IMMEDIATE_FIRST_CHECK_LIMIT]:
            try:
                check_monitor.delay(str(monitor.id))
                published += 1
            except Exception:
                # The monitor is created and scheduled; a broker hiccup only
                # delays its first check by one scheduler tick.
                logger.exception(
                    "intelligence activate publish isolated error [monitor_id=%s]",
                    monitor.id,
                )

    return {
        "monitors": created_monitors,
        "product_watches": product_watches,
        "created": len(created_monitors),
        "skipped": skipped,
        "limit_reached": limit_reached,
        "plan": plan,
        "plan_limit": max_monitors,
        "check_interval": resolved_interval,
        "recipe": recipe_slug,
        "published_first_checks": published,
    }
