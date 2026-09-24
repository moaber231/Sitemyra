"""Phase E tests — plan D9: scheduler single-hop + bounded batch, and
the monitor-list flat-query prefetch (response shape unchanged)."""
from datetime import timedelta
from unittest import mock

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User

from .models import AdvancedMonitorConfig, Monitor, MonitorCheck
from .tasks import schedule_due_monitors


class SchedulerSingleHopTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "scheduler@example.com", "a-strong-password"
        )

    def _due(self, name, seconds_overdue=60, mode=None, active=True):
        monitor = Monitor.objects.create(
            user=self.user,
            name=name,
            url=f"https://example.com/{name}",
            check_interval=900,
            timeout=15,
            active=active,
            next_check_at=timezone.now()
            - timedelta(seconds=seconds_overdue),
        )
        if mode is not None:
            AdvancedMonitorConfig.objects.create(
                monitor=monitor, mode=mode
            )
        return monitor

    def test_due_browser_monitor_is_enqueued_directly_single_hop(self):
        monitor = self._due(
            "browser-one", mode=AdvancedMonitorConfig.DOM
        )
        with mock.patch(
            "monitors.tasks.enqueue_browser_check"
        ) as browser, mock.patch(
            "monitors.tasks.enqueue_http_check"
        ) as http, mock.patch(
            "monitors.tasks.dispatch_monitor_check.delay"
        ) as second_hop:
            scheduled = schedule_due_monitors()

        self.assertEqual(scheduled, 1)
        browser.assert_called_once_with(monitor.id)
        http.assert_not_called()
        # The old dispatcher hop (a second message per check) is gone:
        second_hop.assert_not_called()

        monitor.refresh_from_db()
        self.assertGreater(monitor.next_check_at, timezone.now())

    def test_due_http_monitor_goes_to_the_http_queue(self):
        monitor = self._due("http-one")  # no advanced config -> http
        with mock.patch(
            "monitors.tasks.enqueue_browser_check"
        ) as browser, mock.patch(
            "monitors.tasks.enqueue_http_check"
        ) as http:
            scheduled = schedule_due_monitors()

        self.assertEqual(scheduled, 1)
        http.assert_called_once_with(monitor.id)
        browser.assert_not_called()

    def test_inactive_and_future_monitors_are_not_scheduled(self):
        self._due("future", seconds_overdue=-300)  # next_check in future
        self._due("paused", active=False)
        with mock.patch(
            "monitors.tasks.enqueue_browser_check"
        ) as browser, mock.patch(
            "monitors.tasks.enqueue_http_check"
        ) as http:
            scheduled = schedule_due_monitors()

        self.assertEqual(scheduled, 0)
        browser.assert_not_called()
        http.assert_not_called()

    @override_settings(SCHEDULER_BATCH_SIZE=2)
    def test_batch_size_caps_each_tick(self):
        first = self._due("a", seconds_overdue=300)
        second = self._due("b", seconds_overdue=200)
        third = self._due("c", seconds_overdue=100)
        fourth = self._due("d", seconds_overdue=50)

        with mock.patch(
            "monitors.tasks.enqueue_browser_check"
        ), mock.patch(
            "monitors.tasks.enqueue_http_check"
        ) as http:
            scheduled = schedule_due_monitors()

        # Bounded batch: only the two soonest-due monitors are claimed.
        self.assertEqual(scheduled, 2)
        enqueued = {call.args[0] for call in http.call_args_list}
        self.assertEqual(enqueued, {first.id, second.id})

        # Claimed rows advanced past due; the rest stay due for the
        # next tick (nothing is skipped).
        for monitor in (first, second):
            monitor.refresh_from_db()
            self.assertGreater(monitor.next_check_at, timezone.now())
        for monitor in (third, fourth):
            monitor.refresh_from_db()
            self.assertLess(monitor.next_check_at, timezone.now())


