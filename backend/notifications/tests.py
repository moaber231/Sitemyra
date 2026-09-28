from unittest.mock import patch

from django.core import mail
from django.test import SimpleTestCase, TestCase, override_settings

from accounts.models import User
from monitors.models import Monitor, MonitorCheck

from .models import NotificationEvent, NotificationPreference
from .services import queue_notification, send_monitor_email, send_owner_email
from .tasks import send_weekly_digests


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

    def test_weekly_digest_respects_opt_out(self):
        NotificationPreference.objects.create(
            user=self.user,
            email_weekly_digest=False,
        )

        send_weekly_digests()

        self.assertEqual(len(mail.outbox), 0)


class EmailConfigurationStatusTests(SimpleTestCase):
    @patch.dict(
        "os.environ",
        {
            "EMAIL_HOST": "smtp.example.test",
            "EMAIL_PORT": "465",
            "EMAIL_HOST_USER": "alerts@example.test",
            "EMAIL_FROM": "alerts@example.test",
        },
        clear=False,
    )
    def test_integration_status_names_missing_smtp_password_without_values(self):
        import os

        os.environ.pop("EMAIL_HOST_PASSWORD", None)
        from common.integration_status import integration_status

        smtp = integration_status()["optional_integrations"]["smtp_email"]

        self.assertFalse(smtp["configured"])
        self.assertEqual(smtp["status"], "not_configured")
        self.assertEqual(smtp["missing"], ["EMAIL_HOST_PASSWORD"])
        self.assertIn("EMAIL NOT CONFIGURED", smtp["detail"])
        self.assertNotIn("smtp.example.test", smtp["detail"])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend")
    @patch.dict(
        "os.environ",
        {
            "EMAIL_HOST": "smtp.example.test",
            "EMAIL_PORT": "465",
            "EMAIL_HOST_USER": "alerts@example.test",
            "EMAIL_FROM": "alerts@example.test",
        },
        clear=False,
    )
    def test_owner_email_reports_missing_password_without_attempting_smtp(self):
        import os

        os.environ.pop("EMAIL_HOST_PASSWORD", None)
        monitor = type(
            "MonitorStub",
            (),
            {"user": type("UserStub", (), {"email": "owner@example.test"})()},
        )()
        with patch("notifications.services._send_transactional_email") as send:
            result = send_owner_email(monitor, "subject", "message")

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "not_configured")
        self.assertIn("EMAIL_HOST_PASSWORD", result["error"])
        self.assertEqual(result["attempts"], 0)
        send.assert_not_called()
