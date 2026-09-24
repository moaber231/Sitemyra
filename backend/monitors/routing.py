"""Queue-aware task publishing (Phase B import decoupling).

The API container (and beat / http-worker containers built from the API
image) must boot WITHOUT Playwright, Pillow or pixelmatch. Browser
checks are therefore published *by task name* with ``app.send_task`` —
never by importing ``monitors.advanced_tasks`` in this process.

Only the dedicated browser worker imports the browser task module (via
``CELERY_IMPORTS=monitors.advanced_tasks`` in its environment), and only
it consumes the ``celery_browser`` queue.

The queue names below must stay in sync with ``CELERY_TASK_ROUTES`` in
``config.settings.base``; passing ``queue=`` explicitly at the call site
makes the intent unambiguous even if routing config changes later.
"""

from config.celery import app

TASK_HTTP_CHECK = "monitors.tasks.check_monitor"
TASK_BROWSER_CHECK = "monitors.advanced_tasks.run_advanced_monitor"

QUEUE_HTTP = "celery_http"
QUEUE_BROWSER = "celery_browser"


def enqueue_http_check(monitor_id) -> str:
    """Publish an HTTP/content check to celery_http; returns the task id."""
    async_result = app.send_task(
        TASK_HTTP_CHECK,
        args=[str(monitor_id)],
        queue=QUEUE_HTTP,
    )
    return async_result.id


def enqueue_browser_check(monitor_id) -> str:
    """Publish a Playwright check to celery_browser; returns the task id.

    Safe to call from the API container: publishing by name never
    imports the task module, so Playwright stays out of this process.
    """
    async_result = app.send_task(
        TASK_BROWSER_CHECK,
        args=[str(monitor_id)],
        queue=QUEUE_BROWSER,
    )
    return async_result.id
