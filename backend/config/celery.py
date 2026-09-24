import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("apeiro")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Worker liveness registry for GET /api/health/ (docs/RESOURCE-BUDGET.md
# section 6). worker_ready/worker_shutdown only fire in `celery worker`
# processes — beat and the API are unaffected, and no Celery code is
# imported into the API's health path.
from config import worker_heartbeat  # noqa: E402

worker_heartbeat.install()
