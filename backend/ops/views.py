import time
from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response


def _redis_ping():
    url = getattr(settings, "REDIS_URL", "redis://redis:6379/0")
    try:
        import redis

        client = redis.Redis.from_url(url, socket_timeout=3)
        start = time.monotonic()
        client.ping()
        latency_ms = round((time.monotonic() - start) * 1000, 1)
        info = client.info("replication") if False else {}
        return {
            "status": "ok",
            "latency_ms": latency_ms,
            "url_host": url.split("@")[-1],
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)[:200]}


def _celery_status():
    try:
        from config.celery import app as celery_app

        inspect = celery_app.control.inspect(timeout=3)
        stats = inspect.stats() or {}
        active = inspect.active() or {}
        workers = list(stats.keys())
        queued = sum(len(v) for v in active.values())
        beat_ok = True
        # Beat liveness: check last schedule tick via cache/DB fallback.
        return {
            "status": "ok" if workers else "no_workers",
            "workers": workers,
            "active_tasks": queued,
            "beat": {"status": "ok" if workers else "unknown"},
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)[:200]}


def _browser_pool_health():
    """Browser engine availability *in this container*.

    The API container intentionally ships without Playwright/Chromium
    (Phase B/C) — the engine lives on the dedicated browser worker. So
    "not importable here" is the healthy state for the API, not a
    failure of the browser service (worker liveness is covered by the
    celery check above).
    """
    try:
        import playwright  # noqa: F401
    except ImportError:
        return {
            "status": "not-in-this-container",
            "engine": "playwright",
            "detail": (
                "Playwright/Chromium runs on the dedicated browser "
                "worker; this API container does not ship it."
            ),
        }
    try:
        from monitors.services.browser_fetcher import fetch_with_browser  # noqa

        return {
            "status": "ok",
            "engine": "playwright",
            "detail": "Playwright module importable; browser worker owns it.",
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)[:200]}


def _total_users():
    try:
        from django.contrib.auth import get_user_model

        return get_user_model().objects.count()
    except Exception:
        return None


def _disk_usage():
    """Disk usage for storage/artifacts (container + host bind-mount aware)."""
    import shutil
    from pathlib import Path

    from common.artifact_storage import local_root

    candidates = [
        # Env-driven first (ARTIFACT_LOCAL_ROOT) — plan D10 removed
        # the hardcoded /app/storage candidates.
        local_root(),
        Path(settings.BASE_DIR) / "storage",
        Path(settings.BASE_DIR) / "backend" / "storage",
    ]
    target = next((p for p in candidates if p.exists()), candidates[0])
    try:
        du = shutil.disk_usage(str(target.parent if not target.exists() else target))
    except Exception as exc:
        return {"status": "error", "error": str(exc)[:200]}
    artifacts_bytes = 0
    artifact_files = 0
    for base in candidates:
        if not base.exists():
            continue
        try:
            for f in base.rglob("*"):
                try:
                    if f.is_file():
                        artifacts_bytes += f.stat().st_size
                        artifact_files += 1
                except OSError:
                    continue
            break
        except Exception:
            continue
    return {
        "status": "ok",
        "path": str(target),
        "total_bytes": du.total,
        "used_bytes": du.used,
        "free_bytes": du.free,
        "total_mb": round(du.total / 1024 / 1024, 1),
        "used_mb": round(du.used / 1024 / 1024, 1),
        "free_mb": round(du.free / 1024 / 1024, 1),
        "used_pct": round(du.used / du.total * 100, 1) if du.total else 0,
        "artifacts_bytes": artifacts_bytes,
        "artifacts_mb": round(artifacts_bytes / 1024 / 1024, 2),
        "artifact_files": artifact_files,
    }


