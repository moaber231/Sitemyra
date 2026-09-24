from .base import *

DEBUG = False

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",")
    if host.strip()
]

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
# Hostinger uses implicit TLS on port 465 (EMAIL_USE_SSL=1); 587 uses
# STARTTLS (EMAIL_USE_TLS=1). Django rejects both being true, so SSL wins
# when explicitly enabled.
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "0") == "1"
EMAIL_USE_TLS = (
    os.getenv("EMAIL_USE_TLS", "0" if EMAIL_USE_SSL else "1") == "1"
)
# Sender identity (DEFAULT_FROM_EMAIL) is inherited from base settings.

# Phase E (plan D9): reuse DB connections instead of reconnecting per
# request (default 60 s; 0 restores the old per-connection behaviour).
CONN_MAX_AGE = int(os.getenv("CONN_MAX_AGE", "60"))

# Phase E (plan D10): only trust X-Forwarded-Proto when a proxy sets it
# (opt-in: SECURE_PROXY_SSL_HEADER=1 behind a TLS-terminating proxy).
SECURE_PROXY_SSL_HEADER = (
    ("HTTP_X_FORWARDED_PROTO", "https")
    if os.getenv("SECURE_PROXY_SSL_HEADER", "0") == "1"
    else None
)
