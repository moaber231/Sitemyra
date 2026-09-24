from django.conf import settings
from django.utils import timezone

from monitors.models import Monitor


def get_due_monitors(limit=None):
    """Due monitors soonest-first, with their advanced config joined.

    Was dead code; Phase E (plan D9) revived it as the scheduler's
    single "who is due" query. ``limit`` defaults to
    ``settings.SCHEDULER_BATCH_SIZE`` so each60 s tick processes a
    bounded batch instead of the entire due backlog. ``advanced_config``
    is joined because the scheduler makes its routing decision (HTTP vs
    browser queue) inline — that would otherwise be one extra query per
    monitor.
    """
    if limit is None:
        limit = settings.SCHEDULER_BATCH_SIZE

    now = timezone.now()

    return (
        Monitor.objects
        .select_related("advanced_config")
        .filter(
            active=True,
            next_check_at__isnull=False,
            next_check_at__lte=now,
        )
        .order_by("next_check_at")[:limit]
    )
