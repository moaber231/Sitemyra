from unittest.mock import patch

from django.test import SimpleTestCase

from common.integration_status import integration_status


class IntegrationStatusTests(SimpleTestCase):
    def test_email_requires_password_and_reports_only_missing_variable_names(self):
        env = {
            "EMAIL_HOST": "smtp.example.test",
            "EMAIL_PORT": "465",
            "EMAIL_HOST_USER": "alerts@example.test",
            "EMAIL_HOST_PASSWORD": "",
            "EMAIL_FROM": "alerts@example.test",
        }
        with patch.dict("os.environ", env, clear=False):
            status = integration_status()["optional_integrations"]["smtp_email"]

        self.assertFalse(status["configured"])
        self.assertEqual(status["status"], "not_configured")
        self.assertEqual(status["missing"], ["EMAIL_HOST_PASSWORD"])
        self.assertIn("EMAIL NOT CONFIGURED", status["detail"])
        self.assertNotIn("smtp.example.test", status["detail"])
        self.assertNotIn("alerts@example.test", status["detail"])

    def test_stripe_requires_secret_and_both_price_ids(self):
        env = {
            "STRIPE_SECRET_KEY": "test-only-placeholder",
            "STRIPE_PRICE_PRO": "",
            "STRIPE_PRICE_BUSINESS": "",
            "STRIPE_WEBHOOK_SECRET": "",
        }
        with patch.dict("os.environ", env, clear=False):
            status = integration_status()["optional_integrations"]["stripe"]

        self.assertFalse(status["configured"])
        self.assertEqual(
            set(status["missing"]), {"STRIPE_PRICE_PRO", "STRIPE_PRICE_BUSINESS"}
        )
        self.assertNotIn("test-only-placeholder", status["detail"])

    def test_webhook_destinations_are_reported_as_user_managed(self):
        status = integration_status()["optional_integrations"]["slack_discord_webhook"]

        self.assertEqual(status["status"], "user_managed")
        self.assertFalse(status["configured"])
        self.assertIn("each user", status["detail"].lower())