class MonitorListFlatQueryTests(APITestCase):
    """Plan D9: the monitor list stays at a flat query count (was 2 per
    monitor: status property + last_response_time_ms) with an unchanged
    response shape and identical values."""

    EXPECTED_KEYS = {
        "id",
        "name",
        "url",
        "workspace",
        "active",
        "check_interval",
        "timeout",
        "next_check_at",
        "last_checked_at",
        "last_success_at",
        "last_changed_at",
        "last_content_hash",
        "last_status_code",
        "last_response_time_ms",
        "status",
        "created_at",
        "updated_at",
    }

    def setUp(self):
        self.user = User.objects.create_user(
            "list@example.com", "a-strong-password"
        )
        self.client.force_authenticate(self.user)

    def _create(self, name, active=True, checks=(), last_checked_at=None):
        monitor = Monitor.objects.create(
            user=self.user,
            name=name,
            url=f"https://example.com/{name}",
            check_interval=900,
            timeout=15,
            active=active,
            last_checked_at=last_checked_at,
        )
        for checked_at, error, changed, response_time_ms in checks:
            MonitorCheck.objects.create(
                monitor=monitor,
                checked_at=checked_at,
                error=error,
                changed=changed,
                response_time_ms=response_time_ms,
                status_code=500 if error else 200,
                content_hash="hash",
            )
        return monitor

    def _list(self):
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(reverse("monitor-list"))
        self.assertEqual(response.status_code, 200)
        return len(ctx.captured_queries), list(response.data)

    def test_query_count_is_flat_and_shape_unchanged(self):
        now = timezone.now()
        self._create("s1", checks=[(now, "", False, 11)])
        self._create("s2", checks=[(now, "boom", False, 22)])
        self._create("s3", checks=[(now, "", True, 33)])

        # Warm any per-process caches (auth, content types) first so the
        # comparison below measures only steady-state behaviour.
        self._list()
        baseline, data = self._list()
        self.assertEqual(len(data), 3)
        self.assertEqual(set(data[0].keys()), self.EXPECTED_KEYS)

        # +7 monitors with multiple checks each: the query count must
        # NOT grow (the old code issued 2 extra queries per monitor).
        for index in range(7):
            self._create(
                f"s{index + 4}",
                checks=[
                    (now - timedelta(minutes=index + 1), "", False, 40 + index),
                    (now, "", index % 2 == 0, 50 + index),
                ],
            )
        grew, data = self._list()
        self.assertEqual(len(data), 10)
        self.assertEqual(grew, baseline)

    def test_status_values_match_previous_semantics(self):
        now = timezone.now()
        # Latest-row selection matters here: the older row is an ERROR
        # while the newest is a clean change — the wrong row would
        # report "failing".
        self._create(
            "changed",
            last_checked_at=now,
            checks=[
                (now - timedelta(minutes=10), "old error", False, 5),
                (now, "", True, 77),
            ],
        )
        self._create(
            "failing",
            last_checked_at=now,
            checks=[(now, "selector exploded", False, None)],
        )
        self._create(
            "healthy",
            last_checked_at=now,
            checks=[(now, "", False, 123)],
        )
        self._create(
            "paused",
            active=False,
            last_checked_at=now,
            checks=[(now, "err", False, 1)],
        )
        self._create("never")  # never checked at all
        self._create(
            "ghost", last_checked_at=now  # last_checked_at, no rows
        )

        _queries, data = self._list()
        by_name = {row["name"]: row for row in data}

        self.assertEqual(by_name["changed"]["status"], "changed")
        self.assertEqual(
            by_name["changed"]["last_response_time_ms"], 77
        )
        self.assertEqual(by_name["failing"]["status"], "failing")
        self.assertIsNone(
            by_name["failing"]["last_response_time_ms"]
        )
        self.assertEqual(by_name["healthy"]["status"], "healthy")
        self.assertEqual(
            by_name["healthy"]["last_response_time_ms"], 123
        )
        self.assertEqual(by_name["paused"]["status"], "paused")
        self.assertEqual(by_name["never"]["status"], "never_checked")
        self.assertIsNone(by_name["never"]["last_response_time_ms"])
        self.assertEqual(by_name["ghost"]["status"], "never_checked")
        self.assertIsNone(by_name["ghost"]["last_response_time_ms"])
