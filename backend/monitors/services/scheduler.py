from django.utils import timezone

from monitors.models import Monitor


def get_due_monitors(limit=100):
    now = timezone.now()

    return (
        Monitor.objects
        .filter(
            active=True,
            next_check_at__isnull=False,
            next_check_at__lte=now,
        )
        .order_by("next_check_at")[:limit]
    )
