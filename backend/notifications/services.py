"""Phase 7 — central notification dispatcher with per-monitor routing.

Single notification path for all monitor engines (HTTP/content, DOM,
screenshot, price). Monitor tasks detect events and call
:func:`dispatch_monitor_event`; all provider logic lives here.

Routing: a monitor notifies ONLY channels linked via
``MonitorAlertChannel``. No owner-wide / workspace-wide fan-out.

Providers: Slack, Discord, generic webhook (HTTP POST) + owner email via
Django SMTP (NotificationPreference-gated). SMS / email-as-channel types
stay unsupported and are never delivered as webhooks.
"""

from __future__ import annotations

import logging
import smtplib
import time
from urllib.parse import urlparse

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils.html import escape

from .models import (
    AlertChannel,
    MonitorAlertChannel,
    NotificationDelivery,
    NotificationEvent,
    NotificationPreference,
)

logger = logging.getLogger(__name__)

# Reasonable provider timeout (seconds) — Slack/Discord/webhook.
NOTIFY_TIMEOUT_SECONDS = 8
# Bounded retries for transient provider/network failures.
MAX_DELIVERY_ATTEMPTS = 3
RETRY_BACKOFF_BASE_SECONDS = 0.5

# HTTP statuses worth retrying (transient). Everything else 3xx/4xx is
# permanent — retrying invalid config forever is a bug, not resilience.
RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


class PermanentDeliveryError(Exception):
    """Misconfiguration / rejected payload — do NOT retry."""


class TransientDeliveryError(Exception):
    """Network / provider blip — safe to retry with backoff."""


# ---------------------------------------------------------------------------
# Legacy preference/event helpers (kept for backwards compatibility)
# ---------------------------------------------------------------------------

def get_preferences(user):
    preferences, _ = NotificationPreference.objects.get_or_create(
        user=user
    )
    return preferences


def queue_notification(monitor, check, event_type):
    """Legacy email-gated event creation (pre-Phase-7 callers).

    The central dispatcher (:func:`dispatch_monitor_event`) creates events
    without preference gating so webhook routing works even when the owner
    disabled email for that event type. This helper keeps its historical
    contract for existing callers/tests.
    """
    preferences = get_preferences(monitor.user)

    enabled = {
        NotificationEvent.CHANGE: preferences.email_on_change,
        NotificationEvent.FAILURE: preferences.email_on_failure,
        NotificationEvent.RECOVERY: preferences.email_on_recovery,
    }.get(event_type, False)

    if not enabled:
        return False

    try:
        with transaction.atomic():
            NotificationEvent.objects.create(
                monitor=monitor,
                monitor_check=check,
                event_type=event_type,
            )
    except IntegrityError:
        return False

    return True


def _record_event(monitor, check, event_type):
    """Create the dedupe-guarded NotificationEvent. Returns (event, created)."""
    try:
        with transaction.atomic():
            event = NotificationEvent.objects.create(
                monitor=monitor,
                monitor_check=check,
                event_type=event_type,
            )
        return event, True
    except IntegrityError:
        event = NotificationEvent.objects.filter(
            monitor_check=check, event_type=event_type
        ).first()
        return event, False


def _build_subject_message(monitor, check, event_type):
    dashboard_url = (
        f"{settings.FRONTEND_URL.rstrip('/')}/dashboard/monitors/{monitor.id}"
    )
    if event_type == NotificationEvent.CHANGE:
        subject = f"Sitemyra: Change detected — {monitor.name}"
        message = (
            f"A change was detected on {monitor.name}.\n\n"
            f"URL: {monitor.url}\n"
            f"Checked: {check.checked_at}\n"
            f"Status: {check.status_code}\n\n"
            f"Review this monitor in Sitemyra: {dashboard_url}\n"
        )
    elif event_type == NotificationEvent.FAILURE:
        subject = f"Sitemyra: Monitor failing — {monitor.name}"
        message = (
            f"A monitor has started failing.\n\n"
            f"Monitor: {monitor.name}\n"
            f"URL: {monitor.url}\n"
            f"Checked: {check.checked_at}\n"
            f"Error: {check.error}\n\n"
            f"Review this monitor in Sitemyra: {dashboard_url}\n"
        )
    else:
        subject = f"Sitemyra: Monitor recovered — {monitor.name}"
        message = (
            f"A monitor has recovered.\n\n"
            f"Monitor: {monitor.name}\n"
            f"URL: {monitor.url}\n"
            f"Checked: {check.checked_at}\n"
            f"Status: {check.status_code}\n\n"
            f"Review this monitor in Sitemyra: {dashboard_url}\n"
        )
    return subject, message


