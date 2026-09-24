import logging
import os
from datetime import timedelta
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from notifications.tasks import deliver_monitor_event

from .models import AdvancedMonitorConfig, Monitor, MonitorCheck
from .routing import enqueue_browser_check, enqueue_http_check
from .services.change_detector import detect_change
from .services.fetcher import FetchError, SecurityError, fetch_url
from .services.normalizer import content_hash
from .services.scheduler import get_due_monitors

logger = logging.getLogger(__name__)


@shared_task(
    # Scheduler is a fan-out: bounded tight so a stuck query or broker
    # hiccup can never pin the http worker (Phase A time limits).
    soft_time_limit=settings.SCHEDULER_TASK_SOFT_TIME_LIMIT,
    time_limit=settings.SCHEDULER_TASK_TIME_LIMIT,
)
def schedule_due_monitors():
    """Fan out due checks — single hop, bounded batch (plan D9).

    One query picks the batch (``get_due_monitors``, capped at
    ``SCHEDULER_BATCH_SIZE``); each row is re-locked, advanced, and its
    TARGET task is published directly to celery_http/celery_browser via
    ``monitors.routing`` (by name — this process never imports the
    Playwright task module). That's1 message per check instead of the
    old dispatch_monitor_check -> enqueue_* -> target chain (2), with
    the exact routing decision that ``dispatch_monitor_check`` makes.
    """
    now = timezone.now()
    scheduled = 0

    for due in get_due_monitors():
        with transaction.atomic():
            monitor = (
                Monitor.objects
                # Lock ONLY the monitor row: advanced_config is the
                # nullable side of the join, and Postgres refuses
                # FOR UPDATE on it (`OF self` scopes the lock to what
                # this transaction actually mutates).
                .select_for_update(of=("self",))
                .select_related("advanced_config")
                .filter(
                    id=due.id,
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

        config = getattr(
            monitor,
            "advanced_config",
            None,
        )

        if (
            config is not None
            and config.mode != AdvancedMonitorConfig.HTTP
        ):
            enqueue_browser_check(monitor.id)
        else:
            enqueue_http_check(monitor.id)

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
    """Hand the event to the notifications queue — never breaks the
    monitor task and never blocks one on SMTP/webhooks (plan D7).

    Production queues to celery_notifications; development (and the
    test suite) run Celery eagerly, so the dispatch still executes
    synchronously there and existing behaviour is preserved.
    """
    try:
        deliver_monitor_event.delay(
            str(monitor.id),
            str(check.id),
            event_type,
        )
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

# NOTE (Phase B): do NOT import .advanced_tasks here. That module pulls
# in Playwright, and monitors.tasks is imported by every API/beat/http
# process (urls -> views -> tasks). Browser checks are published by name
# via monitors.routing instead; only the browser worker imports the task
# module (CELERY_IMPORTS=monitors.advanced_tasks).


@shared_task
def dispatch_monitor_check(monitor_id):
    """
    Route a monitor to the appropriate monitoring engine.

    HTTP monitors use the original lightweight checker.
    Advanced modes use the browser-based advanced engine (published by
    name to celery_browser — no Playwright import in this process).
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
        task_id = enqueue_browser_check(monitor.id)
        return {
            "status": "advanced_queued",
            "task_id": task_id,
            "mode": config.mode,
        }

    task_id = enqueue_http_check(monitor.id)

    return {
        "status": "http_queued",
        "task_id": task_id,
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


# ---------------------------------------------------------------------------
# Phase F (plan D8): retention cap, orphan sweep, empty-dir prune.
# ---------------------------------------------------------------------------

_ORPHAN_GRACE_SECONDS = 600
# Objects are written BEFORE their rows commit (advanced_tasks): a file
# newer than this may belong to an in-flight check whose row has not
# landed yet. Never sweep those — an early sweep would delete an object
# that its about-to-commit row needs. Every later (idempotent) run picks
# them up once they age past the window.


def _effective_retention_days(plan_days: int) -> int:
    """Plan history days, optionally SHORTENED by ARTIFACT_RETENTION_DAYS.

    The env value is a cap: min(plan, cap) — it can tighten storage
    use but never extends what a plan already guarantees/deletes.
    """
    cap = getattr(settings, "ARTIFACT_RETENTION_DAYS", None)
    if cap:
        return min(plan_days, cap)
    return plan_days


def _sweep_orphan_artifacts(cutoffs, now, totals) -> None:
    """Delete storage objects no live, in-retention row needs (plan D8).

    A layout key (``artifacts/<monitor>/<check>/<file>``) is orphaned
    when its monitor is gone, its check row is gone, or its check sits
    past that monitor's effective retention. Live fresh checks keep
    their objects: check + diff rows commit in one transaction, so a
    live check implies live references. Legacy flat files are kept only
    while a ``ChangeDiff`` still references their absolute path.
    Files younger than the grace window are skipped (write-then-row).
    Idempotent: already-deleted objects simply are not seen again.
    """
    from common.artifact_storage import (
        delete_key,
        iter_storage_objects,
    )

    from .models import ChangeDiff

    layout = []  # (key, monitor_id, check_id, size)
    legacy = []  # (absolute_path, size)
    now_ts = now.timestamp()
    for key, size, mtime in iter_storage_objects():
        if now_ts - mtime <= _ORPHAN_GRACE_SECONDS:
            continue
        parts = key.split("/")
        if len(parts) == 4 and parts[0] == "artifacts":
            layout.append((key, parts[1], parts[2], size))
        else:
            legacy.append((key, size))

    if not layout and not legacy:
        return

    # Existence + age of every check behind the keys: one query per 500.
    check_rows = {}
    check_ids = sorted(
        {check_id for _key, _monitor, check_id, _size in layout}
    )
    for start in range(0, len(check_ids), 500):
        rows = (
            MonitorCheck.objects
            .filter(id__in=check_ids[start:start + 500])
            .values_list("id", "monitor_id", "checked_at")
        )
        for row_id, row_monitor, row_checked_at in rows:
            check_rows[str(row_id)] = (str(row_monitor), row_checked_at)

    # Legacy files: referenced only while a diff still points at them.
    referenced = set()
    legacy_paths = sorted({path for path, _size in legacy})
    for start in range(0, len(legacy_paths), 500):
        referenced.update(
            ChangeDiff.objects
            .filter(artifact_path__in=legacy_paths[start:start + 500])
            .values_list("artifact_path", flat=True)
        )

    for key, monitor_id, check_id, size in layout:
        row = check_rows.get(check_id)
        cutoff = cutoffs.get(monitor_id)
        if (
            cutoff is not None  # monitor still exists
            and row is not None  # check row still exists
            and row[0] == monitor_id  # ...and belongs to this key
            and row[1] >= cutoff  # ...within effective retention
        ):
            continue
        if delete_key(key):
            totals["orphans_deleted"] += 1
            totals["bytes_reclaimed"] += size

    for path, size in legacy:
        if path in referenced:
            continue
        if delete_key(path):
            totals["orphans_deleted"] += 1
            totals["bytes_reclaimed"] += size


def _prune_empty_dirs(totals) -> None:
    """Remove now-empty artifact directories bottom-up, keeping the
    storage root itself (plan D8: up to and including the monitor's
    ``artifacts/<monitor_id>/`` dir). Local backend only — object
    stores have no directories. The OS ``rmdir`` error (not empty) IS
    the emptiness test, so stale walk listings cannot mislead it.
    """
    from common.artifact_storage import backend_name, local_root

    if backend_name() != "local":
        return
    root = local_root()
    if not root.is_dir():
        return
    for dirpath, _dirnames, _filenames in os.walk(root, topdown=False):
        path = Path(dirpath)
        if path == root:
            continue  # the storage root always survives
        try:
            path.rmdir()
        except OSError:
            continue  # not empty (or already gone) — keep it
        totals["dirs_pruned"] += 1


@shared_task(
    # Artifact sweep over all storage: bounded (env-tunable) so the daily
    # cleanup can never pin the http worker indefinitely.
    soft_time_limit=settings.CLEANUP_TASK_SOFT_TIME_LIMIT,
    time_limit=settings.CLEANUP_TASK_TIME_LIMIT,
)
def cleanup_expired_artifacts():
    """Daily retention janitor (plan D8): DB-driven delete, orphan sweep
    and empty-dir prune — with reclaimed byte/count logging; idempotent.

    Retention = the monitor owner's plan ``history_days``, optionally
    shortened by ``ARTIFACT_RETENTION_DAYS`` (min of the two — the env
    value is a cap, never an extension). Objects are deleted BEFORE
    their rows, so a crash can only orphan objects (the same run's
    sweep or the next day's catches them) — never leave rows pointing
    at missing objects. Monitor ``post_delete`` handles the direct
    delete path; this task is the safety net either way.
    """
    from billing.models import get_plan_for_user, plan_limits
    from common.artifact_storage import size_of

    from .models import ChangeDiff

    now = timezone.now()
    totals = {
        "checks_deleted": 0,
        "diffs_deleted": 0,
        "files_deleted": 0,
        "orphans_deleted": 0,
        "dirs_pruned": 0,
        "bytes_reclaimed": 0,
    }

    cutoffs = {}  # str(monitor_id) -> effective cutoff

    for monitor in Monitor.objects.select_related("user").only(
        "id", "user__id", "user__is_superuser"
    ):
        days = _effective_retention_days(
            plan_limits(get_plan_for_user(monitor.user))["history_days"]
        )
        cutoff = now - timedelta(days=days)
        cutoffs[str(monitor.id)] = cutoff

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
            # Size BEFORE delete (objects go first, then rows).
            byte_size = size_of(artifact_path)
            if _delete_artifact_file(artifact_path):
                totals["files_deleted"] += 1
                totals["bytes_reclaimed"] += byte_size
        totals["diffs_deleted"] += stale_diffs.count()
        stale_diffs.delete()

        totals["checks_deleted"] += len(stale_ids)
        MonitorCheck.objects.filter(id__in=stale_ids).delete()

    # Safety net: storage objects whose rows are gone/stale (missed
    # monitor deletes, rolled-back commits, failed deletes last run) —
    # then drop the directories they leave behind.
    _sweep_orphan_artifacts(cutoffs, now, totals)
    _prune_empty_dirs(totals)

    logger.info(
        "retention sweep: checks=%d diffs=%d files=%d orphans=%d "
        "dirs=%d bytes=%d",
        totals["checks_deleted"],
        totals["diffs_deleted"],
        totals["files_deleted"],
        totals["orphans_deleted"],
        totals["dirs_pruned"],
        totals["bytes_reclaimed"],
    )
    return totals
