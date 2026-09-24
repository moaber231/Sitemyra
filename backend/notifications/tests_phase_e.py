"""Phase E tests — docs/OPTIMIZATION-PLAN.md D7/D9.

- Both engines' notification call sites hand events off via
  deliver_monitor_event.delay: no SMTP/webhook work on a check's
  critical path, and nothing dispatched inline when the handoff is
  queued (event rows appear only when the queue runs the task).
- Development settings run Celery eagerly so local/test behaviour
  stays synchronous — the plan's D7 gate, asserted here.
- The digest rewrite must produce byte-identical email bodies with a
  flat query count (comparison against a verbatim legacy copy).
"""
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from accounts.models import User
from monitors.models import (
    AdvancedMonitorConfig,
    Monitor,
    MonitorCheck,
    PricePoint,
)
from monitors.services.browser_fetcher import BrowserResult
from monitors.services.fetcher import FetchError, FetchResult
from monitors.services.normalizer import content_hash
from notifications import tasks as notify_tasks
from notifications.models import NotificationEvent


class DevelopmentEagerGateTests(TestCase):
    def test_celery_runs_eagerly_under_development_settings(self):
        # Plan D7 relies on this: deliver_monitor_event.delay() runs
        # synchronously in dev/tests, so notification assertions (every
        # existing notification test included) observe dispatches with
        # no broker. Production settings must never set this flag.
        self.assertTrue(settings.CELERY_TASK_ALWAYS_EAGER)


class NotificationHandoffTests(TestCase):
    """Both engines hand off via deliver_monitor_event.delay — the check
    task itself never dispatches notifications inline (plan D7)."""

    def setUp(self):
        self.user = User.objects.create_user(
            "handoff@example.com", "a-strong-password"
        )
        self.monitor = Monitor.objects.create(
            user=self.user,
            name="Handoff",
            url="https://example.com",
            check_interval=900,
            timeout=15,
        )
        self.delay = mock.patch(
            "notifications.tasks.deliver_monitor_event.delay"
        ).start()
        self.addCleanup(mock.patch.stopall)

    def test_http_engine_failure_event_is_handed_off(self):
        from monitors.tasks import check_monitor

        with mock.patch(
            "monitors.tasks.fetch_url",
            side_effect=FetchError("connection refused"),
        ):
            result = check_monitor(str(self.monitor.id))

        self.assertEqual(result["status"], "failed")
        self.delay.assert_called_once()
        monitor_arg, check_arg, event_arg = self.delay.call_args[0]
        self.assertEqual(monitor_arg, str(self.monitor.id))
        self.assertEqual(event_arg, "failure")

        check = MonitorCheck.objects.get(id=check_arg)
        self.assertEqual(check.monitor_id, self.monitor.id)
        self.assertIn("connection refused", check.error)
        # Handed off, not executed: no event exists until the queue
        # runs deliver_monitor_event.
        self.assertEqual(NotificationEvent.objects.count(), 0)

    def test_http_engine_change_event_is_handed_off(self):
        from monitors.tasks import check_monitor

        self.monitor.last_content_hash = content_hash(
            b"previous content", "text/html"
        )
        self.monitor.save(update_fields=["last_content_hash", "updated_at"])

        fetch_result = FetchResult(
            status_code=200,
            response_time_ms=42,
            content=b"current content",
            content_type="text/html",
        )
        with mock.patch(
            "monitors.tasks.fetch_url", return_value=fetch_result
        ):
            check_monitor(str(self.monitor.id))

        self.delay.assert_called_once()
        monitor_arg, check_arg, event_arg = self.delay.call_args[0]
        self.assertEqual(monitor_arg, str(self.monitor.id))
        self.assertEqual(event_arg, "change")

        check = MonitorCheck.objects.get(id=check_arg)
        self.assertTrue(check.changed)
        self.assertEqual(NotificationEvent.objects.count(), 0)

    def test_advanced_engine_change_event_is_handed_off(self):
        AdvancedMonitorConfig.objects.create(
            monitor=self.monitor,
            mode=AdvancedMonitorConfig.DOM,
            selector="body",
        )
        MonitorCheck.objects.create(
            monitor=self.monitor,
            checked_at=timezone.now() - timedelta(minutes=5),
            status_code=200,
            response_time_ms=30,
            content_hash="stale-hash",
            changed=True,
        )
        browser_result = BrowserResult(
            status_code=200,
            response_time_ms=55,
            html="<html><body><p>fresh content</p></body></html>",
            screenshot=b"",
        )
        with mock.patch(
            "monitors.advanced_tasks.fetch_with_browser",
            return_value=browser_result,
        ), mock.patch(
            "monitors.advanced_tasks.save_artifact",
            return_value="artifacts/fake.html",
        ):
            from monitors.advanced_tasks import run_advanced_monitor

            run_advanced_monitor(str(self.monitor.id))

        self.delay.assert_called_once()
        monitor_arg, check_arg, event_arg = self.delay.call_args[0]
        self.assertEqual(monitor_arg, str(self.monitor.id))
        self.assertEqual(event_arg, "change")
        self.assertTrue(
            MonitorCheck.objects.filter(
                id=check_arg, changed=True, error=""
            ).exists()
        )
        self.assertEqual(NotificationEvent.objects.count(), 0)