def _transactional_html(subject, message):
    """Build a small, escaped HTML alternative for notification email."""
    dashboard_url = escape(f"{settings.FRONTEND_URL.rstrip('/')}/dashboard")
    safe_subject = escape(subject)
    safe_message = escape(message).replace("\n", "<br />")
    return (
        "<!doctype html><html><body style=\"margin:0;background:#080c14;"
        "color:#e2e8f0;font-family:Arial,sans-serif\">"
        "<div style=\"max-width:640px;margin:0 auto;padding:32px\">"
        "<p style=\"color:#c8ef72;font-weight:700;letter-spacing:1px\">"
        "SITEMYRA</p>"
        f"<h1 style=\"font-size:24px;line-height:1.25\">{safe_subject}</h1>"
        f"<div style=\"font-size:15px;line-height:1.7\">{safe_message}</div>"
        f"<p style=\"margin-top:28px;font-size:13px;color:#94a3b8\">"
        f"<a href=\"{dashboard_url}\" style=\"color:#c8ef72\">Open your dashboard</a>"
        "</p></div></body></html>"
    )


def _send_transactional_email(*, subject, message, recipient):
    """Send text + HTML with the verified sender identity and optional Reply-To.

    Reply-To is opt-in because the transactional sender may not be the best
    public support mailbox. No SMTP credential or provider secret is exposed
    to the frontend.
    """
    kwargs = {
        "subject": subject,
        "message": message,
        "html_message": _transactional_html(subject, message),
        "from_email": None,
        "recipient_list": [recipient],
        "fail_silently": False,
    }
    reply_to = getattr(settings, "EMAIL_REPLY_TO", [])
    if reply_to:
        kwargs["reply_to"] = reply_to
    return send_mail(**kwargs)


def _email_enabled(user, event_type) -> bool:
    prefs = get_preferences(user)
    return {
        NotificationEvent.CHANGE: prefs.email_on_change,
        NotificationEvent.FAILURE: prefs.email_on_failure,
        NotificationEvent.RECOVERY: prefs.email_on_recovery,
    }.get(event_type, False)


# ---------------------------------------------------------------------------
# Safe logging helpers — never log secrets
# ---------------------------------------------------------------------------

def _safe_log_context(monitor, channel, event_type, attempt=None):
    ctx = {
        "monitor_id": str(getattr(monitor, "id", monitor)),
        "channel_id": str(getattr(channel, "id", channel)) if channel else None,
        "event_type": event_type,
        "provider": getattr(channel, "channel_type", "email") if channel else "email",
    }
    if attempt is not None:
        ctx["attempt"] = attempt
    return ctx


def _log_safe(level, msg, monitor, channel, event_type, attempt=None, result=None):
    ctx = _safe_log_context(monitor, channel, event_type, attempt)
    extra = " ".join(f"{k}={v}" for k, v in ctx.items() if v is not None)
    if result is not None:
        extra += f" result={result}"
    getattr(logger, level)("notification %s [%s]", msg, extra)


# ---------------------------------------------------------------------------
# Webhook target validation + SSRF protection
# ---------------------------------------------------------------------------

