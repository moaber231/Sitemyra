"""Phase 1 production-safety regression tests (no new integrations)."""

import json
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from monitors.models import ChangeDiff, Monitor, MonitorCheck
from notifications.models import AlertChannel


class UnsafeOAuthBridgeTests(APITestCase):
    def test_self_asserted_email_without_code_is_rejected(self):
        response = self.client.post(
            reverse("oauth-login"),
            {
                "provider": "google",
                "email": "victim@example.com",
                "provider_user_id": "google:victim@example.com",
            },
            format="json",
        )
        # Serializer requires `code` (400) or the view returns 503
        # sso_disabled — either way no account is created or minted.
        self.assertIn(
            response.status_code,
            (
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_503_SERVICE_UNAVAILABLE,
            ),
        )
        self.assertFalse(
            User.objects.filter(email="victim@example.com").exists()
        )

    def test_missing_code_field_is_rejected(self):
        response = self.client.post(
            reverse("oauth-login"), {"provider": "github"}, format="json"
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_400_BAD_REQUEST, status.HTTP_503_SERVICE_UNAVAILABLE),
        )

    def test_password_login_still_works(self):
        User.objects.create_user("user@example.com", "a-strong-password")
        response = self.client.post(
            reverse("login"),
            {"email": "user@example.com", "password": "a-strong-password"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)


class StripeSafetyTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "buyer@example.com", "a-strong-password"
        )
        self.client.force_authenticate(self.user)

    @patch("billing.views.stripe_client", return_value=None)
    def test_checkout_without_keys_returns_503(self, _mock):
        response = self.client.post(
            reverse("billing-checkout"), {"plan": "pro"}, format="json"
        )
        self.assertEqual(
            response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE
        )
        self.assertEqual(response.data["code"], "billing_not_configured")
        self.assertNotIn("checkout_url", response.data)

    @patch("billing.views.stripe_client", return_value=None)
    def test_portal_without_keys_returns_503(self, _mock):
        response = self.client.post(reverse("billing-portal"), {}, format="json")
        self.assertEqual(
            response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE
        )
        self.assertEqual(response.data["code"], "billing_not_configured")

    @patch("billing.views.stripe_client", return_value=None)
    def test_status_reports_billing_not_configured(self, _mock):
        response = self.client.get(reverse("billing-subscription"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["billing_configured"])


class StripeWebhookSecurityTests(TestCase):
    def test_missing_secret_rejected_in_production(self):
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("STRIPE_WEBHOOK_SECRET", None)
            with override_settings(DEBUG=False):
                from django.test import Client

                response = Client().post(
                    reverse("billing-webhook"),
                    data=json.dumps({"type": "invoice.paid"}),
                    content_type="application/json",
                )
                self.assertIn(response.status_code, (400, 503))
                self.assertEqual(response.status_code, 503)

    def test_missing_secret_rejected_without_dev_bypass(self):
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("STRIPE_WEBHOOK_SECRET", None)
            os.environ.pop("STRIPE_DEV_SKIP_WEBHOOK_VERIFY", None)
            with override_settings(DEBUG=True):
                from django.test import Client

                response = Client().post(
                    reverse("billing-webhook"),
                    data=json.dumps({"type": "invoice.paid"}),
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 400)


class ArtifactPathSecurityTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "owner@example.com", "a-strong-password"
        )
        self.client.force_authenticate(self.user)
        self.monitor = Monitor.objects.create(
            user=self.user, name="M", url="https://example.com"
        )
        check = MonitorCheck.objects.create(
            monitor=self.monitor,
            checked_at="2026-09-19T12:00:00Z",
            status_code=200,
            response_time_ms=10,
            content_hash="b" * 64,
        )
        ChangeDiff.objects.create(
            monitor=self.monitor,
            previous_check=check,
            current_check=check,
            diff_type="dom",
            summary="changed",
            artifact_path="/app/storage/monitor-artifacts/x.html",
        )

    def test_diffs_do_not_expose_filesystem_paths(self):
        response = self.client.get(f"/api/monitors/{self.monitor.id}/diffs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        body = json.dumps(response.data, default=str)
        self.assertNotIn("/app/", body)
        self.assertNotIn("artifact_path", body)
        self.assertTrue(response.data[0]["artifact_available"])
        # Phase 5: a same-origin authorized download URL (never a path).
        download_url = response.data[0]["artifact_download_url"]
        self.assertTrue(download_url.endswith("/download/"))
        self.assertNotIn("/app/", download_url)


class UnsupportedChannelTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "chan@example.com", "a-strong-password"
        )
        self.client.force_authenticate(self.user)

    def test_email_channel_rejected(self):
        response = self.client.post(
            reverse("alert-channels"),
            {"channel_type": "email", "name": "E", "config": "x"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sms_channel_rejected(self):
        response = self.client.post(
            reverse("alert-channels"),
            {"channel_type": "sms", "name": "S", "config": "x"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unsupported_existing_channel_skipped_without_post(self):
        from monitors.models import Monitor

        monitor = Monitor.objects.create(
            user=self.user, name="M", url="https://example.com"
        )
        AlertChannel.objects.create(
            user=self.user,
            channel_type="sms",
            name="legacy",
            config_encrypted="https://example.com/hook",
        )
        with patch("httpx.post") as mock_post:
            from notifications.services import dispatch_webhooks

            dispatch_webhooks(monitor, "subject", "message")
            mock_post.assert_not_called()
