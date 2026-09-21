import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse

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
except Exception:  # celery importable but schedules missing (never in practice)
    _daily_midnight = 24 * 3600.0

CELERY_BEAT_SCHEDULE = {
    "schedule-due-monitors": {
        "task": "monitors.tasks.schedule_due_monitors",
        "schedule": 60.0,
    },
    "weekly-digest": {
        "task": "notifications.tasks.send_weekly_digests",
        # Celery beat crontab would be nicer; weekly Monday 09:00 UTC.
        "schedule": 7 * 24 * 3600.0,
    },
    "cleanup-expired-artifacts": {
        "task": "monitors.tasks.cleanup_expired_artifacts",
        "schedule": _daily_midnight,
    },
}

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
