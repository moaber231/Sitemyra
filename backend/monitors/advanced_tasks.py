from decimal import Decimal

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from .models import (
    AdvancedMonitorConfig,
    ChangeDiff,
    Monitor,
    MonitorCheck,
    PricePoint,
)
from .services.artifacts import save_artifact
from .services.browser_fetcher import (
    BrowserFetchError,
    fetch_with_browser,
)
from .services.dom_diff import (
    content_hash,
    normalize_html,
)
from .services.price_extractor import extract_price
from .services.screenshot_diff import compare_screenshots


def _notify_advanced(monitor, check, event_type):
    """Hand the event to the notifications queue (plan D7).

    Detection stays here; SMTP/webhook delivery runs on the
    celery_notifications worker — never inside a browser check.
    Development/tests execute Celery eagerly, so local behaviour stays
    synchronous. Never breaks the monitor task.
    """
    try:
        from notifications.tasks import deliver_monitor_event

        deliver_monitor_event.delay(
            str(monitor.id),
            str(check.id),
            event_type,
        )
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "advanced monitor notify isolated error [monitor_id=%s]",
            monitor.id,
        )


def _advanced_previous_check_was_failure(monitor):
    previous = (
        MonitorCheck.objects
        .filter(monitor=monitor)
        .order_by("-checked_at")
        .first()
    )
    return previous, bool(previous and previous.error)


def _record_advanced_failure(monitor, error_message: str) -> dict:
    """Persist a failed check — the single failure path.

    Used for non-retryable fetch errors (HTTP 4xx, blocked destinations,
    timeouts classified non-retryable) AND for config errors (DOM/price
    selector mismatch, screenshot height cap): the MonitorCheck row, the
    monitor state reset and the deduped failure notification are exactly
    the same no matter which stage failed — the failure is always
    recorded and state is never left half-written (Phase D error
    handling: no unhandled ValueError can escape this task anymore).
    """
    previous, was_failing = _advanced_previous_check_was_failure(monitor)

    with transaction.atomic():
        checked_at = timezone.now()
        check = MonitorCheck.objects.create(
            monitor=monitor,
            checked_at=checked_at,
            status_code=None,
            response_time_ms=None,
            content_hash="",
            changed=False,
            error=error_message,
        )

        monitor.last_checked_at = checked_at
        monitor.last_success_at = None
        monitor.last_content_hash = ""
        monitor.last_status_code = None
        monitor.next_check_at = checked_at + timedelta(
            seconds=monitor.check_interval
        )
        monitor.save(
            update_fields=[
                "last_checked_at",
                "last_success_at",
                "last_content_hash",
                "last_status_code",
                "next_check_at",
            ]
        )

    if not was_failing:
        _notify_advanced(monitor, check, "failure")

    return {
        "monitor_id": str(monitor.id),
        "check_id": str(check.id),
        "status": "failed",
        "error": error_message,
    }


