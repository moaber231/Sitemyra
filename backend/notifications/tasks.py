from datetime import timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db.models import Avg, Count, Q
from django.utils import timezone

from .services import TransientDeliveryError, send_monitor_email


@shared_task(
    bind=True,
    # Only transient provider/network failures retry; permanent
    # rejections (bad config, 4xx) are recorded, not raised, so they
    # fail fast without duplicates.
    autoretry_for=(TransientDeliveryError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def send_notification_email(self, event_id):
    try:
        send_monitor_email(event_id)
    except TransientDeliveryError:
        raise
    return {"status": "sent", "event_id": str(event_id)}


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def deliver_monitor_event(self, monitor_id, check_id, event_type):
    """Async wrapper around the central dispatcher (optional path).

    Monitor tasks call :func:`dispatch_monitor_event` synchronously; this
    task exists for queued/test deliveries. Bounded retries with
    exponential backoff apply to the whole dispatch; per-check dedupe
    inside the dispatcher prevents duplicate sends.
    """
    from monitors.models import Monitor, MonitorCheck

    from .services import dispatch_monitor_event

    monitor = Monitor.objects.select_related("user").get(id=monitor_id)
    check = MonitorCheck.objects.get(id=check_id)
    return dispatch_monitor_event(monitor, check, event_type)


@shared_task
def send_weekly_digests():
    """Automated Weekly Digest Email: uptime, avg latency, price drift."""
    from monitors.models import Monitor, MonitorCheck, PricePoint

    User = get_user_model()
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    sent = 0

    for user in User.objects.filter(is_active=True):
        monitors = Monitor.objects.filter(user=user)
        if not monitors.exists():
            continue
        lines = []
        for monitor in monitors:
            checks = MonitorCheck.objects.filter(
                monitor=monitor, checked_at__gte=week_ago
            )
            total = checks.count()
            if total == 0:
                lines.append(f"- {monitor.name}: no checks this week")
                continue
            errors = checks.exclude(error="").count()
            uptime = round((total - errors) / total * 100, 1)
            avg_latency = (
                checks.filter(response_time_ms__isnull=False).aggregate(
                    avg=Avg("response_time_ms")
                )["avg"]
                or 0
            )
            price_note = ""
            prices = list(
                PricePoint.objects.filter(
                    monitor=monitor, created_at__gte=week_ago
                ).order_by("created_at")
            )
            if len(prices) >= 2:
                drift = float(prices[-1].price) - float(prices[0].price)
                price_note = f", price drift {drift:+.2f} {prices[-1].currency}"
            lines.append(
                f"- {monitor.name}: {uptime}% uptime ({total} checks), "
                f"avg latency {round(avg_latency)}ms{price_note}"
            )
        body = (
            f"Hi {user.email},\n\nYour Sitemyra weekly digest "
            f"({week_ago.date()} -> {now.date()}):\n\n"
            + "\n".join(lines)
            + "\n\nHappy monitoring,\nSitemyra"
        )
        try:
            send_mail(
                subject="Sitemyra: Your weekly monitoring digest",
                message=body,
                from_email=None,
                recipient_list=[user.email],
                fail_silently=False,
            )
            sent += 1
        except Exception:
            continue
    return {"sent": sent}
