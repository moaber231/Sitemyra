from .base import *

DEBUG = True

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "backend",
]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
# Sender identity (DEFAULT_FROM_EMAIL) is inherited from base settings.

# Phase E (plan D7): monitor tasks hand notifications off with
# deliver_monitor_event.delay(); eager mode keeps that execution
# synchronous HERE (development + the test suite) so local runs and
# tests behave exactly as before the change — no broker required.
# Production settings never set this: notifications queue to
# celery_notifications and run on the notifications worker instead.
CELERY_TASK_ALWAYS_EAGER = True
