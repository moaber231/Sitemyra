import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db.models import Avg, Count, Q
from django.utils import timezone

from .services import TransientDeliveryError, send_monitor_email

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    # Only transient provider/network failures retry; permanent
    # rejections (bad config, 4xx) are recorded, not raised, so they
    # fail fast without duplicates.
    autoretry_for=(TransientDeliveryError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    # Bounded (env-tunable): a slow SMTP target can never pin the
    # worker consuming celery_notifications.
    soft_time_limit=settings.NOTIFICATION_TASK_SOFT_TIME_LIMIT,
    time_limit=settings.NOTIFICATION_TASK_TIME_LIMIT,
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
    soft_time_limit=settings.NOTIFICATION_TASK_SOFT_TIME_LIMIT,
    time_limit=settings.NOTIFICATION_TASK_TIME_LIMIT,
)
def deliver_monitor_event(self, monitor_id, check_id, event_type):
    """Queue entrypoint for notification delivery (plan D7, Phase E).

    This is THE path monitor checks use (``deliver_monitor_event.delay``):
    event recording, owner email and webhook delivery all run here, on
    the ``celery_notifications`` worker — never inside an HTTP or
    browser check task. Development and the test suite run Celery
    eagerly (``CELERY_TASK_ALWAYS_EAGER`` in development settings), so
    local behaviour stays synchronous. Bounded retries with exponential
    backoff apply to the whole dispatch; per-check dedupe inside the
    dispatcher prevents duplicate sends.
    """
    from monitors.models import Monitor, MonitorCheck

    from .services import dispatch_monitor_event

    monitor = Monitor.objects.select_related("user").get(id=monitor_id)
    check = MonitorCheck.objects.get(id=check_id)
    return dispatch_monitor_event(monitor, check, event_type)


@shared_task(
    # Full-table digest scan: bounded (env-tunable) so it cannot occupy
    # the notifications worker beyond its budget.
    soft_time_limit=settings.DIGEST_TASK_SOFT_TIME_LIMIT,
    time_limit=settings.DIGEST_TASK_TIME_LIMIT,
)
def send_weekly_digests():
    """Automated Weekly Digest Email: uptime, avg latency, price drift.

    Phase E (plan D9): rewritten from 1 + U×2 + U×M×4 queries (users ×
    monitors × count/error/avg/price per monitor) to FOUR flat queries
    (monitors, one aggregate over the week's checks, one ordered scan
    of the week's price points, users via .iterator()) while the email
    body stays byte-identical — notifications/tests_phase_e.py asserts
    that against a verbatim copy of the old implementation, along with
    the flat query count.
    """
    from monitors.models import Monitor, MonitorCheck, PricePoint

    User = get_user_model()
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    sent = 0

    # Flat pass 1: every monitor, bucketed per user. Monitor.Meta
    # ordering (-created_at) matches the old per-user queryset, so the
    # line order inside each digest is unchanged.
    monitors_by_user: dict = {}
    for monitor_id, user_id, name in Monitor.objects.values_list(
        "id", "user_id", "name"
    ):
        monitors_by_user.setdefault(user_id, []).append(
            (monitor_id, name)
        )

    # Flat pass 2: one aggregate over the week's checks. Monitors with
    # no checks this week never appear -> same "no checks" line as before.
    stats: dict = {}
    week_checks = (
        MonitorCheck.objects.filter(checked_at__gte=week_ago)
        .values("monitor_id")
        .annotate(
            total=Count("id"),
            errors=Count("id", filter=~Q(error="")),
            avg_latency=Avg(
                "response_time_ms",
                filter=Q(response_time_ms__isnull=False),
            ),
        )
    )
    for row in week_checks:
        stats[row["monitor_id"]] = row

    # Flat pass 3: this week's price points, oldest-first per monitor
    # (monitor_id grouping == the old per-monitor order_by("created_at")),
    # streamed with .iterator() so a price-heavy week cannot balloon RAM.
    price_first: dict = {}
    price_last: dict = {}
    price_count: dict = {}
    week_prices = (
        PricePoint.objects.filter(created_at__gte=week_ago)
        .values_list("monitor_id", "price", "currency")
        .order_by("monitor_id", "created_at")
        .iterator(chunk_size=2000)
    )
    for monitor_id, price, currency in week_prices:
        price_count[monitor_id] = price_count.get(monitor_id, 0) + 1
        price_first.setdefault(monitor_id, (price, currency))
        price_last[monitor_id] = (price, currency)

    # Flat pass 4: users (same query as before, streamed).
    for user in User.objects.filter(is_active=True).iterator(
        chunk_size=500
    ):
        entries = monitors_by_user.get(user.id)
        if not entries:
            continue
        lines = []
        for monitor_id, name in entries:
            row = stats.get(monitor_id)
            total = row["total"] if row else 0
            if not total:
                lines.append(f"- {name}: no checks this week")
                continue
            errors = row["errors"] or 0
            uptime = round((total - errors) / total * 100, 1)
            avg_latency = row["avg_latency"] or 0
            price_note = ""
            if price_count.get(monitor_id, 0) >= 2:
                first_price = price_first[monitor_id][0]
                last_price, last_currency = price_last[monitor_id]
                drift = float(last_price) - float(first_price)
                price_note = f", price drift {drift:+.2f} {last_currency}"
            lines.append(
                f"- {name}: {uptime}% uptime ({total} checks), "
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
            # One recipient's failure must not stop the rest — and it
            # is no longer silent (plan D9: log swallowed failures).
            logger.exception(
                "weekly digest email failed [user_id=%s]", user.id
            )
            continue
    return {"sent": sent}