# ---------------------------------------------------------------------------
# Weekly digest — byte-identical body comparison (plan D9).
# ---------------------------------------------------------------------------

FROZEN_NOW = datetime(2026, 9, 17, 12, 0, 0, tzinfo=dt_timezone.utc)


def _legacy_send_weekly_digests():
    """Verbatim copy of the pre-Phase-E send_weekly_digests — the plan's
    comparison baseline (1 + U×2 + U×M×4 queries, one per monitor row)."""
    from django.core.mail import send_mail
    from django.db.models import Avg
    from django.utils import timezone as _tz

    from monitors.models import Monitor, MonitorCheck, PricePoint

    User = get_user_model()
    now = _tz.now()
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


class DigestByteIdenticalTests(TestCase):
    """Plan D9 gate: same email body, flat query count."""

    def setUp(self):
        self.alice = User.objects.create_user(
            "alice@example.com", "a-strong-password"
        )
        self.bob = User.objects.create_user(
            "bob@example.com", "a-strong-password"
        )
        carol = User.objects.create_user(
            "carol@example.com", "a-strong-password"
        )
        carol.is_active = False
        carol.save(update_fields=["is_active"])

        # Alice's monitors, created in line order (Monitor.Meta ordering
        # is -created_at, which decides the digest line order).
        alpha = self._monitor(self.alice, "Alpha")
        beta = self._monitor(self.alice, "Beta")
        self._monitor(self.alice, "Gamma")
        delta = self._monitor(self.alice, "Delta")
        epsilon = self._monitor(self.bob, "Epsilon")
        self._monitor(carol, "Zeta")

        # Alpha:3 in-window checks (one error, one null latency) and one
        # out-of-window check that must not influence uptime/avg.
        self._check(alpha, FROZEN_NOW - timedelta(days=2), 100)
        self._check(alpha, FROZEN_NOW - timedelta(days=1), 200)
        self._check(
            alpha, FROZEN_NOW - timedelta(hours=3), None, error="boom"
        )
        self._check(
            alpha, FROZEN_NOW - timedelta(days=14), 9999, error="old-boom"
        )

        # Price drift must use only in-window price points (the old
        # point is excluded). PricePoint is one-to-one with a check, so
        # each point gets its OWN carrier check — dated OUTSIDE the
        # window so the carriers cannot skew uptime/latency stats.
        old_carrier = self._check(
            alpha, FROZEN_NOW - timedelta(days=16), None
        )
        carrier_1 = self._check(
            alpha, FROZEN_NOW - timedelta(days=16), None
        )
        carrier_2 = self._check(
            alpha, FROZEN_NOW - timedelta(days=16), None
        )
        self._price(alpha, old_carrier, FROZEN_NOW - timedelta(days=14), "1.00")
        self._price(alpha, carrier_1, FROZEN_NOW - timedelta(days=2), "9.99")
        self._price(alpha, carrier_2, FROZEN_NOW - timedelta(days=1), "12.49")

        self._check(beta, FROZEN_NOW - timedelta(hours=6), 50)
        # Gamma: no checks this week -> "no checks" line.
        # Delta: check exists but never measured latency -> avg 0ms.
        self._check(delta, FROZEN_NOW - timedelta(hours=1), None)

        self._check(epsilon, FROZEN_NOW - timedelta(days=3), 10)
        self._check(epsilon, FROZEN_NOW - timedelta(days=1), 20)

    @staticmethod
    def _monitor(user, name):
        return Monitor.objects.create(
            user=user,
            name=name,
            url=f"https://example.com/{name.lower()}",
            check_interval=900,
            timeout=15,
        )

    @staticmethod
    def _check(monitor, checked_at, response_time_ms, error=""):
        return MonitorCheck.objects.create(
            monitor=monitor,
            checked_at=checked_at,
            status_code=500 if error else 200,
            response_time_ms=response_time_ms,
            content_hash=f"hash-{monitor.name}-{checked_at.isoformat()}",
            changed=True,
            error=error,
        )

    @staticmethod
    def _price(monitor, check, created_at, value):
        point = PricePoint.objects.create(
            monitor=monitor,
            monitor_check=check,
            price=Decimal(value),
            currency="USD",
            raw_value=value,
        )
        # created_at is set explicitly so "in/out of window" is exact.
        PricePoint.objects.filter(pk=point.pk).update(created_at=created_at)
        return point

    @staticmethod
    def _outbox():
        return [
            (tuple(message.to), message.subject, message.body)
            for message in mail.outbox
        ]

    def test_body_matches_legacy_and_queries_are_flat(self):
        # New implementation.
        with mock.patch(
            "django.utils.timezone.now", return_value=FROZEN_NOW
        ):
            with CaptureQueriesContext(connection) as new_ctx:
                new_result = notify_tasks.send_weekly_digests()
        new_outbox = self._outbox()

        mail.outbox.clear()

        # Legacy implementation, same frozen clock.
        with mock.patch(
            "django.utils.timezone.now", return_value=FROZEN_NOW
        ):
            with CaptureQueriesContext(connection) as legacy_ctx:
                legacy_result = _legacy_send_weekly_digests()
        legacy_outbox = self._outbox()

        # Byte-identical subject + body per recipient (compared as a
        # mapping so neither side depends on user-iteration order).
        self.assertEqual(
            {to: (subject, body) for to, subject, body in new_outbox},
            {to: (subject, body) for to, subject, body in legacy_outbox},
        )
        self.assertEqual(new_result, legacy_result)
        # alice + bob only — the inactive user gets nothing.
        self.assertEqual(new_result["sent"], 2)

        # Contract spot-checks (any drift in these would also break the
        # byte comparison above):
        bodies = "\n".join(body for _to, _subject, body in new_outbox)
        self.assertIn(
            "66.7% uptime (3 checks), avg latency 150ms", bodies
        )
        self.assertIn("price drift +2.50 USD", bodies)
        self.assertIn("Gamma: no checks this week", bodies)
        self.assertIn("avg latency 0ms", bodies)
        self.assertIn("100.0% uptime (1 checks), avg latency 50ms", bodies)
        self.assertNotIn("Zeta", bodies)

        # Flat:4 queries total regardless of users/monitors/rows, and
        # strictly fewer than the legacy per-monitor storm.
        self.assertLess(
            len(new_ctx.captured_queries),
            len(legacy_ctx.captured_queries),
        )
        self.assertLessEqual(len(new_ctx.captured_queries), 6)
