"""Celery task for workspace invitation email delivery.

Runs on the ``celery_notifications`` worker (routed in
``config.settings.base.CELERY_TASK_ROUTES``), alongside monitor alert
delivery, so invitation mail shares the project's existing queue,
time limits and TLS/auth behaviour.
"""

import logging

from celery import shared_task
from django.conf import settings

from .invitation_email import deliver_invitation_email

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    # Bounded, env-tunable, matching the notification tasks: a slow SMTP
    # target must never pin the worker that also delivers monitor alerts.
    soft_time_limit=settings.NOTIFICATION_TASK_SOFT_TIME_LIMIT,
    time_limit=settings.NOTIFICATION_TASK_TIME_LIMIT,
)
def send_invitation_email(self, invite_id):
    """Deliver one invitation email.

    No autoretry: the sender records a definitive ``failed`` / ``not_configured``
    outcome for rejected or unreachable SMTP, so retrying would risk a
    duplicate message without improving the odds of delivery. The inviter
    sees the recorded status and can share the token link instead.
    """
    result = deliver_invitation_email(invite_id)
    logger.info("workspace_invitation_task_finished status=%s", result.get("status"))
    return result
