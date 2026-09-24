import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse

from kombu import Exchange, Queue

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "development-only-secret")
DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "accounts",
    "monitors",
    "notifications",
    "workspaces",
    "billing",
    "ops",
    "common",
]

MIDDLEWARE = [
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

database_url = os.getenv("DATABASE_URL")
if database_url:
    parsed_database_url = urlparse(database_url)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parsed_database_url.path.lstrip("/")),
            "USER": unquote(parsed_database_url.username or ""),
            "PASSWORD": unquote(parsed_database_url.password or ""),
            "HOST": parsed_database_url.hostname or "localhost",
            "PORT": str(parsed_database_url.port or 5432),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "apeiro"),
            "USER": os.getenv("POSTGRES_USER", "apeiro"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", "apeiro"),
            "HOST": os.getenv("POSTGRES_HOST", "postgres"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
        }
    }

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
CORS_ALLOWED_ORIGINS = [FRONTEND_URL]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "accounts.api_key_auth.ApiKeyAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TIMEZONE = TIME_ZONE

try:
    from celery.schedules import crontab

    _daily_midnight = crontab(hour=0, minute=0)
    # Phase E (plan D9): a REAL wall-clock crontab — Monday 09:00 UTC.
    # The old float interval (604800.0) re-fired7 days after each beat
    # start, drifting across the week and never landing on a weekday.
    _weekly_digest = crontab(day_of_week="mon", hour=9, minute=0)
except Exception:  # celery importable but schedules missing (never in practice)
    _daily_midnight = 24 * 3600.0
    _weekly_digest = 7 * 24 * 3600.0

CELERY_BEAT_SCHEDULE = {
    "schedule-due-monitors": {
        "task": "monitors.tasks.schedule_due_monitors",
        "schedule": 60.0,
    },
    "weekly-digest": {
        "task": "notifications.tasks.send_weekly_digests",
        "schedule": _weekly_digest,
    },
    "cleanup-expired-artifacts": {
        "task": "monitors.tasks.cleanup_expired_artifacts",
        "schedule": _daily_midnight,
    },
}

# ---------------------------------------------------------------------------
# Celery: queues, routing, reliability and time limits.
# (docs/OPTIMIZATION-PLAN.md D2/D6 — Phase A.)
#
# Three queues so each workload can run in its own container and be
# scaled independently:
#   celery_http          HTTP/content checks + scheduler + cleanup
#   celery_browser       Playwright checks ONLY -> dedicated browser worker
#   celery_notifications email/webhook/digest delivery
# ---------------------------------------------------------------------------


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, "1" if default else "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        return default


def _env_limits(
    soft_name: str,
    hard_name: str,
    soft_default: int,
    hard_default: int,
) -> tuple[int, int]:
    """Return (soft, hard); soft is clamped because Celery rejects soft > hard."""
    hard = _env_int(hard_name, hard_default)
    soft = min(_env_int(soft_name, soft_default), hard)
    return soft, hard


# Phase E (plan D9): scheduler fan-out cap per60 s tick. The default
#500 bounds each burst (500 checks/min max) so a large due backlog can
# never outrun the workers or the DB in a single pass.
SCHEDULER_BATCH_SIZE = _env_int("SCHEDULER_BATCH_SIZE", 500)

# Phase F (plan D8): optional retention CAP for artifacts/history.
# Effective retention per monitor = min(plan history_days, this value)
# — it can shorten but NEVER extend the plan's retention. Unset, 0 or
# invalid = no cap (plan limits govern alone).
try:
    _artifact_retention_days = int(
        os.getenv("ARTIFACT_RETENTION_DAYS", "") or ""
    )
except ValueError:
    _artifact_retention_days = 0
ARTIFACT_RETENTION_DAYS = (
    _artifact_retention_days if _artifact_retention_days > 0 else None
)


def _celery_queue(name: str) -> Queue:
    # Explicit exchange + routing key per queue: unambiguous on the Redis
    # broker (deployed today) and on AMQP brokers (portability target).
    return Queue(name, Exchange(name, type="direct"), routing_key=name)


CELERY_TASK_QUEUES = (
    _celery_queue("celery_http"),
    _celery_queue("celery_browser"),
    _celery_queue("celery_notifications"),
)
CELERY_TASK_DEFAULT_QUEUE = "celery_http"
CELERY_TASK_DEFAULT_ROUTING_KEY = "celery_http"

# Explicit routing. Playwright work NEVER lands on the default queue —
# only the dedicated browser worker consumes celery_browser. Notification
# delivery never runs on the browser worker. Everything else (HTTP
# checks, scheduler, cleanup) is celery_http.
CELERY_TASK_ROUTES = {
    "monitors.advanced_tasks.run_advanced_monitor": {
        "queue": "celery_browser",
    },
    "notifications.tasks.*": {"queue": "celery_notifications"},
    "monitors.tasks.*": {"queue": "celery_http"},
}

# Extra task modules imported at worker boot (comma-separated env var).
# ONLY the browser worker sets CELERY_IMPORTS=monitors.advanced_tasks —
# it is the sole process with Playwright installed and the sole consumer
# of celery_browser. The API/beat/http-worker containers must leave it
# empty, or boot would import the Playwright-backed task module and fail
# (Phase B import decoupling).
CELERY_IMPORTS = tuple(
    module.strip()
    for module in os.getenv("CELERY_IMPORTS", "").split(",")
    if module.strip()
)

