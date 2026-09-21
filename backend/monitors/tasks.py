from datetime import timedelta
from pathlib import Path

from celery import shared_task
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from notifications.services import dispatch_monitor_event

from .models import AdvancedMonitorConfig, Monitor, MonitorCheck
from .services.change_detector import detect_change
from .services.fetcher import FetchError, SecurityError, fetch_url
from .services.normalizer import content_hash


@shared_task
def schedule_due_monitors():
    now = timezone.now()
    monitor_ids = list(
        Monitor.objects.filter(
            active=True,
            next_check_at__lte=now,
        ).values_list("id", flat=True)
    )

    scheduled = 0

    for monitor_id in monitor_ids:
        with transaction.atomic():
            monitor = (
                Monitor.objects
                .select_for_update()
                .filter(
                    id=monitor_id,
                    active=True,
                    next_check_at__lte=now,
                )
                .first()
            )

            if not monitor:
                continue

            monitor.next_check_at = now + timedelta(
                seconds=monitor.check_interval
            )
            monitor.save(
                update_fields=["next_check_at", "updated_at"]
            )

        dispatch_monitor_check.delay(str(monitor.id))
        scheduled += 1

    return scheduled


def _previous_check_was_failure(monitor):
    previous = (
        monitor.checks
        .order_by("-checked_at")
        .first()
    )
    return bool(previous and previous.error)


def _notify(monitor, check, event_type):
    """Central notification path — never breaks the monitor task."""
    try:
        dispatch_monitor_event(monitor, check, event_type)
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "monitor notify isolated error [monitor_id=%s]", monitor.id
        )


def _record_failure(monitor, checked_at, error):
    was_failing = _previous_check_was_failure(monitor)

    monitor.last_checked_at = checked_at
    monitor.next_check_at = checked_at + timedelta(
        seconds=monitor.check_interval
    )
    monitor.save(
        update_fields=[
            "last_checked_at",
            "next_check_at",
            "updated_at",
        ]
    )

    check = MonitorCheck.objects.create(
        monitor=monitor,
        checked_at=checked_at,
        error=str(error),
        changed=False,
    )

    if not was_failing:
        _notify(monitor, check, "failure")


@shared_task(bind=True)
def check_monitor(self, monitor_id):
    try:
        monitor = Monitor.objects.get(id=monitor_id)
    except Monitor.DoesNotExist:
        return {"status": "skipped", "reason": "not_found"}

    if not monitor.active:
        return {"status": "skipped", "reason": "inactive"}

    was_failing = _previous_check_was_failure(monitor)
    checked_at = timezone.now()

    try:
        result = fetch_url(
            str(monitor.url),
            timeout_seconds=monitor.timeout,
        )
    except (SecurityError, FetchError) as exc:
        _record_failure(monitor, checked_at, exc)
        return {"status": "failed", "error": str(exc)}
    except Exception:
        _record_failure(
            monitor,
            checked_at,
            "Unexpected monitoring error.",
        )
        raise

    current_hash = content_hash(
        result.content,
        result.content_type,
    )

    changed = detect_change(
        monitor.last_content_hash,
        current_hash,
    )

    check = MonitorCheck.objects.create(
        monitor=monitor,
        checked_at=checked_at,
        status_code=result.status_code,
        response_time_ms=result.response_time_ms,
        content_hash=current_hash,
        changed=changed,
    )

    monitor.last_checked_at = checked_at
    monitor.last_success_at = checked_at
    monitor.last_status_code = result.status_code
    monitor.next_check_at = checked_at + timedelta(
        seconds=monitor.check_interval
    )

    update_fields = [
        "last_checked_at",
        "last_success_at",
        "last_status_code",
        "next_check_at",
        "updated_at",
    ]

    if monitor.last_content_hash != current_hash:
        monitor.last_content_hash = current_hash
        update_fields.append("last_content_hash")

    if changed:
        monitor.last_changed_at = checked_at
        update_fields.append("last_changed_at")

    monitor.save(update_fields=update_fields)

    if changed:
        _notify(monitor, check, "change")

    if was_failing:
        _notify(monitor, check, "recovery")

    return {
        "status": "changed" if changed else "unchanged",
        "monitor_id": str(monitor.id),
    }