def validate_webhook_target(raw_url: str) -> str:
    """Validate a webhook URL for SaaS delivery. Returns normalized URL.

    Raises PermanentDeliveryError for misconfiguration/blocked destinations
    (never retried) and TransientDeliveryError for DNS blips (retryable).
    Never includes the secret URL in the exception message.
    """
    if not raw_url or not raw_url.strip():
        raise PermanentDeliveryError("Channel is missing its webhook URL.")
    candidate = raw_url.strip()
    if len(candidate) > 2048:
        raise PermanentDeliveryError("Webhook URL is too long.")
    try:
        parsed = urlparse(candidate)
    except Exception:
        raise PermanentDeliveryError("Webhook URL is invalid.")
    if parsed.scheme.lower() not in ("http", "https"):
        raise PermanentDeliveryError("Webhook URL must use http(s).")
    if not parsed.hostname:
        raise PermanentDeliveryError("Webhook URL is invalid.")
    if parsed.username or parsed.password:
        raise PermanentDeliveryError("Webhook URL must not contain credentials.")
    if parsed.port is not None and parsed.port not in (80, 443):
        raise PermanentDeliveryError("Webhook URL uses a blocked port.")
    # SSRF: reuse the monitor fetcher's guard (blocks loopback / private /
    # link-local / reserved / multicast, localhost, metadata hosts).
    try:
        from monitors.services.fetcher import validate_url as validate_fetch_url

        validate_fetch_url(candidate)
    except Exception as exc:
        from monitors.services.fetcher import SecurityError

        if isinstance(exc, SecurityError):
            raise PermanentDeliveryError("Webhook target is not allowed.")
        msg = str(exc).lower()
        if "dns" in msg or "resolve" in msg:
            raise TransientDeliveryError("Webhook host DNS temporarily failed.")
        raise PermanentDeliveryError("Webhook URL is invalid.")
    return candidate


# ---------------------------------------------------------------------------
# Provider delivery (Slack / Discord / generic webhook)
# ---------------------------------------------------------------------------

def _payload_for(channel_type: str, subject: str, message: str, monitor=None,
                 event_type: str = "") -> dict:
    text = f"*{subject}*\n{message}"
    if channel_type == AlertChannel.SLACK:
        return {"text": text}
    if channel_type == AlertChannel.DISCORD:
        return {"content": text[:1900]}
    return {
        "subject": subject,
        "message": message,
        "monitor": getattr(monitor, "name", ""),
        "url": getattr(monitor, "url", ""),
        "event_type": event_type,
        "monitor_id": str(getattr(monitor, "id", "")),
    }


def _classify_http_status(status_code: int) -> str:
    if 200 <= status_code < 300:
        return "ok"
    if status_code in RETRYABLE_STATUS_CODES:
        return "transient"
    return "permanent"


