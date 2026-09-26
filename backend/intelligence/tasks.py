"""Celery tasks for the intelligence layer.

Deliberately minimal. Analysis is synchronous (the user is waiting and a
real product page fetch is a few hundred milliseconds), and product
observation rides the existing monitor check. The only scheduled work here
is housekeeping: dropping cached analyses that have expired so the table
does not grow without bound.

Task routing: this module is imported by every worker via
``autodiscover_tasks`` and is not part of the Playwright import chain, so
it is safe in the API, beat and HTTP-worker containers.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import UrlAnalysis

logger = logging.getLogger(__name__)


@shared_task(
    soft_time_limit=settings.CLEANUP_TASK_SOFT_TIME_LIMIT,
    time_limit=settings.CLEANUP_TASK_TIME_LIMIT,
)
def expire_url_analyses():
    """Delete cached analyses older than their TTL.

    Rows already converted into monitors stay useful as history, but an
    analysis is a *cache of a fetch*, not a record the user needs forever.
    Anything older than twice the TTL is removed; activated monitors keep
    their own history independently.
    """
    from .services.analysis import ANALYSIS_TTL_MINUTES

    cutoff = timezone.now() - timedelta(minutes=ANALYSIS_TTL_MINUTES * 2)
    deleted, _details = UrlAnalysis.objects.filter(fetched_at__lt=cutoff).delete()
    if deleted:
        logger.info("intelligence expired url analyses [rows=%s]", deleted)
    return deleted
