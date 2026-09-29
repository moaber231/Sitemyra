"""Workspace invitation email delivery.

Reuses the project's existing transactional email sender and Celery
notification queue rather than introducing a second mail path, so
delivery, retries, TLS handling and the SMTP readiness gate behave
exactly as they do for monitor notifications.

Three rules govern this module:

1. Never claim success that did not happen. :func:`deliver_invitation_email`
   reports ``sent`` only when the SMTP server accepted the message, and
   records ``not_configured`` / ``failed`` otherwise.
2. Never leak a secret. No token, credential, or traceback is ever written
   to a log line or to ``WorkspaceInvite.email_error``; logging is limited to
   the invite id and workspace id.
3. Never weaken invitation security. This module only *sends* mail. The
   accept endpoint still requires the signed-in email to match the invited
   address, and only Owner/Admin can read tokens.
"""

from __future__ import annotations

import logging
import smtplib

from django.conf import settings
from django.utils import timezone

from .models import WorkspaceInvite

logger = logging.getLogger(__name__)

# Bounded so a hostile SMTP response can never bloat a model row.
_MAX_ERROR_CHARS = 180


def invitation_accept_url(invite: WorkspaceInvite) -> str:
    """Build the public acceptance URL for an invitation.

    Uses the configured frontend origin (production: https://sitemyra.com).
    The token travels in the query string because that is what the existing
    Workspaces page already reads; the accept endpoint still verifies the
    signed-in email, so a leaked link alone cannot grant access.
    """
    base = str(getattr(settings, "FRONTEND_URL", "")).rstrip("/")
    return f"{base}/dashboard/workspaces?invite={invite.token}"


def _inviter_label(invite: WorkspaceInvite) -> str:
    """Best available identity for the person who sent the invitation."""
    inviter = invite.created_by
    if inviter is None:
        return "A Sitemyra workspace owner"
    email = (getattr(inviter, "email", "") or "").strip()
    return email or "A Sitemyra workspace owner"


def _role_label(role: str) -> str:
    from .models import WorkspaceMembership

    return {
        WorkspaceMembership.ADMIN: "Admin",
        WorkspaceMembership.VIEWER: "Viewer",
    }.get(role, "Viewer")


def _compose(invite: WorkspaceInvite) -> tuple[str, str]:
    """Build the subject and plain-text body for an invitation email."""
    workspace = invite.workspace
    accept_url = invitation_accept_url(invite)
    inviter = _inviter_label(invite)
    role = _role_label(invite.role)

    subject = f"You have been invited to {workspace.name} on Sitemyra"
    message = (
        f"{inviter} invited you to join the workspace \"{workspace.name}\" on Sitemyra.\n\n"
        f"Sitemyra watches your competitors' web pages and tells you when "
        f"something changes. Members of this workspace share its monitors, "
        f"changes and alerts.\n\n"
        f"Role: {role}\n\n"
        f"Accept the invitation:\n{accept_url}\n\n"
        f"You can only accept this invitation while signed in as "
        f"{invite.email}. If you were not expecting this, you can ignore "
        f"this message — no account is created automatically.\n\n"
        f"— Sitemyra\n"
    )
    return subject, message


def _smtp_missing() -> list[str]:
    from common.integration_status import smtp_missing_environment

    return smtp_missing_environment()


def _short_error(exc: Exception) -> str:
    """Reduce an exception to a short, non-sensitive reason string."""
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return "The mail server rejected the SMTP credentials."
    if isinstance(
        exc,
        (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused),
    ):
        return "The mail server refused the sender or recipient address."
    if isinstance(
        exc,
        (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected,
         ConnectionError, TimeoutError, OSError),
    ):
        return "Could not reach the mail server."
    if isinstance(exc, smtplib.SMTPException):
        return "The mail server returned an error."
    return "The invitation email could not be sent."


def _record(invite_id, **fields) -> None:
    WorkspaceInvite.objects.filter(pk=invite_id).update(**fields)


def deliver_invitation_email(invite_id) -> dict:
    """Send one invitation email and record the true outcome.

    Safe to call more than once: an already-accepted invitation is skipped
    rather than re-sent. Returns a small result dict; never raises for a
    delivery failure, so the Celery task records the outcome instead of
    retrying a message that was definitively rejected.
    """
    from notifications.services import _send_transactional_email

    invite = (
        WorkspaceInvite.objects.select_related("workspace", "created_by")
        .filter(pk=invite_id)
        .first()
    )
    if invite is None:
        logger.info("workspace_invitation_missing [invite_id=%s]", invite_id)
        return {"status": "missing", "invite_id": str(invite_id)}

    if invite.accepted:
        # Nothing to send, and nothing was sent: record it honestly.
        _record(invite.id, email_status=WorkspaceInvite.EMAIL_STATUS_SKIPPED,
                email_error="")
        return {"status": "skipped", "invite_id": str(invite.id)}

    # Same readiness gate as monitor notification email: only meaningful when
    # Django is actually going to speak SMTP. A test/dev backend (locmem,
    # console) delivers by its own contract and is never reported unconfigured.
    if settings.EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend":
        missing = _smtp_missing()
        if missing:
            _record(
                invite.id,
                email_status=WorkspaceInvite.EMAIL_STATUS_NOT_CONFIGURED,
                email_error="Email is not configured. Share the invitation link instead.",
            )
            return {"status": "not_configured", "invite_id": str(invite.id)}

    subject, message = _compose(invite)
    try:
        _send_transactional_email(
            subject=subject,
            message=message,
            recipient=invite.email,
        )
    except Exception as exc:  # noqa: BLE001 - outcome is recorded, not raised
        reason = _short_error(exc)[:_MAX_ERROR_CHARS]
        _record(
            invite.id,
            email_status=WorkspaceInvite.EMAIL_STATUS_FAILED,
            email_error=reason,
            email_sent_at=None,
        )
        # No token, address, credential, or exception text in the log line.
        logger.warning(
            "workspace_invitation_email_failed [invite_id=%s workspace_id=%s reason=%s]",
            invite.id,
            invite.workspace_id,
            reason,
        )
        return {"status": "failed", "invite_id": str(invite.id), "error": reason}

    _record(
        invite.id,
        email_status=WorkspaceInvite.EMAIL_STATUS_SENT,
        email_sent_at=timezone.now(),
        email_error="",
    )
    logger.info(
        "workspace_invitation_email_sent [invite_id=%s workspace_id=%s]",
        invite.id,
        invite.workspace_id,
    )
    return {"status": "sent", "invite_id": str(invite.id)}
