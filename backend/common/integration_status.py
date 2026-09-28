"""Phase 1 third-party configuration audit (no secrets exposed).

Categories:
  - required core: app cannot serve traffic without it.
  - optional integration: safe to leave unconfigured; features degrade loudly.
  - production-required: must be set when DEBUG is off for the owning flow.
  - development-only: only honoured when DEBUG is on.
"""

import os

from django.conf import settings


def _present(*names: str) -> bool:
    return all(bool(os.getenv(name, "").strip()) for name in names)


SMTP_REQUIRED_ENV = (
    "EMAIL_HOST",
    "EMAIL_PORT",
    "EMAIL_HOST_USER",
    "EMAIL_HOST_PASSWORD",
    "EMAIL_FROM",
)
STRIPE_REQUIRED_ENV = (
    "STRIPE_SECRET_KEY",
    "STRIPE_PRICE_PRO",
    "STRIPE_PRICE_BUSINESS",
    "STRIPE_WEBHOOK_SECRET",
)


def smtp_missing_environment():
    """Return names of missing SMTP settings, never their values."""
    return [
        name for name in SMTP_REQUIRED_ENV
        if not os.getenv(name, "").strip()
    ]


def _artifact_storage_status() -> dict:
    try:
        from .artifact_storage import storage_status

        return storage_status()
    except Exception as exc:
        return {
            "backend": "unknown",
            "configured": False,
            "status": "error",
            "detail": str(exc)[:200],
        }


def integration_status() -> dict:
    debug = bool(settings.DEBUG)
    stripe_missing = [
        name for name in STRIPE_REQUIRED_ENV
        if not os.getenv(name, "").strip()
    ]
    stripe = not stripe_missing
    webhook_secret = bool(os.getenv("STRIPE_WEBHOOK_SECRET", "").strip())
    google = _present("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET")
    github = _present("GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET")
    smtp_missing = smtp_missing_environment()
    smtp = not smtp_missing

    return {
        "core": {
            "django_secret_key": {
                "configured": os.getenv("DJANGO_SECRET_KEY", "")
                not in ("", "development-only-secret"),
                "required": True,
            },
            "database": {
                "configured": bool(
                    os.getenv("DATABASE_URL", "").strip()
                    or os.getenv("POSTGRES_PASSWORD", "").strip()
                ),
                "required": True,
            },
            "redis": {
                "configured": bool(os.getenv("REDIS_URL", "").strip()),
                "required": True,
            },
        },
        "optional_integrations": {
            "stripe": {
                "configured": stripe,
                "production_required_for_billing": True,
                "missing": stripe_missing,
                "status": "ready" if stripe else "not_configured",
                "detail": (
                    "Live billing ready."
                    if stripe
                    else "Billing is not configured. Missing: "
                    + ", ".join(stripe_missing)
                ),
            },
            "stripe_webhook": {
                "configured": webhook_secret,
                "production_required": True,
                "status": "ready" if webhook_secret else "missing",
                "detail": (
                    "Signature verification active."
                    if webhook_secret
                    else (
                        "Unsigned webhooks rejected "
                        f"({'dev bypass possible' if debug else '503 in production'})."
                    ),
                ),
            },
            "google_oauth": {
                "configured": google,
                "status": "ready" if google else "disabled",
                "detail": (
                    "Authorization-code flow ready."
                    if google
                    else "Set GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET to enable."
                ),
            },
            "github_oauth": {
                "configured": github,
                "status": "ready" if github else "disabled",
                "detail": (
                    "Authorization-code flow ready."
                    if github
                    else "Set GITHUB_CLIENT_ID/GITHUB_CLIENT_SECRET to enable."
                ),
            },
            "smtp_email": {
                "configured": smtp,
                "status": "ready" if smtp else "not_configured",
                "missing": smtp_missing,
                "detail": (
                    "SMTP configured."
                    if smtp
                    else "EMAIL NOT CONFIGURED. Missing: "
                    + ", ".join(smtp_missing)
                ),
            },
            "slack_discord_webhook": {
                "configured": False,
                "configuration_scope": "per-user",
                "status": "user_managed",
                "detail": (
                    "No global key is required. Each user must create and test "
                    "a destination under Alert Channels."
                ),
            },
            "artifact_storage": _artifact_storage_status(),
        },
        "development_only_flags": {
            "STRIPE_DEV_STUB": os.getenv("STRIPE_DEV_STUB", "0") == "1",
            "STRIPE_DEV_SKIP_WEBHOOK_VERIFY": os.getenv(
                "STRIPE_DEV_SKIP_WEBHOOK_VERIFY", "0"
            )
            == "1",
            "honoured": debug,
            "detail": (
                "Dev bypass flags are honoured."
                if debug
                else "Dev bypass flags are ignored in production."
            ),
        },
    }


def log_integration_warnings() -> None:
    import logging

    logger = logging.getLogger(__name__)
    status = integration_status()
    if not status["core"]["django_secret_key"]["configured"]:
        logger.warning("DJANGO_SECRET_KEY is still the development default")
    if not status["optional_integrations"]["stripe"]["configured"]:
        logger.warning(
            "Stripe billing is not configured: missing %s",
            ", ".join(status["optional_integrations"]["stripe"]["missing"]),
        )
    if not status["optional_integrations"]["stripe_webhook"]["configured"]:
        logger.warning(
            "STRIPE_WEBHOOK_SECRET is not set: webhooks rejected "
            "(503 in production)"
        )
    if not status["optional_integrations"]["smtp_email"]["configured"]:
        logger.warning(
            "EMAIL NOT CONFIGURED: missing %s",
            ", ".join(status["optional_integrations"]["smtp_email"]["missing"]),
        )
    flags = status["development_only_flags"]
    if not flags["honoured"] and any(
        [
            flags["STRIPE_DEV_STUB"],
            flags["STRIPE_DEV_SKIP_WEBHOOK_VERIFY"],
        ]
    ):
        logger.warning("Dev-only integration bypass flags set but ignored (DEBUG off)")