def deliver_to_channel(channel, subject, message, *, monitor=None,
                       event_type: str = "") -> dict:
    """Deliver one payload to one channel with bounded retries.

    Never raises: returns a result dict the service layer can record.
    Never logs the target URL or any secret.
    """
    import httpx

    channel_id = str(channel.id)
    channel_type = channel.channel_type
    monitor_ref = monitor if monitor is not None else getattr(channel, "user", None)

    if channel_type in AlertChannel.UNSUPPORTED_TYPES:
        _log_safe("warning", "skipped_unsupported", monitor_ref, channel,
                  event_type, result="skipped_unsupported")
        return {
            "ok": False, "channel_id": channel_id, "channel_type": channel_type,
            "attempts": 0, "status": "skipped",
            "error": f"Channel type '{channel_type}' is not implemented.",
            "permanent": True,
        }
    if channel_type not in AlertChannel.SUPPORTED_TYPES:
        _log_safe("warning", "skipped_unknown", monitor_ref, channel,
                  event_type, result="skipped_unknown")
        return {
            "ok": False, "channel_id": channel_id, "channel_type": channel_type,
            "attempts": 0, "status": "skipped",
            "error": f"Unknown channel type '{channel_type}'.",
            "permanent": True,
        }

    raw_target = channel.config_encrypted or ""
    if not raw_target:
        _log_safe("warning", "missing_config", monitor_ref, channel,
                  event_type, result="failed_permanent")
        return {
            "ok": False, "channel_id": channel_id, "channel_type": channel_type,
            "attempts": 0, "status": "failed",
            "error": "Channel is missing its webhook URL.",
            "permanent": True,
        }
    try:
        target = validate_webhook_target(raw_target)
    except PermanentDeliveryError as exc:
        _log_safe("warning", "invalid_config", monitor_ref, channel,
                  event_type, result="failed_permanent")
        return {
            "ok": False, "channel_id": channel_id, "channel_type": channel_type,
            "attempts": 0, "status": "failed", "error": str(exc),
            "permanent": True,
        }
    except TransientDeliveryError as exc:
        _log_safe("warning", "dns_transient", monitor_ref, channel,
                  event_type, result="failed_transient")
        return {
            "ok": False, "channel_id": channel_id, "channel_type": channel_type,
            "attempts": 0, "status": "failed", "error": str(exc),
            "permanent": False,
        }

    payload = _payload_for(channel_type, subject, message,
                           monitor=monitor, event_type=event_type)

    last_error = "Delivery failed."
    status_code = None
    attempts = 0
    for attempt in range(1, MAX_DELIVERY_ATTEMPTS + 1):
        attempts = attempt
        try:
            response = httpx.post(target, json=payload,
                                  timeout=NOTIFY_TIMEOUT_SECONDS)
            status_code = response.status_code
            outcome = _classify_http_status(status_code)
            if outcome == "ok":
                _log_safe("info", "delivered", monitor_ref, channel,
                          event_type, attempt=attempt,
                          result=f"http_{status_code}")
                return {
                    "ok": True, "channel_id": channel_id,
                    "channel_type": channel_type, "attempts": attempts,
                    "status": "delivered", "status_code": status_code,
                    "error": "", "permanent": False,
                }
            if outcome == "transient":
                last_error = f"Provider returned HTTP {status_code}."
                _log_safe("warning", "transient_http", monitor_ref, channel,
                          event_type, attempt=attempt,
                          result=f"http_{status_code}")
            else:
                last_error = (
                    f"Provider rejected the payload (HTTP {status_code})."
                )
                _log_safe("warning", "permanent_http", monitor_ref, channel,
                          event_type, attempt=attempt,
                          result=f"http_{status_code}")
                return {
                    "ok": False, "channel_id": channel_id,
                    "channel_type": channel_type, "attempts": attempts,
                    "status": "failed", "status_code": status_code,
                    "error": last_error, "permanent": True,
                }
        except PermanentDeliveryError as exc:
            last_error = str(exc)
            _log_safe("warning", "failed_permanent", monitor_ref, channel,
                      event_type, attempt=attempt, result="failed_permanent")
            return {
                "ok": False, "channel_id": channel_id,
                "channel_type": channel_type, "attempts": attempts,
                "status": "failed", "error": last_error, "permanent": True,
            }
        except Exception as exc:
            # httpx network errors (Connect/Timeout/HTTPError) are transient:
            # back off and retry within the bounded attempt budget.
            last_error = f"{type(exc).__name__}: {str(exc)[:120]}"
            _log_safe("warning", "transient_network", monitor_ref, channel,
                      event_type, attempt=attempt, result="failed_transient")
        if attempt < MAX_DELIVERY_ATTEMPTS:
            time.sleep(RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))

    _log_safe("error", "failed_exhausted", monitor_ref, channel,
              event_type, attempt=attempts, result="failed_exhausted")
    return {
        "ok": False, "channel_id": channel_id, "channel_type": channel_type,
        "attempts": attempts, "status": "failed",
        "status_code": status_code, "error": last_error, "permanent": False,
    }


# ---------------------------------------------------------------------------
# Owner email (real SMTP via Django) — NOT a webhook
# ---------------------------------------------------------------------------

def send_owner_email(monitor, subject, message) -> dict:
    """Send the owner email once. Returns a result dict, never raises."""
    recipient = getattr(getattr(monitor, "user", None), "email", "")
    if not recipient:
        _log_safe("warning", "email_no_recipient", monitor, None, "")
        return {"ok": False, "status": "failed",
                "error": "Monitor owner has no email address.",
                "attempts": 0, "permanent": True}
    try:
        _send_transactional_email(
            subject=subject,
            message=message,
            recipient=recipient,
        )
    except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused) as exc:
        _log_safe("warning", "email_rejected", monitor, None, "")
        return {"ok": False, "status": "failed",
                "error": f"Email rejected: {str(exc)[:150]}",
                "attempts": 1, "permanent": True}
    except Exception as exc:
        # Connection/timeout/auth errors: single bounded retry only when the
        # first attempt likely never sent (avoids duplicate sends).
        transient = isinstance(
            exc,
            (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected,
             TimeoutError, ConnectionError, OSError),
        )
        if transient:
            try:
                time.sleep(RETRY_BACKOFF_BASE_SECONDS)
                _send_transactional_email(
                    subject=subject,
                    message=message,
                    recipient=recipient,
                )
                _log_safe("info", "email_delivered_retry", monitor, None, "")
                return {"ok": True, "status": "delivered", "error": "",
                        "attempts": 2, "permanent": False}
            except Exception as retry_exc:
                _log_safe("error", "email_failed", monitor, None, "")
                return {"ok": False, "status": "failed",
                        "error": f"Email failed: {str(retry_exc)[:150]}",
                        "attempts": 2, "permanent": False}
        _log_safe("error", "email_failed", monitor, None, "")
        return {"ok": False, "status": "failed",
                "error": f"Email failed: {str(exc)[:150]}",
                "attempts": 1, "permanent": False}
    _log_safe("info", "email_delivered", monitor, None, "")
    return {"ok": True, "status": "delivered", "error": "",
            "attempts": 1, "permanent": False}