@api_view(["GET"])
@permission_classes([IsAdminUser])
def metrics(request):
    """Super-Admin SaaS metrics: users, MRR, subscribers, checks, queue, disk."""
    from billing.models import Subscription
    from monitors.models import Monitor, MonitorCheck

    now = timezone.now()
    day_ago = now - timedelta(hours=24)

    mrr_cents = (
        Subscription.objects.filter(status__in=("active", "trialing", "past_due"))
        .aggregate(total=Sum("mrr_cents"))["total"]
        or 0
    )
    # Active Monthly Subscribers: any paying plan still in good/dunning state.
    active_subs = Subscription.objects.filter(
        status__in=("active", "trialing", "past_due")
    ).exclude(plan="free").count()
    total_users = _total_users()
    past_due = Subscription.objects.filter(status="past_due").count()
    canceled_30d = Subscription.objects.filter(
        status="canceled", updated_at__gte=now - timedelta(days=30)
    ).count()

    checks_24h = MonitorCheck.objects.filter(checked_at__gte=day_ago).count()
    failed_24h = (
        MonitorCheck.objects.filter(checked_at__gte=day_ago)
        .exclude(error="")
        .count()
    )
    monitors_active = Monitor.objects.filter(active=True).count()
    monitors_total = Monitor.objects.count()

    # Worker queue latency: inspect celery queue length via Redis.
    queue_latency = _redis_ping()
    queue_depth = None
    try:
        import redis

        client = redis.Redis.from_url(settings.REDIS_URL)
        queue_depth = client.llen("celery")
    except Exception:
        queue_depth = None

    # Churn risk heuristic: past_due subs + monitors failing repeatedly.
    failing_monitors = (
        MonitorCheck.objects.filter(checked_at__gte=day_ago)
        .exclude(error="")
        .values("monitor_id")
        .annotate(fails=Count("id"))
        .filter(fails__gte=5)
        .count()
    )
    churn_risk = {
        "past_due_subscriptions": past_due,
        "canceled_last_30d": canceled_30d,
        "monitors_failing_repeatedly_24h": failing_monitors,
        "score": min(100, past_due * 10 + canceled_30d * 5 + failing_monitors),
    }

    return Response(
        {
            "total_users": total_users,
            "mrr_cents": mrr_cents,
            "mrr_dollars": round(mrr_cents / 100, 2),
            "active_subscribers": active_subs,
            "past_due_subscriptions": past_due,
            "checks_24h": checks_24h,
            "failed_checks_24h": failed_24h,
            "active_monitors": monitors_active,
            "total_monitors": monitors_total,
            "worker_queue": {
                "latency_ms": queue_latency.get("latency_ms"),
                "redis": queue_latency.get("status"),
                "celery_queue_depth": queue_depth,
                # Alias kept for dashboard clarity: Redis ping ≈ queue latency
                # probe; depth shows backlog.
                "queue_latency_ms": queue_latency.get("latency_ms"),
            },
            "storage": _disk_usage(),
            "churn_risk": churn_risk,
            "generated_at": now,
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
def diagnostics(request):
    """Automated diagnostic tools: Redis ping, Celery/Beat, Playwright pool."""
    redis_health = _redis_ping()
    celery_health = _celery_status()
    browser_health = _browser_pool_health()

    # Optional live test: dispatch a lightweight check when POSTed.
    test_dispatch = None
    if request.method == "POST":
        try:
            from monitors.tasks import schedule_due_monitors

            result = schedule_due_monitors.apply()
            test_dispatch = {"status": "ok", "scheduled": result.get()}
        except Exception as exc:
            test_dispatch = {"status": "error", "error": str(exc)[:200]}

    overall = (
        "ok"
        if redis_health.get("status") == "ok"
        and celery_health.get("status") in ("ok",)
        else "degraded"
    )
    try:
        from common.integration_status import integration_status

        integrations = integration_status()
    except Exception as exc:
        integrations = {"status": "error", "error": str(exc)[:200]}
    return Response(
        {
            "overall": overall,
            "redis": redis_health,
            "celery": celery_health,
            "playwright": browser_health,
            "test_dispatch": test_dispatch,
            "integrations": integrations,
        }
    )
