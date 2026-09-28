from django.urls import reverse
from unittest.mock import patch
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import ApiKey, User
from monitors.models import Monitor, MonitorCheck
from workspaces.models import Workspace, WorkspaceMembership

from .models import NotificationDelivery, NotificationEvent


class NotificationHistoryTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="history-owner@example.com", password="a-strong-password"
        )
        self.other = User.objects.create_user(
            email="history-other@example.com", password="a-strong-password"
        )
        self.monitor = Monitor.objects.create(
            user=self.owner,
            name="Owner monitor",
            url="https://example.com",
            check_interval=3600,
            timeout=15,
        )
        self.owner_delivery = self.delivery(
            self.monitor, detail="private provider response must not be returned"
        )

    @staticmethod
    def delivery(monitor, **overrides):
        event_type = overrides.get("event_type", "change")
        check = MonitorCheck.objects.create(
            monitor=monitor,
            checked_at="2026-09-28T12:00:00Z",
            status_code=200,
            content_hash="a" * 64,
        )
        event = NotificationEvent.objects.create(
            monitor=monitor,
            monitor_check=check,
            event_type=event_type,
        )
        data = {
            "monitor": monitor,
            "event": event,
            "channel_type": "discord",
            "event_type": event_type,
            "status": NotificationDelivery.FAILED,
            "attempts": 2,
            "detail": "Provider returned HTTP 503.",
        }
        data.update(overrides)
        return NotificationDelivery.objects.create(**data)

    def test_history_is_authenticated_and_excludes_other_users(self):
        other_monitor = Monitor.objects.create(
            user=self.other,
            name="Other monitor",
            url="https://other.example",
            check_interval=3600,
            timeout=15,
        )
        self.delivery(other_monitor)
        self.client.force_authenticate(self.owner)

        response = self.client.get(reverse("notification-history"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["monitor_id"], str(self.monitor.id))
        delivery = response.data["results"][0]["deliveries"][0]
        self.assertEqual(delivery["status"], NotificationDelivery.FAILED)
        self.assertEqual(delivery["attempts"], 2)
        self.assertNotIn("detail", delivery)
        self.assertNotIn("config", delivery)

        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get(reverse("notification-history")).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_preferences_expose_only_boolean_email_readiness(self):
        self.client.force_authenticate(self.owner)
        env = {
            "EMAIL_HOST": "smtp.example.test",
            "EMAIL_PORT": "465",
            "EMAIL_HOST_USER": "alerts@example.test",
            "EMAIL_HOST_PASSWORD": "",
            "EMAIL_FROM": "alerts@example.test",
        }
        with patch.dict("os.environ", env, clear=False):
            response = self.client.get(reverse("notification-preferences"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["email_delivery_configured"])
        self.assertNotIn("EMAIL_HOST_PASSWORD", response.data)
        self.assertNotIn("smtp.example.test", str(response.data))

    def test_workspace_members_can_read_workspace_delivery_history(self):
        workspace = Workspace.objects.create(name="Shared", owner=self.owner)
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=self.other,
            role=WorkspaceMembership.VIEWER,
        )
        monitor = Monitor.objects.create(
            user=self.owner,
            workspace=workspace,
            name="Shared monitor",
            url="https://shared.example",
            check_interval=3600,
            timeout=15,
        )
        self.delivery(monitor, status=NotificationDelivery.DELIVERED, attempts=1)
        self.client.force_authenticate(self.other)

        response = self.client.get(reverse("notification-history"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["monitor_name"], "Shared monitor")

    def test_event_remains_visible_when_no_delivery_record_was_created(self):
        check = MonitorCheck.objects.create(
            monitor=self.monitor,
            checked_at="2026-09-28T12:01:00Z",
            status_code=200,
            content_hash="b" * 64,
            changed=True,
        )
        NotificationEvent.objects.create(
            monitor=self.monitor,
            monitor_check=check,
            event_type="change",
        )
        self.client.force_authenticate(self.owner)

        response = self.client.get(reverse("notification-history"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event_without_delivery = next(
            row for row in response.data["results"] if row["deliveries"] == []
        )
        self.assertEqual(event_without_delivery["event_type"], "change")

    def test_monitor_only_api_key_cannot_read_notification_history(self):
        _api_key, raw_key = ApiKey.generate(
            user=self.owner,
            name="monitor-only test key",
            scopes="monitors:read monitors:write",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {raw_key}")

        response = self.client.get(reverse("notification-history"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_history_is_paginated_and_bounds_requested_limit(self):
        self.delivery(self.monitor, event_type="failure")
        self.delivery(self.monitor, event_type="recovery")
        self.client.force_authenticate(self.owner)

        first = self.client.get(reverse("notification-history"), {"limit": 2})
        second = self.client.get(
            reverse("notification-history"), {"limit": 2, "offset": 2}
        )

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["count"], 3)
        self.assertEqual(len(first.data["results"]), 2)
        self.assertEqual(first.data["next_offset"], 2)
        self.assertEqual(len(second.data["results"]), 1)
        self.assertIsNone(second.data["next_offset"])
        self.assertEqual(
            self.client.get(reverse("notification-history"), {"limit": "invalid"}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.get(reverse("notification-history"), {"offset": -1}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
