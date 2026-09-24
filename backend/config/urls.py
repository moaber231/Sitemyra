from django.db import connection
from django.http import JsonResponse
from django.urls import include, path


def _check_postgres():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)[:200]}


def _check_redis():
    from django.conf import settings

    try:
        import redis

        client = redis.Redis.from_url(
            settings.REDIS_URL, socket_timeout=2
        )
        client.ping()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)[:200]}


def _check_celery():
    """Worker liveness from the Redis heartbeat registry.

    Formerly a live ``control.inspect()`` broadcast per probe: ~2.1 s
    each, and under concurrency the shared kombu pidbox producer pool
    wedged (17/20 probes still blocked at 45 s, each pinning a DB
    connection — docs/RESOURCE-BUDGET.md section 6). Workers now
    re-register a TTL'd key every few seconds (config/worker_heartbeat.py);
    this side only scans that prefix — no broker round-trip, safe to call
    concurrently. Response shape unchanged.
    """
    from django.conf import settings

    try:
        import redis

        from config.worker_heartbeat import live_workers

        client = redis.Redis.from_url(
            settings.REDIS_URL, socket_timeout=2
        )
        workers = live_workers(client)
        if not workers:
            return {"status": "degraded", "detail": "no workers responded"}
        return {"status": "ok", "workers": workers}
    except Exception as exc:
        return {"status": "error", "error": str(exc)[:200]}


def health(request):
    checks = {
        "postgres": _check_postgres(),
        "redis": _check_redis(),
        "celery": _check_celery(),
    }
    statuses = {check["status"] for check in checks.values()}
    if statuses == {"ok"}:
        overall = "ok"
        http_status = 200
    elif "error" in statuses:
        overall = "error"
        http_status = 503
    else:
        overall = "degraded"
        http_status = 503
    return JsonResponse(
        {"status": overall, "checks": checks}, status=http_status
    )


urlpatterns = [
    path("api/notifications/", include("notifications.urls")),
    path("api/health/", health, name="health"),
    path("api/auth/", include("accounts.urls")),
    path("api/monitors/", include("monitors.urls")),
    path("api/workspaces/", include("workspaces.urls")),
    path("api/billing/", include("billing.urls")),
    path("api/admin/", include("ops.urls")),
]
