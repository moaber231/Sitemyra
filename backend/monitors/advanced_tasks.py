from decimal import Decimal

from celery import shared_task
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
    """Route advanced-engine events through the central dispatcher.

    Detection stays here; delivery lives in notifications.services.
    Never breaks the monitor task.
    """
    try:
        from notifications.services import dispatch_monitor_event

        dispatch_monitor_event(monitor, check, event_type)
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


@shared_task(
    bind=True,
    max_retries=5,
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
                error=str(exc),
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
            "error": str(exc),
        }

    normalized = normalize_html(
        result.html,
        selector=config.selector,
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

    screenshot_changed = False
    price_changed = False

    with transaction.atomic():
        checked_at = timezone.now()
        check = MonitorCheck.objects.create(
            monitor=monitor,
            checked_at=checked_at,
            status_code=result.status_code,
            response_time_ms=result.response_time_ms,
            content_hash=current_hash,
            changed=changed,
            error="",
        )

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

        html_path = save_artifact(
            monitor.id,
            check.id,
            normalized.encode("utf-8"),
            "html",
        )

        if changed:
            ChangeDiff.objects.create(
                monitor=monitor,
                previous_check=previous,
                current_check=check,
                diff_type=ChangeDiff.DOM,
                summary="Normalized page content changed.",
                diff_percentage=Decimal("100.0000"),
                artifact_path=html_path,
            )

        if config.mode == AdvancedMonitorConfig.SCREENSHOT:
            from .services.artifacts import load_artifact

            current_screenshot_key = save_artifact(
                monitor.id,
                check.id,
                result.screenshot,
                "png",
            )

            if previous:
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

                if previous_artifact and previous_artifact.artifact_path:
                    import os
                    import tempfile

                    comparison = {"changed": False, "percentage": 0.0}
                    diff_bytes = None
                    with tempfile.TemporaryDirectory() as tmp:
                        prev_path = os.path.join(tmp, "previous.png")
                        cur_path = os.path.join(tmp, "current.png")
                        diff_path = os.path.join(tmp, "diff.png")
                        with open(prev_path, "wb") as fh:
                            fh.write(
                                load_artifact(
                                    previous_artifact.artifact_path
                                )
                            )
                        with open(cur_path, "wb") as fh:
                            fh.write(result.screenshot)

                        comparison = compare_screenshots(
                            prev_path,
                            cur_path,
                            diff_path,
                            float(config.screenshot_threshold),
                        )
                        if comparison["changed"] and os.path.exists(diff_path):
                            with open(diff_path, "rb") as fh:
                                diff_bytes = fh.read()

                    if comparison["changed"]:
                        screenshot_changed = True
                        if diff_bytes is not None:
                            artifact_key = save_artifact(
                                monitor.id,
                                check.id,
                                diff_bytes,
                                "png",
                            )
                        else:
                            # Size-mismatch path: no diff image rendered;
                            # reference the current screenshot instead.
                            artifact_key = current_screenshot_key
                        ChangeDiff.objects.create(
                            monitor=monitor,
                            previous_check=previous,
                            current_check=check,
                            diff_type=ChangeDiff.SCREENSHOT,
                            summary="Visual screenshot changed.",
                            diff_percentage=Decimal(
                                str(comparison["percentage"])
                            ),
                            artifact_path=artifact_key,
                        )

            else:
                ChangeDiff.objects.create(
                    monitor=monitor,
                    previous_check=check,
                    current_check=check,
                    diff_type=ChangeDiff.SCREENSHOT,
                    summary="Initial screenshot captured.",
                    diff_percentage=Decimal("100.0000"),
                    artifact_path=current_screenshot_key,
                )

        if config.mode == AdvancedMonitorConfig.PRICE:
            price, currency, raw_value = extract_price(
                result.html,
                config.price_selector,
                config.price_currency,
            )

            PricePoint.objects.create(
                monitor=monitor,
                monitor_check=check,
                price=price,
                currency=currency,
                raw_value=raw_value,
            )

            previous_price = None

            if previous:
                previous_price_point = getattr(
                    previous,
                    "price_point",
                    None,
                )
                if previous_price_point:
                    previous_price = previous_price_point.price

            if (
                previous_price is not None
                and previous_price != price
            ):
                price_changed = True
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