def send_monitor_email(event_id):
    """Celery-compatible email sender (email only, no webhook fan-out).

    Kept for backwards compatibility with queued tasks. The central
    dispatcher is the primary path for new events.
    """
    event = NotificationEvent.objects.select_related(
        "monitor",
        "monitor_check",
        "monitor__user",
    ).get(id=event_id)

    monitor = event.monitor
    check = event.monitor_check
    if not _email_enabled(monitor.user, event.event_type):
        logger.info("notification email_skipped [monitor_id=%s event_type=%s]",
                    monitor.id, event.event_type)
        return

    subject, message = _build_subject_message(monitor, check, event.event_type)
    result = send_owner_email(monitor, subject, message)
    NotificationDelivery.objects.create(
        event=event, monitor=monitor, channel=None, channel_type="email",
        event_type=event.event_type,
        status=(NotificationDelivery.DELIVERED if result["ok"]
                else NotificationDelivery.FAILED),
        attempts=result.get("attempts", 1),
        detail=result.get("error", "")[:300],
    )
    if not result["ok"] and not result.get("permanent"):
        raise TransientDeliveryError(result["error"])


# ---------------------------------------------------------------------------
# Central dispatcher — the single notification path for every engine
# ---------------------------------------------------------------------------

def get_monitor_channels(monitor):
    """Channels explicitly assigned to this monitor (tenant-checked)."""
    linked_ids = MonitorAlertChannel.objects.filter(
        monitor=monitor
    ).values_list("channel_id", flat=True)
    channels = (
        AlertChannel.objects.filter(id__in=list(linked_ids))
        .select_related("workspace")
    )
    # Defense in depth: drop links that cross tenant boundaries even if
    # they were inserted outside the validated API path.
    result = []
    for channel in channels:
        if channel.user_id == monitor.user_id:
            result.append(channel)
        elif (
            channel.workspace_id is not None
            and getattr(monitor, "workspace_id", None) is not None
            and channel.workspace_id == monitor.workspace_id
        ):
            result.append(channel)
        else:
            logger.warning(
                "notification cross_tenant_link_dropped "
                "[monitor_id=%s channel_id=%s]",
                monitor.id, channel.id,
            )
    return result


