"""Phase 4 Stripe hardening tests (mocked Stripe SDK, no network)."""

import json
import os
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from billing.models import (
    BUSINESS,
    FREE,
    PRO,
    StripeWebhookEvent,
    get_plan_for_user,
    plan_limits,
)
from monitors.models import Monitor


def _auth(client, email="buyer@example.com"):
    from billing.models import get_or_create_subscription

    user = User.objects.create_user(email, "a-strong-password")
    get_or_create_subscription(user)
    client.force_authenticate(user)
    return user


class _FakeCheckoutSessions:
    url = "https://checkout.stripe.com/session/test"

    @staticmethod
    def create(**kwargs):
        assert kwargs["mode"] == "subscription"
        assert kwargs["metadata"]["plan"] in (PRO, BUSINESS)
        assert kwargs["metadata"]["user_id"]
        session = _FakeCheckoutSessions()
        return session


class _FakeCheckout:
    Session = _FakeCheckoutSessions


class _FakeCustomers:
    @staticmethod
    def create(**kwargs):
        assert kwargs.get("email")
        return type("Customer", (), {"id": "cus_test123"})()


class _FakePortalSessions:
    url = "https://billing.stripe.com/portal/test"

    @staticmethod
    def create(**kwargs):
        assert kwargs["customer"].startswith("cus_")
        return _FakePortalSessions()


class _FakePortal:
    Session = _FakePortalSessions


class _FakeStripe:
    Customer = _FakeCustomers
    checkout = _FakeCheckout
    billing_portal = _FakePortal


KEYED_ENV = {
    "STRIPE_SECRET_KEY": "sk_test_123",
    "STRIPE_PRICE_PRO": "price_pro_123",
    "STRIPE_PRICE_BUSINESS": "price_biz_123",
}


class CheckoutTests(APITestCase):
    def test_missing_config_returns_503(self):
        _auth(self.client)
        with patch("billing.views.stripe_client", return_value=None):
            response = self.client.post(
                reverse("billing-checkout"), {"plan": "pro"}, format="json"
            )
        self.assertEqual(
            response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE
        )
        self.assertEqual(response.data["code"], "billing_not_configured")

    def test_missing_price_returns_503(self):
        _auth(self.client)
        env = {"STRIPE_SECRET_KEY": "sk_test_123"}
        with patch.dict(os.environ, env, clear=False), patch(
            "billing.views.stripe_client", return_value=object()
        ):
            for key in ("STRIPE_PRICE_PRO", "STRIPE_PRICE_BUSINESS"):
                os.environ.pop(key, None)
            response = self.client.post(
                reverse("billing-checkout"), {"plan": "pro"}, format="json"
            )
        self.assertEqual(
            response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE
        )
        self.assertEqual(response.data["code"], "price_not_configured")

    def test_successful_checkout(self):
        user = _auth(self.client)
        with patch.dict(os.environ, KEYED_ENV, clear=False), patch(
            "billing.views.stripe_client", return_value=_FakeStripe
        ):
            response = self.client.post(
                reverse("billing-checkout"), {"plan": "pro"}, format="json"
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data["stub"])
        self.assertIn("checkout.stripe.com", response.data["checkout_url"])
        user.subscription.refresh_from_db()
        self.assertEqual(user.subscription.stripe_customer_id, "cus_test123")

    def test_stripe_error_returns_502(self):
        _auth(self.client)

        class _Broken(_FakeStripe):
            class Customer:
                @staticmethod
                def create(**kwargs):
                    raise Exception("card exploded")

        with patch.dict(os.environ, KEYED_ENV, clear=False), patch(
            "billing.views.stripe_client", return_value=_Broken
        ):
            response = self.client.post(
                reverse("billing-checkout"), {"plan": "pro"}, format="json"
            )
        self.assertEqual(
            response.status_code, status.HTTP_502_BAD_GATEWAY
        )
        self.assertEqual(response.data["code"], "stripe_error")