# Advanced monitoring task registration.
# Celery autodiscovers monitors.tasks, so re-exporting the task here
# ensures it is registered without importing Django models too early.
from .advanced_tasks import run_advanced_monitor


@shared_task
def dispatch_monitor_check(monitor_id):
    """
    Route a monitor to the appropriate monitoring engine.

    HTTP monitors use the original lightweight checker.
    Advanced modes use the browser-based advanced engine.
    """
    monitor = (
        Monitor.objects
        .select_related("advanced_config")
        .filter(
            id=monitor_id,
            active=True,
        )
        .first()
    )

    if monitor is None:
        return {
            "status": "skipped",
            "reason": "monitor_not_found_or_inactive",
        }

    config = getattr(
        monitor,
        "advanced_config",
        None,
    )

    if (
        config is not None
        and config.mode != AdvancedMonitorConfig.HTTP
    ):
        task = run_advanced_monitor.delay(
            str(monitor.id)
        )
        return {
            "status": "advanced_queued",
            "task_id": task.id,
            "mode": config.mode,
        }

    task = check_monitor.delay(
        str(monitor.id)
    )

    return {
        "status": "http_queued",
        "task_id": task.id,
    }


def _delete_artifact_file(path_str: str) -> bool:
    """Delete one artifact object (storage key or legacy local path).

    Delegates to the configured storage backend so retention removes
    objects from S3/MinIO, not merely database references. Legacy
    absolute paths are confined to the local artifacts root.
    """
    from common.artifact_storage import StorageError, delete_key

    if not path_str:
        return False
    try:
        return bool(delete_key(path_str))
    except StorageError:
        return False


@shared_task
def cleanup_expired_artifacts():
    """Daily retention janitor: delete checks/diffs/objects past plan limit.

    Retention comes from the monitor owner's active plan
    (`billing.PLAN_LIMITS[].history_days`). Deleting a `MonitorCheck`
    cascades to its `ChangeDiff`s, `PricePoint`, and `NotificationEvent`s;
    artifact *objects* are deleted from the configured storage backend
    (local disk or S3) first — keys live only on the diff rows.
    """
    from billing.models import get_plan_for_user, plan_limits

    from .models import ChangeDiff

    now = timezone.now()
    totals = {"checks_deleted": 0, "diffs_deleted": 0, "files_deleted": 0}

    for monitor in Monitor.objects.select_related("user").only(
        "id", "user__id", "user__is_superuser"
    ):
        days = plan_limits(get_plan_for_user(monitor.user))["history_days"]
        cutoff = now - timedelta(days=days)

        stale_ids = list(
            MonitorCheck.objects.filter(
                monitor=monitor, checked_at__lt=cutoff
            ).values_list("id", flat=True)
        )
        if not stale_ids:
            continue

        # A diff is stale when EITHER linked check is stale (keeping it
        # would leave a dangling FK once the check is deleted anyway).
        stale_diffs = ChangeDiff.objects.filter(
            monitor=monitor
        ).filter(
            Q(previous_check_id__in=stale_ids)
            | Q(current_check_id__in=stale_ids)
        )
        for artifact_path in (
            stale_diffs.exclude(artifact_path="")
            .values_list("artifact_path", flat=True)
            .distinct()
        ):
            if artifact_path and _delete_artifact_file(artifact_path):
                totals["files_deleted"] += 1
        totals["diffs_deleted"] += stale_diffs.count()
        stale_diffs.delete()

        totals["checks_deleted"] += len(stale_ids)
        MonitorCheck.objects.filter(id__in=stale_ids).delete()

    return totals