# Reliability: a worker killed mid-check (deploy, OOM, hard time limit)
# must not silently lose the check. acks_late acks AFTER completion, so
# redelivery happens on crash; the accepted duplicate-MonitorCheck risk
# in that window is documented (OPTIMIZATION-PLAN risk R2).
CELERY_TASK_ACKS_LATE = _env_bool("CELERY_TASK_ACKS_LATE", True)
CELERY_TASK_REJECT_ON_WORKER_LOST = _env_bool(
    "CELERY_TASK_REJECT_ON_WORKER_LOST", True
)
# task_acks_on_failure_or_timeout keeps its default (True): a task that
# raises or hits its soft limit is acked and never redelivered, so a
# poison task cannot loop forever.
#
# Prefetch 1 (env-tunable): with acks_late this means each worker child
# holds at most one unacked task — the right default for the browser
# worker and a safe one for the http worker (raise it per-worker via
# --prefetch-multiplier if throughput requires).
CELERY_WORKER_PREFETCH_MULTIPLIER = _env_int(
    "CELERY_TASK_PREFETCH_MULTIPLIER", 1
)
# No application code consumes AsyncResult/ResultSet — the only result
# reader is ops diagnostics' local Task.apply(), which never touches the
# backend. So do not persist results into Redis.
CELERY_TASK_IGNORE_RESULT = _env_bool("CELERY_TASK_IGNORE_RESULT", True)

# Global time limits = the HTTP-monitor defaults; they apply to every
# task without an explicit limit (check_monitor, dispatch_monitor_check).
# The hard limit is the final kill switch behind all inner fetch timeouts.
CELERY_TASK_SOFT_TIME_LIMIT, CELERY_TASK_TIME_LIMIT = _env_limits(
    "CELERY_HTTP_TASK_SOFT_TIME_LIMIT",
    "CELERY_HTTP_TASK_TIME_LIMIT",
    150,
    180,
)

# Per-task limits (env-tunable) applied on the @shared_task decorators:
# scheduler beats a single check's outer budget; browser tasks sit above
# the per-check navigation timeout; notifications/digest/cleanup are
# bounded so no queue can pin a worker indefinitely.
SCHEDULER_TASK_SOFT_TIME_LIMIT, SCHEDULER_TASK_TIME_LIMIT = _env_limits(
    "CELERY_SCHEDULER_TASK_SOFT_TIME_LIMIT",
    "CELERY_SCHEDULER_TASK_TIME_LIMIT",
    50,
    60,
)
BROWSER_TASK_SOFT_TIME_LIMIT, BROWSER_TASK_TIME_LIMIT = _env_limits(
    "CELERY_BROWSER_TASK_SOFT_TIME_LIMIT",
    "CELERY_BROWSER_TASK_TIME_LIMIT",
    180,
    240,
)
NOTIFICATION_TASK_SOFT_TIME_LIMIT, NOTIFICATION_TASK_TIME_LIMIT = _env_limits(
    "CELERY_NOTIFICATION_TASK_SOFT_TIME_LIMIT",
    "CELERY_NOTIFICATION_TASK_TIME_LIMIT",
    90,
    120,
)
DIGEST_TASK_SOFT_TIME_LIMIT, DIGEST_TASK_TIME_LIMIT = _env_limits(
    "CELERY_DIGEST_TASK_SOFT_TIME_LIMIT",
    "CELERY_DIGEST_TASK_TIME_LIMIT",
    600,
    900,
)
CLEANUP_TASK_SOFT_TIME_LIMIT, CLEANUP_TASK_TIME_LIMIT = _env_limits(
    "CELERY_CLEANUP_TASK_SOFT_TIME_LIMIT",
    "CELERY_CLEANUP_TASK_TIME_LIMIT",
    600,
    900,
)

# Email sender identity (Sitemyra rebrand).
# Production sender mailbox (e.g. info@<sitemyra-domain>) is provided via
# EMAIL_FROM at deploy time; SMTP host/user/password are also env-only and
# must never be committed. Display name via EMAIL_FROM_NAME.
EMAIL_FROM_ADDRESS = os.getenv("EMAIL_FROM", "alerts@example.com").strip()
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Sitemyra").strip()
if "<" in EMAIL_FROM_ADDRESS:
    # Operator supplied a full "Name <addr>" value; respect it verbatim.
    DEFAULT_FROM_EMAIL = EMAIL_FROM_ADDRESS
elif EMAIL_FROM_NAME:
    DEFAULT_FROM_EMAIL = f"{EMAIL_FROM_NAME} <{EMAIL_FROM_ADDRESS}>"
else:
    DEFAULT_FROM_EMAIL = EMAIL_FROM_ADDRESS

# Stripe / SSO (empty = disabled with loud 503s; Phase 1 safety).
# Dev-only bypasses: STRIPE_DEV_STUB, STRIPE_DEV_SKIP_WEBHOOK_VERIFY —
# honoured only when DEBUG is on. OAuth needs no bypass: unconfigured
# providers report disabled via /api/auth/oauth/status/.
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_PRO = os.getenv("STRIPE_PRICE_PRO", "")
STRIPE_PRICE_BUSINESS = os.getenv("STRIPE_PRICE_BUSINESS", "")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
