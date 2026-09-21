from django.core import mail
from django.test import TestCase

from accounts.models import User
from monitors.models import Monitor, MonitorCheck

from .models import NotificationEvent, NotificationPreference
from .services import queue_notification, send_monitor_email


class NotificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="notify@example.com",
            password="a-strong-password",
        )

        self.monitor = Monitor.objects.create(
            user=self.user,
            name="Example",
            url="https://example.com",
            check_interval=3600,
            timeout=15,
        )

        self.check = MonitorCheck.objects.create(
            monitor=self.monitor,
            checked_at="2026-09-19T12:00:00Z",
            status_code=200,
            response_time_ms=120,
            content_hash="a" * 64,
        )

    def test_change_notification_can_be_queued(self):
        created = queue_notification(
            self.monitor,
            self.check,
            NotificationEvent.CHANGE,
        )

        self.assertTrue(created)
        self.assertEqual(NotificationEvent.objects.count(), 1)

    def test_notification_respects_preferences(self):
        NotificationPreference.objects.create(
            user=self.user,
            email_on_change=False,
        )

        created = queue_notification(
            self.monitor,
            self.check,
            NotificationEvent.CHANGE,
        )

        self.assertFalse(created)
        self.assertEqual(NotificationEvent.objects.count(), 0)

    def test_notification_is_not_duplicated(self):
        first = queue_notification(
            self.monitor,
            self.check,
            NotificationEvent.CHANGE,
        )
        second = queue_notification(
            self.monitor,
            self.check,
            NotificationEvent.CHANGE,
        )

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(NotificationEvent.objects.count(), 1)

    def test_email_is_sent(self):
        event = NotificationEvent.objects.create(
            monitor=self.monitor,
            monitor_check=self.check,
            event_type=NotificationEvent.CHANGE,
        )

        send_monitor_email(event.id)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Change detected", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ["notify@example.com"])