@shared_task(
    bind=True,
    max_retries=5,
    # Browser checks run on the dedicated browser worker only; limits are
    # env-tunable and always above the inner per-check navigation timeout
    # so the Celery hard limit stays the final kill switch (Phase A).
    soft_time_limit=settings.BROWSER_TASK_SOFT_TIME_LIMIT,
    time_limit=settings.BROWSER_TASK_TIME_LIMIT,
)
def run_advanced_monitor(
    self,
    monitor_id,
):
    monitor = (
        Monitor.objects
        .select_related(
            "user",
            "advanced_config",
        )
        .get(
            id=monitor_id,
            active=True,
        )
    )

    config = monitor.advanced_config

    if config.mode == AdvancedMonitorConfig.HTTP:
        return {
            "monitor_id": str(monitor.id),
            "status": "delegated",
        }

    try:
        result = fetch_with_browser(
            monitor.url,
            timeout_seconds=monitor.timeout,
            mode=config.mode,
        )
    except BrowserFetchError as exc:
        if exc.retryable:
            raise self.retry(
                exc=exc,
                countdown=min(
                    60 * (2 ** self.request.retries),
                    900,
                ),
            )

        return _record_advanced_failure(monitor, str(exc))

    # ---- Stage 1: pure computation (no DB, no artifacts) ----------------
    # Selector problems are monitor CONFIG errors (page has no matching
    # element): record a failed check instead of crashing the task.
    try:
        normalized = normalize_html(
            result.html,
            selector=config.selector,
        )
    except ValueError as exc:
        return _record_advanced_failure(
            monitor,
            f"DOM selector error: {exc}",
        )

    current_hash = content_hash(normalized)

    previous = (
        MonitorCheck.objects
        .filter(monitor=monitor)
        .order_by("-checked_at")
        .first()
    )
    was_failing = bool(previous and previous.error)

    changed = (
        previous is not None
        and previous.content_hash != current_hash
    )

    price_data = None
    previous_price = None
    if config.mode == AdvancedMonitorConfig.PRICE:
        try:
            price_data = extract_price(
                result.html,
                config.price_selector,
                config.price_currency,
            )
        except ValueError as exc:
            return _record_advanced_failure(
                monitor,
                f"Price selector error: {exc}",
            )

        if previous is not None:
            previous_price_point = getattr(
                previous,
                "price_point",
                None,
            )
            if previous_price_point:
                previous_price = previous_price_point.price

    price = currency = raw_value = None
    if price_data is not None:
        price, currency, raw_value = price_data

    price_changed = (
        price_data is not None
        and previous_price is not None
        and previous_price != price
    )

    # The check id is assigned now so artifact keys can be written before
    # the DB row exists (write-object-then-row ordering).
    checked_at = timezone.now()
    check = MonitorCheck(
        monitor=monitor,
        checked_at=checked_at,
        status_code=result.status_code,
        response_time_ms=result.response_time_ms,
        content_hash=current_hash,
        changed=changed,
        error="",
    )

    # ---- Stage 2: artifact objects + image IO (STILL outside atomic) ----
    # Phase invariant: nothing image-based or filesystem-based runs inside
    # transaction.atomic() — a failed/rolled-back transaction can only
    # leave an orphan OBJECT (removed by the retention sweeper), never a
    # DB row pointing at a missing object.
    html_key = ""
    if changed:
        # Unchanged content: skip the write entirely so it is never an
        # orphan (objects are only written when a row will reference them).
        html_key = save_artifact(
            monitor.id,
            check.id,
            normalized.encode("utf-8"),
            "html",
        )

    screenshot_changed = False
    screenshot_initial = False
    screenshot_key = ""
    screenshot_percentage = Decimal("100.0000")

    if config.mode == AdvancedMonitorConfig.SCREENSHOT:
        import os
        import tempfile

        from .services.artifacts import load_artifact

        previous_artifact = None
        if previous is not None:
            previous_artifact = (
                ChangeDiff.objects
                .filter(
                    monitor=monitor,
                    current_check=previous,
                    diff_type=ChangeDiff.SCREENSHOT,
                )
                .order_by("-created_at")
                .first()
            )

        with tempfile.TemporaryDirectory() as tmp:
            if previous is None:
                # First capture: the initial-diff row below references it.
                screenshot_initial = True
                screenshot_key = save_artifact(
                    monitor.id,
                    check.id,
                    result.screenshot,
                    "png",
                )
            elif previous_artifact is not None and previous_artifact.artifact_path:
                current_path = os.path.join(tmp, "current.png")
                previous_path = os.path.join(tmp, "previous.png")
                diff_path = os.path.join(tmp, "diff.png")

                with open(current_path, "wb") as fh:
                    fh.write(result.screenshot)
                with open(previous_path, "wb") as fh:
                    fh.write(
                        load_artifact(
                            previous_artifact.artifact_path
                        )
                    )

                # Image decode/pixelmatch/diff-write: all here, all
                # outside the DB transaction.
                comparison = compare_screenshots(
                    previous_path,
                    current_path,
                    diff_path,
                    float(config.screenshot_threshold),
                )

                if comparison["changed"]:
                    screenshot_changed = True
                    screenshot_percentage = Decimal(
                        str(comparison["percentage"])
                    )
                    if os.path.exists(diff_path):
                        with open(diff_path, "rb") as fh:
                            diff_bytes = fh.read()
                        screenshot_key = save_artifact(
                            monitor.id,
                            check.id,
                            diff_bytes,
                            "png",
                        )
                    else:
                        # Size-mismatch path: no diff image rendered;
                        # the current screenshot is stored instead.
                        screenshot_key = save_artifact(
                            monitor.id,
                            check.id,
                            result.screenshot,
                            "png",
                        )
                # Unchanged (or no baseline): no object written, no row —
                # artifacts are only written when referenced.

    # ---- Stage 3: the ONLY transactional block: DB rows -----------------
    with transaction.atomic():
        check.save()

        monitor.last_checked_at = checked_at
        monitor.last_success_at = checked_at
        monitor.last_content_hash = current_hash
        monitor.last_status_code = result.status_code

        if changed:
            monitor.last_changed_at = checked_at

        monitor.save(
            update_fields=[
                "last_checked_at",
                "last_success_at",
                "last_content_hash",
                "last_status_code",
                "last_changed_at",
            ]
        )

        if changed:
            ChangeDiff.objects.create(
                monitor=monitor,
                previous_check=previous,
                current_check=check,
                diff_type=ChangeDiff.DOM,
                summary="Normalized page content changed.",
                diff_percentage=Decimal("100.0000"),
                artifact_path=html_key,
            )

        if screenshot_initial:
            ChangeDiff.objects.create(
                monitor=monitor,
                previous_check=check,
                current_check=check,
                diff_type=ChangeDiff.SCREENSHOT,
                summary="Initial screenshot captured.",
                diff_percentage=Decimal("100.0000"),
                artifact_path=screenshot_key,
            )
        elif screenshot_changed:
            ChangeDiff.objects.create(
                monitor=monitor,
                previous_check=previous,
                current_check=check,
                diff_type=ChangeDiff.SCREENSHOT,
                summary="Visual screenshot changed.",
                diff_percentage=screenshot_percentage,
                artifact_path=screenshot_key,
            )

        if price_data is not None:
            PricePoint.objects.create(
                monitor=monitor,
                monitor_check=check,
                price=price,
                currency=currency,
                raw_value=raw_value,
            )

            if price_changed:
                ChangeDiff.objects.create(
                    monitor=monitor,
                    previous_check=previous,
                    current_check=check,
                    diff_type=ChangeDiff.PRICE,
                    summary=(
                        f"Price changed from "
                        f"{previous_price} to {price} {currency}."
                    ),
                    diff_percentage=Decimal("100.0000"),
                    artifact_path="",
                )

    # Central notifications — same behavior as the HTTP/content engine:
    # change for the engine's own signal, recovery when a failure streak ends.
    if config.mode == AdvancedMonitorConfig.DOM and changed:
        _notify_advanced(monitor, check, "change")
    elif config.mode == AdvancedMonitorConfig.SCREENSHOT and screenshot_changed:
        _notify_advanced(monitor, check, "change")
    elif config.mode == AdvancedMonitorConfig.PRICE and price_changed:
        _notify_advanced(monitor, check, "change")

    if was_failing:
        _notify_advanced(monitor, check, "recovery")

    return {
        "monitor_id": str(monitor.id),
        "check_id": str(check.id),
        "changed": changed,
        "mode": config.mode,
        "status": "success",
    }