class PortalTests(APITestCase):
    def test_portal_without_customer_returns_409(self):
        _auth(self.client)
        with patch.dict(os.environ, KEYED_ENV, clear=False), patch(
            "billing.views.stripe_client", return_value=_FakeStripe
        ):
            response = self.client.post(reverse("billing-portal"))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "no_stripe_customer")

    def test_portal_success(self):
        user = _auth(self.client)
        user.subscription.stripe_customer_id = "cus_test123"
        user.subscription.save(update_fields=["stripe_customer_id"])
        with patch.dict(os.environ, KEYED_ENV, clear=False), patch(
            "billing.views.stripe_client", return_value=_FakeStripe
        ):
            response = self.client.post(reverse("billing-portal"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["stub"])
        self.assertIn("billing.stripe.com", response.data["portal_url"])


@override_settings(DEBUG=True)
class WebhookLifecycleTests(TestCase):
    def setUp(self):
        from billing.models import get_or_create_subscription

        self.user = User.objects.create_user(
            "sub@example.com", "a-strong-password"
        )
        get_or_create_subscription(self.user)
        self.sub = self.user.subscription
        self.env = patch.dict(
            os.environ,
            {
                **KEYED_ENV,
                "STRIPE_DEV_SKIP_WEBHOOK_VERIFY": "1",
                "STRIPE_WEBHOOK_SECRET": "",
            },
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        from django.test import Client

        self.client = Client()

    def _post(self, event):
        return self.client.post(
            reverse("billing-webhook"),
            data=json.dumps(event),
            content_type="application/json",
        )

    def _completed(self, plan="pro", event_id="evt_1", customer="cus_test123",
                   sub_id="sub_test123", user_id=None):
        return {
            "id": event_id,
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": customer,
                    "subscription": sub_id,
                    "metadata": {
                        "plan": plan,
                        "user_id": user_id or str(self.user.id),
                    },
                }
            },
        }

    def test_successful_subscription(self):
        response = self._post(self._completed())
        self.assertEqual(response.status_code, 200)
        self.sub.refresh_from_db()
        self.assertEqual((self.sub.plan, self.sub.status), (PRO, "active"))
        self.assertEqual(self.sub.stripe_customer_id, "cus_test123")
        self.assertEqual(self.sub.stripe_subscription_id, "sub_test123")
        self.assertEqual(get_plan_for_user(self.user), PRO)

    def test_checkout_without_metadata_plan_ignored(self):
        event = self._completed()
        event["data"]["object"]["metadata"] = {}
        response = self._post(event)
        self.assertEqual(response.status_code, 200)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.plan, FREE)

    def test_payment_failure_and_recovery(self):
        self._post(self._completed())
        failed = {
            "id": "evt_fail",
            "type": "invoice.payment_failed",
            "data": {"object": {"customer": "cus_test123",
                                "subscription": "sub_test123"}},
        }
        self.assertEqual(self._post(failed).status_code, 200)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, "past_due")
        # Grace period: paid features retained.
        self.assertEqual(get_plan_for_user(self.user), PRO)

        paid = {
            "id": "evt_paid",
            "type": "invoice.paid",
            "data": {"object": {"customer": "cus_test123",
                                "subscription": "sub_test123"}},
        }
        self.assertEqual(self._post(paid).status_code, 200)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, "active")

    def test_upgrade_pro_to_business(self):
        self._post(self._completed(plan="pro"))
        updated = {
            "id": "evt_upd",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_test123",
                    "customer": "cus_test123",
                    "status": "active",
                    "cancel_at_period_end": False,
                    "items": {"data": [{"price": {"id": "price_biz_123"}}]},
                }
            },
        }
        self.assertEqual(self._post(updated).status_code, 200)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.plan, BUSINESS)

    def test_cancellation_downgrades_and_pauses_excess(self):
        self._post(self._completed(plan="pro"))
        for i in range(5):
            Monitor.objects.create(
                user=self.user, name=f"M{i}", url="https://example.com"
            )
        self.assertEqual(
            Monitor.objects.filter(user=self.user, active=True).count(), 5
        )
        deleted = {
            "id": "evt_del",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_test123",
                    "customer": "cus_test123",
                }
            },
        }
        self.assertEqual(self._post(deleted).status_code, 200)
        self.sub.refresh_from_db()
        self.assertEqual((self.sub.plan, self.sub.status), (FREE, "canceled"))
        self.assertEqual(self.sub.mrr_cents, 0)
        self.assertEqual(
            Monitor.objects.filter(user=self.user, active=True).count(),
            plan_limits(FREE)["max_monitors"],
        )
        self.assertEqual(get_plan_for_user(self.user), FREE)

    def test_duplicate_webhook_processed_once(self):
        self.assertEqual(self._post(self._completed(event_id="evt_dup")).status_code, 200)
        self.assertEqual(self._post(self._completed(event_id="evt_dup")).status_code, 200)
        self.assertEqual(
            StripeWebhookEvent.objects.filter(event_id="evt_dup").count(), 1
        )
        self.sub.refresh_from_db()
        self.assertEqual((self.sub.plan, self.sub.status), (PRO, "active"))

    def test_tenant_isolation(self):
        from billing.models import get_or_create_subscription

        other = User.objects.create_user("other@example.com", "a-strong-password")
        get_or_create_subscription(other)
        self.sub.stripe_customer_id = "cus_mine"
        self.sub.save(update_fields=["stripe_customer_id"])

        # Event for an UNKNOWN customer must not touch my subscription,
        # even if metadata points at me.
        event = self._completed(
            event_id="evt_x", customer="cus_attacker",
            user_id=str(self.user.id),
        )
        event["type"] = "invoice.payment_failed"
        self.assertEqual(self._post(event).status_code, 200)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, "active")
        other.subscription.refresh_from_db()
        self.assertEqual(other.subscription.status, "active")