def dispatch_monitor_event(monitor, check, event_type) -> dict:
    """Central notification entrypoint. Never raises.

    Records the event (dedupe-guarded), sends owner email when the owner's
    preferences enable it, and dispatches to the monitor's assigned
    channels with per-channel failure isolation. Returns a summary.
    """
    summary: dict = {
        "event_type": event_type,
        "monitor_id": str(monitor.id),
        "status": "dispatched",
        "email": None,
        "channels": [],
    }
    try:
        if event_type not in (
            NotificationEvent.CHANGE,
            NotificationEvent.FAILURE,
            NotificationEvent.RECOVERY,
        ):
            summary["status"] = "skipped"
            return summary

        event, created = _record_event(monitor, check, event_type)
        if not created:
            summary["status"] = "duplicate"
            summary["event_id"] = str(event.id) if event else None
            return summary
        summary["event_id"] = str(event.id)

        subject, message = _build_subject_message(monitor, check, event_type)

        # Owner email (SMTP, preference-gated) — isolated.
        try:
            if _email_enabled(monitor.user, event_type):
                email_result = send_owner_email(monitor, subject, message)
                summary["email"] = email_result
                NotificationDelivery.objects.create(
                    event=event, monitor=monitor, channel=None,
                    channel_type="email", event_type=event_type,
                    status=(NotificationDelivery.DELIVERED if email_result["ok"]
                            else NotificationDelivery.FAILED),
                    attempts=email_result.get("attempts", 1),
                    detail=email_result.get("error", "")[:300],
                )
            else:
                summary["email"] = {"ok": False, "status": "skipped",
                                    "error": "Disabled by preferences."}
                NotificationDelivery.objects.create(
                    event=event, monitor=monitor, channel=None,
                    channel_type="email", event_type=event_type,
                    status=NotificationDelivery.SKIPPED, attempts=0,
                    detail="Disabled by preferences.",
                )
        except Exception as exc:  # never break the monitor task
            logger.exception("notification email_isolated_error "
                             "[monitor_id=%s]", monitor.id)
            summary["email"] = {"ok": False, "status": "failed",
                                "error": f"{type(exc).__name__}"}

        # Per-monitor channels — one channel can never break the others.
        for channel in get_monitor_channels(monitor):
            try:
                result = deliver_to_channel(
                    channel, subject, message,
                    monitor=monitor, event_type=event_type,
                )
            except Exception as exc:  # absolute isolation guard
                logger.exception("notification channel_isolated_error "
                                 "[monitor_id=%s channel_id=%s]",
                                 monitor.id, channel.id)
                result = {
                    "ok": False, "channel_id": str(channel.id),
                    "channel_type": channel.channel_type, "attempts": 0,
                    "status": "failed",
                    "error": f"{type(exc).__name__}",
                    "permanent": False,
                }
            summary["channels"].append(result)
            try:
                NotificationDelivery.objects.create(
                    event=event, monitor=monitor, channel=channel,
                    channel_type=channel.channel_type,
                    event_type=event_type,
                    status=(NotificationDelivery.DELIVERED if result["ok"]
                            else NotificationDelivery.FAILED),
                    attempts=result.get("attempts", 1),
                    detail=(result.get("error", "")
                            or f"HTTP {result.get('status_code', '')}").strip()[:300],
                )
            except Exception:
                logger.exception("notification delivery_record_failed "
                                 "[monitor_id=%s]", monitor.id)
            if result.get("ok"):
                try:
                    if not channel.verified:
                        channel.verified = True
                        channel.save(update_fields=["verified"])
                except Exception:
                    pass
        return summary
    except Exception as exc:  # notifications never fail the monitor check
        logger.exception("notification dispatcher_isolated_error "
                         "[monitor_id=%s]", getattr(monitor, "id", "?"))
        summary["status"] = "error"
        summary["error"] = f"{type(exc).__name__}"
        return summary


def test_channel_delivery(channel, user=None) -> dict:
    """Deliver a test payload via the real provider path. Never raises."""
    monitor_stub = type("MonitorStub", (), {
        "id": "test", "name": "Sitemyra test monitor",
        "url": "https://example.com",
        "user": user or getattr(channel, "user", None),
    })()
    subject = "Sitemyra: Test notification"
    message = (
        f"Channel '{channel.name}' ({channel.channel_type}) is configured "
        "correctly. This is a test notification."
    )
    result = deliver_to_channel(channel, subject, message,
                                monitor=monitor_stub, event_type="test")
    if result.get("ok"):
        try:
            channel.verified = True
            channel.save(update_fields=["verified"])
        except Exception:
            pass
    return result


# Legacy name kept for backwards compatibility (Phase 1 callers/tests).
# Fan-out was removed in Phase 7: only channels explicitly linked to the
# monitor are notified. Prefer dispatch_monitor_event for new code.
def dispatch_webhooks(monitor, subject, message, event_type=""):
    results = []
    for channel in get_monitor_channels(monitor):
        try:
            results.append(
                deliver_to_channel(
                    channel, subject, message,
                    monitor=monitor, event_type=event_type,
                )
            )
        except Exception:
            logger.exception(
                "notification channel_isolated_error [monitor_id=%s]",
                getattr(monitor, "id", "?"),
            )
    return results