class WebhookSignatureTests(TestCase):
    def test_invalid_signature_rejected(self):
        from django.test import Client

        with patch.dict(
            os.environ,
            {**KEYED_ENV, "STRIPE_WEBHOOK_SECRET": "whsec_test"},
            clear=False,
        ), patch(
            "stripe.Webhook.construct_event", side_effect=Exception("bad sig")
        ):
            response = Client().post(
                reverse("billing-webhook"),
                data=json.dumps({"type": "invoice.paid"}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 400)

    def test_valid_signature_processed(self):
        from django.test import Client

        from billing.models import get_or_create_subscription

        user = User.objects.create_user("sig@example.com", "a-strong-password")
        get_or_create_subscription(user)
        event = {
            "id": "evt_sig",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": "cus_sig",
                    "subscription": "sub_sig",
                    "metadata": {"plan": "pro", "user_id": str(user.id)},
                }
            },
        }
        with patch.dict(
            os.environ,
            {**KEYED_ENV, "STRIPE_WEBHOOK_SECRET": "whsec_test"},
            clear=False,
        ), patch(
            "stripe.Webhook.construct_event", return_value=event
        ):
            response = Client().post(
                reverse("billing-webhook"),
                data=json.dumps(event),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200)
        user.subscription.refresh_from_db()
        self.assertEqual(user.subscription.plan, PRO)


class EffectivePlanTests(TestCase):
    def test_incomplete_gets_free_entitlements(self):
        from billing.models import get_or_create_subscription

        user = User.objects.create_user("inc@example.com", "a-strong-password")
        get_or_create_subscription(user)
        sub = user.subscription
        sub.plan = PRO
        sub.status = "incomplete"
        sub.save()
        self.assertEqual(get_plan_for_user(user), FREE)

    def test_past_due_keeps_grace_entitlements(self):
        from billing.models import get_or_create_subscription

        user = User.objects.create_user("pd@example.com", "a-strong-password")
        get_or_create_subscription(user)
        sub = user.subscription
        sub.plan = PRO
        sub.status = "past_due"
        sub.save()
        self.assertEqual(get_plan_for_user(user), PRO)
