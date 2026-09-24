"""Phase 7 — notification reliability & routing tests.

Covers routing, all four engines, providers, the test endpoint, and
reliability guarantees. Hermetic: HTTP delivery is mocked at httpx,
DNS is shimmed to a public IP (SSRF-blocked hosts never reach DNS).
"""

import smtplib
import socket
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from monitors.models import (
    AdvancedMonitorConfig,
    ChangeDiff,
    Monitor,
    MonitorCheck,
    PricePoint,
)
from monitors.services.browser_fetcher import BrowserFetchError, BrowserResult
from monitors.services.fetcher import FetchError, FetchResult
from notifications.models import (
    AlertChannel,
    MonitorAlertChannel,
    NotificationDelivery,
    NotificationEvent,
)
from notifications import services as notify_services


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


def _public_dns(host, *args, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]


class DnsShimMixin:
    def setUp(self):
        super().setUp()
        dns = mock.patch("socket.getaddrinfo", side_effect=_public_dns)
        dns.start()
        self.addCleanup(dns.stop)
        # No real sleeping during retries.
        backoff = mock.patch.object(
            notify_services, "RETRY_BACKOFF_BASE_SECONDS", 0
        )
        backoff.start()
        self.addCleanup(backoff.stop)


def make_user(email):
    return User.objects.create_user(email=email, password="a-strong-password")


def make_monitor(user, name="M", url="https://example.com"):
    return Monitor.objects.create(
        user=user, name=name, url=url, check_interval=3600, timeout=15
    )


def make_channel(user, ctype="slack", name="hook", url="https://example.com/hook"):
    return AlertChannel.objects.create(
        user=user, channel_type=ctype, name=name, config_encrypted=url
    )


def make_check(monitor, error="", changed=False, hash="h"):
    return MonitorCheck.objects.create(
        monitor=monitor,
        checked_at=timezone.now(),
        status_code=200 if not error else None,
        response_time_ms=50,
        content_hash=hash,
        changed=changed,
        error=error,
    )


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

class RoutingTests(DnsShimMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user("route@example.com")
        self.other = make_user("route-other@example.com")
        self.monitor = make_monitor(self.user)
        self.assigned = make_channel(self.user, url="https://example.com/assigned")
        self.unrelated = make_channel(self.user, url="https://example.com/unrelated")
        self.foreign = make_channel(self.other, url="https://example.com/foreign")
        MonitorAlertChannel.objects.create(
            monitor=self.monitor, channel=self.assigned
        )

    def test_assigned_channel_is_notified(self):
        check = make_check(self.monitor)
        with mock.patch("httpx.post", return_value=FakeResponse(200)) as post:
            summary = notify_services.dispatch_monitor_event(
                self.monitor, check, NotificationEvent.CHANGE
            )
        posted_urls = [c.args[0] for c in post.call_args_list]
        self.assertIn("https://example.com/assigned", posted_urls)
        self.assertEqual(summary["status"], "dispatched")
        self.assertTrue(
            NotificationDelivery.objects.filter(
                monitor=self.monitor, channel=self.assigned,
                status=NotificationDelivery.DELIVERED,
            ).exists()
        )

    def test_unrelated_channel_is_not_notified(self):
        check = make_check(self.monitor)
        with mock.patch("httpx.post", return_value=FakeResponse(200)) as post:
            notify_services.dispatch_monitor_event(
                self.monitor, check, NotificationEvent.CHANGE
            )
        posted_urls = [c.args[0] for c in post.call_args_list]
        self.assertNotIn("https://example.com/unrelated", posted_urls)
        self.assertFalse(
            NotificationDelivery.objects.filter(channel=self.unrelated).exists()
        )

    def test_cross_tenant_link_is_dropped_at_dispatch(self):
        # Even if a bad link row exists, another tenant's channel is ignored.
        MonitorAlertChannel.objects.create(
            monitor=self.monitor, channel=self.foreign
        )
        check = make_check(self.monitor)
        with mock.patch("httpx.post", return_value=FakeResponse(200)) as post:
            notify_services.dispatch_monitor_event(
                self.monitor, check, NotificationEvent.CHANGE
            )
        posted_urls = [c.args[0] for c in post.call_args_list]
        self.assertNotIn("https://example.com/foreign", posted_urls)
        self.assertFalse(
            NotificationDelivery.objects.filter(channel=self.foreign).exists()
        )

    def test_duplicate_event_is_not_resent(self):
        check = make_check(self.monitor)
        with mock.patch("httpx.post", return_value=FakeResponse(200)) as post:
            first = notify_services.dispatch_monitor_event(
                self.monitor, check, NotificationEvent.CHANGE
            )
            second = notify_services.dispatch_monitor_event(
                self.monitor, check, NotificationEvent.CHANGE
            )
        self.assertEqual(first["status"], "dispatched")
        self.assertEqual(second["status"], "duplicate")
        assigned_posts = [
            c for c in post.call_args_list
            if c.args[0] == "https://example.com/assigned"
        ]
        self.assertEqual(len(assigned_posts), 1)


# ---------------------------------------------------------------------------
# HTTP/content engine
# ---------------------------------------------------------------------------

class HttpEngineNotificationTests(DnsShimMixin, TestCase):
    def setUp(self):
        super().setUp()
        from monitors.tasks import check_monitor  # noqa

        self.check_monitor = check_monitor
        self.user = make_user("http@example.com")
        self.monitor = make_monitor(self.user)
        self.channel = make_channel(self.user)
        MonitorAlertChannel.objects.create(
            monitor=self.monitor, channel=self.channel
        )

    def _run_check(self, fetch_result=None, fetch_error=None):
        target = "monitors.tasks.fetch_url"
        if fetch_error is not None:
            cm = mock.patch(target, side_effect=fetch_error)
        else:
            cm = mock.patch(target, return_value=fetch_result)
        with cm, mock.patch("httpx.post", return_value=FakeResponse(200)) as post:
            result = self.check_monitor(str(self.monitor.id))
        return result, post

    def test_http_change_triggers_notification(self):
        from monitors.services.normalizer import content_hash

        old_hash = content_hash(b"old content", "text/html")
        self.monitor.last_content_hash = old_hash
        self.monitor.save(update_fields=["last_content_hash"])
        result, post = self._run_check(
            fetch_result=FetchResult(
                status_code=200, response_time_ms=60,
                content=b"new content here", content_type="text/html",
            )
        )
        self.assertEqual(result["status"], "changed")
        self.assertTrue(post.called)
        self.assertTrue(
            NotificationEvent.objects.filter(
                monitor=self.monitor, event_type=NotificationEvent.CHANGE
            ).exists()
        )

    def test_http_failure_triggers_notification(self):
        result, post = self._run_check(fetch_error=FetchError("boom"))
        self.assertEqual(result["status"], "failed")
        self.assertTrue(
            NotificationEvent.objects.filter(
                monitor=self.monitor, event_type=NotificationEvent.FAILURE
            ).exists()
        )
        self.assertTrue(post.called)

    def test_http_recovery_triggers_notification(self):
        make_check(self.monitor, error="previous outage")
        result, post = self._run_check(
            fetch_result=FetchResult(
                status_code=200, response_time_ms=60,
                content=b"fresh baseline", content_type="text/html",
            )
        )
        self.assertTrue(
            NotificationEvent.objects.filter(
                monitor=self.monitor, event_type=NotificationEvent.RECOVERY
            ).exists()
        )
        self.assertTrue(post.called)


# ---------------------------------------------------------------------------
# Advanced engines (DOM / screenshot / price)
# ---------------------------------------------------------------------------

class AdvancedEngineNotificationTests(DnsShimMixin, TestCase):
    def setUp(self):
        super().setUp()
        from monitors.advanced_tasks import run_advanced_monitor  # noqa

        self.run_advanced = run_advanced_monitor
        self.user = make_user("adv@example.com")
        self.monitor = make_monitor(self.user)
        self.channel = make_channel(self.user)
        MonitorAlertChannel.objects.create(
            monitor=self.monitor, channel=self.channel
        )

    def _browser(self, html):
        return BrowserResult(
            status_code=200, response_time_ms=80, html=html,
            screenshot=b"\x89PNG-fake",
        )

    def _run(self, browser_result=None, browser_error=None, **patches):
        target = "monitors.advanced_tasks.fetch_with_browser"
        if browser_error is not None:
            fetch_cm = mock.patch(target, side_effect=browser_error)
        else:
            fetch_cm = mock.patch(target, return_value=browser_result)
        artifact_cm = mock.patch(
            "monitors.advanced_tasks.save_artifact", return_value="artifact-key"
        )
        with fetch_cm, artifact_cm, mock.patch(
            "httpx.post", return_value=FakeResponse(200)
        ) as post:
            result = self.run_advanced(str(self.monitor.id))
        return result, post

    def _config(self, mode, **kwargs):
        return AdvancedMonitorConfig.objects.create(
            monitor=self.monitor, mode=mode, **kwargs
        )

    def test_dom_change_triggers_notification(self):
        self._config(AdvancedMonitorConfig.DOM, selector="body")
        make_check(self.monitor, hash="0" * 64)
        result, post = self._run(
            self._browser("<html><body>brand new text</body></html>")
        )
        self.assertEqual(result["status"], "success")
        self.assertTrue(
            NotificationEvent.objects.filter(
                monitor=self.monitor, event_type=NotificationEvent.CHANGE
            ).exists()
        )
        self.assertTrue(post.called)

    def test_screenshot_change_triggers_notification(self):
        self._config(
            AdvancedMonitorConfig.SCREENSHOT, selector="body",
            screenshot_threshold=Decimal("0.500"),
        )
        previous = make_check(self.monitor, hash="0" * 64)
        ChangeDiff.objects.create(
            monitor=self.monitor, previous_check=previous,
            current_check=previous, diff_type=ChangeDiff.SCREENSHOT,
            summary="baseline", artifact_path="prev-key",
        )
        with mock.patch(
            "monitors.services.artifacts.load_artifact", return_value=b"prev-bytes"
        ), mock.patch(
            "monitors.advanced_tasks.compare_screenshots",
            return_value={"changed": True, "percentage": 12.5},
        ):
            result, post = self._run(
                self._browser("<html><body>same-ish</body></html>")
            )
        self.assertEqual(result["status"], "success")
        self.assertTrue(
            NotificationEvent.objects.filter(
                monitor=self.monitor, event_type=NotificationEvent.CHANGE
            ).exists()
        )
        self.assertTrue(post.called)

    def test_price_change_triggers_notification(self):
        self._config(
            AdvancedMonitorConfig.PRICE, price_selector=".price",
            price_currency="USD",
        )
        previous = make_check(self.monitor, hash="0" * 64)
        PricePoint.objects.create(
            monitor=self.monitor, monitor_check=previous,
            price=Decimal("10.00"), currency="USD", raw_value="$10.00",
        )
        result, post = self._run(
            self._browser('<html><body><div class="price">$19.99</div></body></html>')
        )
        self.assertEqual(result["status"], "success")
        self.assertTrue(
            ChangeDiff.objects.filter(
                monitor=self.monitor, diff_type=ChangeDiff.PRICE
            ).exists()
        )
        self.assertTrue(
            NotificationEvent.objects.filter(
                monitor=self.monitor, event_type=NotificationEvent.CHANGE
            ).exists()
        )
        self.assertTrue(post.called)

    def test_advanced_failure_triggers_notification(self):
        self._config(AdvancedMonitorConfig.DOM, selector="body")
        result, post = self._run(
            browser_error=BrowserFetchError("Target returned 404.", retryable=False)
        )
        self.assertEqual(result["status"], "failed")
        self.assertTrue(
            NotificationEvent.objects.filter(
                monitor=self.monitor, event_type=NotificationEvent.FAILURE
            ).exists()
        )
        self.assertTrue(post.called)

    def test_advanced_recovery_triggers_notification(self):
        self._config(AdvancedMonitorConfig.DOM, selector="body")
        make_check(self.monitor, error="earlier outage")
        result, post = self._run(
            self._browser("<html><body>back online</body></html>")
        )
        self.assertEqual(result["status"], "success")
        self.assertTrue(
            NotificationEvent.objects.filter(
                monitor=self.monitor, event_type=NotificationEvent.RECOVERY
            ).exists()
        )
        self.assertTrue(post.called)


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

class ProviderDeliveryTests(DnsShimMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user("prov@example.com")
        self.monitor = make_monitor(self.user)

    def _deliver(self, ctype, url, **kwargs):
        channel = make_channel(self.user, ctype=ctype, url=url)
        return channel, notify_services.deliver_to_channel(
            channel, "Subject", "Message", monitor=self.monitor,
            event_type="change", **kwargs,
        )

    def test_slack_success(self):
        with mock.patch("httpx.post", return_value=FakeResponse(200)) as post:
            _, result = self._deliver("slack", "https://example.com/slack")
        self.assertTrue(result["ok"])
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(post.call_args.kwargs["json"], {"text": mock.ANY})
        self.assertIn("Subject", post.call_args.kwargs["json"]["text"])

    def test_slack_transient_retry_then_success(self):
        responses = [FakeResponse(503), FakeResponse(200)]
        with mock.patch("httpx.post", side_effect=responses) as post:
            _, result = self._deliver("slack", "https://example.com/slack")
        self.assertTrue(result["ok"])
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(post.call_count, 2)

    def test_slack_permanent_failure_does_not_retry(self):
        with mock.patch("httpx.post", return_value=FakeResponse(401)) as post:
            _, result = self._deliver("slack", "https://example.com/slack")
        self.assertFalse(result["ok"])
        self.assertTrue(result["permanent"])
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(post.call_count, 1)

    def test_discord_success(self):
        with mock.patch("httpx.post", return_value=FakeResponse(204)) as post:
            _, result = self._deliver("discord", "https://example.com/discord")
        self.assertTrue(result["ok"])
        self.assertIn("content", post.call_args.kwargs["json"])

    def test_discord_transient_retry(self):
        import httpx as httpx_module

        def boom(*args, **kwargs):
            raise httpx_module.ConnectError("down")

        with mock.patch("httpx.post", side_effect=[boom, FakeResponse(200)]) as post:
            _, result = self._deliver("discord", "https://example.com/discord")
        self.assertTrue(result["ok"])
        self.assertEqual(post.call_count, 2)

    def test_webhook_success(self):
        with mock.patch("httpx.post", return_value=FakeResponse(200)) as post:
            _, result = self._deliver("webhook", "https://example.com/wh")
        self.assertTrue(result["ok"])
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["subject"], "Subject")
        self.assertEqual(body["event_type"], "change")

    def test_webhook_persistent_failure_is_bounded(self):
        with mock.patch("httpx.post", return_value=FakeResponse(500)) as post:
            _, result = self._deliver("webhook", "https://example.com/wh")
        self.assertFalse(result["ok"])
        self.assertEqual(result["attempts"], notify_services.MAX_DELIVERY_ATTEMPTS)
        self.assertEqual(post.call_count, notify_services.MAX_DELIVERY_ATTEMPTS)

    def test_invalid_url_is_permanent_without_http(self):
        with mock.patch("httpx.post") as post:
            _, result = self._deliver("slack", "not-a-url")
        self.assertFalse(result["ok"])
        self.assertTrue(result["permanent"])
        post.assert_not_called()

    def test_ssrf_blocked_target_is_permanent_without_http(self):
        with mock.patch("httpx.post") as post:
            _, result = self._deliver("webhook", "http://127.0.0.1:8000/hook")
        self.assertFalse(result["ok"])
        self.assertTrue(result["permanent"])
        post.assert_not_called()

    def test_localhost_blocked(self):
        with mock.patch("httpx.post") as post:
            _, result = self._deliver("webhook", "http://localhost/hook")
        self.assertFalse(result["ok"])
        self.assertTrue(result["permanent"])
        post.assert_not_called()

    def test_sms_is_rejected_without_delivery(self):
        channel = AlertChannel.objects.create(
            user=self.user, channel_type="sms", name="legacy",
            config_encrypted="+15550001111",
        )
        with mock.patch("httpx.post") as post:
            result = notify_services.deliver_to_channel(
                channel, "S", "M", monitor=self.monitor, event_type="change"
            )
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "skipped")
        post.assert_not_called()

    def test_email_success(self):
        check = make_check(self.monitor)
        event = NotificationEvent.objects.create(
            monitor=self.monitor, monitor_check=check,
            event_type=NotificationEvent.CHANGE,
        )
        notify_services.send_monitor_email(event.id)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Change detected", mail.outbox[0].subject)

    def test_email_failure_is_observable(self):
        check = make_check(self.monitor)
        result = notify_services.send_owner_email(
            self.monitor, "Subject", "Body-nonexistent"
        )
        # locmem backend delivers; force a failure path instead:
        with mock.patch(
            "notifications.services.send_mail",
            side_effect=smtplib.SMTPException("provider down"),
        ):
            failed = notify_services.send_owner_email(
                self.monitor, "Subject", "Body"
            )
        self.assertTrue(result["ok"])
        self.assertFalse(failed["ok"])
        self.assertIn("provider down", failed["error"])


# ---------------------------------------------------------------------------
# Test endpoint
# ---------------------------------------------------------------------------

class ChannelTestEndpointTests(DnsShimMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user("endpoint@example.com")
        self.other = make_user("endpoint-other@example.com")
        self.client.force_authenticate(self.user)
        self.secret = "https://example.com/hooks/secret-token-abc123"
        self.channel = make_channel(self.user, url=self.secret)

    def _url(self, channel_id):
        return f"/api/notifications/channels/{channel_id}/test/"

    def test_authorized_channel_test_success(self):
        with mock.patch("httpx.post", return_value=FakeResponse(200)):
            response = self.client.post(self._url(self.channel.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["ok"])
        self.assertNotIn("secret-token-abc123", str(response.data))
        self.channel.refresh_from_db()
        self.assertTrue(self.channel.verified)

    def test_unauthorized_channel_test(self):
        self.client.force_authenticate(user=None)
        # APITestCase: clear auth explicitly
        self.client._force_auth_user = None
        from rest_framework.test import force_authenticate  # noqa
        response = self.client.post(self._url(self.channel.id))
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_cross_tenant_rejected(self):
        foreign = make_channel(self.other, url="https://example.com/other")
        response = self.client.post(self._url(foreign.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_provider_failure_returns_failure(self):
        with mock.patch("httpx.post", return_value=FakeResponse(500)):
            response = self.client.post(self._url(self.channel.id))
        self.assertEqual(
            response.status_code, status.HTTP_502_BAD_GATEWAY
        )
        self.assertFalse(response.data["ok"])
        self.assertNotIn("secret-token-abc123", str(response.data))

    def test_secrets_never_returned(self):
        with mock.patch("httpx.post", return_value=FakeResponse(200)):
            response = self.client.post(self._url(self.channel.id))
        body = str(response.data)
        self.assertNotIn(self.secret, body)
        self.assertNotIn("secret-token-abc123", body)

    def test_unsupported_channel_test_rejected(self):
        sms = AlertChannel.objects.create(
            user=self.user, channel_type="sms", name="legacy",
            config_encrypted="+15550001111",
        )
        response = self.client.post(self._url(sms.id))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["ok"])

    def test_monitor_channel_attach_and_list(self):
        # Attach
        response = self.client.post(
            f"/api/monitors/{make_monitor(self.user).id}/channels/",
            {"channel_id": str(self.channel.id)},
            format="json",
        )
        self.assertIn(
            response.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED)
        )


class MonitorChannelAttachTests(DnsShimMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user("attach@example.com")
        self.other = make_user("attach-other@example.com")
        self.client.force_authenticate(self.user)
        self.monitor = make_monitor(self.user)
        self.channel = make_channel(self.user)

    def _url(self):
        return f"/api/monitors/{self.monitor.id}/channels/"

    def test_attach_and_list_and_detach(self):
        attach = self.client.post(
            self._url(), {"channel_id": str(self.channel.id)}, format="json"
        )
        self.assertIn(attach.status_code, (200, 201))
        listing = self.client.get(self._url())
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.data), 1)
        self.assertNotIn("example.com/hook", str(listing.data))
        detach = self.client.delete(f"{self._url()}{self.channel.id}/")
        self.assertEqual(detach.status_code, 204)
        self.assertEqual(self.client.get(self._url()).data, [])

    def test_cross_tenant_attach_rejected(self):
        foreign = make_channel(self.other, url="https://example.com/foreign")
        response = self.client.post(
            self._url(), {"channel_id": str(foreign.id)}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(
            MonitorAlertChannel.objects.filter(
                monitor=self.monitor, channel=foreign
            ).exists()
        )


# ---------------------------------------------------------------------------
# Reliability
# ---------------------------------------------------------------------------

class ReliabilityTests(DnsShimMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user("rel@example.com")
        self.monitor = make_monitor(self.user)
        self.good = make_channel(self.user, name="good", url="https://example.com/good")
        self.bad = make_channel(self.user, name="bad", url="https://example.com/bad")
        MonitorAlertChannel.objects.create(monitor=self.monitor, channel=self.good)
        MonitorAlertChannel.objects.create(monitor=self.monitor, channel=self.bad)

    def test_one_failed_channel_does_not_block_others(self):
        def route(url, **kwargs):
            if url == "https://example.com/bad":
                return FakeResponse(401)
            return FakeResponse(200)

        check = make_check(self.monitor)
        with mock.patch("httpx.post", side_effect=route) as post:
            summary = notify_services.dispatch_monitor_event(
                self.monitor, check, NotificationEvent.CHANGE
            )
        self.assertEqual(post.call_count, 2)
        oks = {r["channel_id"]: r["ok"] for r in summary["channels"]}
        self.assertTrue(oks[str(self.good.id)])
        self.assertFalse(oks[str(self.bad.id)])
        self.assertEqual(
            NotificationDelivery.objects.filter(
                monitor=self.monitor, status=NotificationDelivery.DELIVERED,
                channel__isnull=False,
            ).count(),
            1,
        )
        self.assertEqual(
            NotificationDelivery.objects.filter(
                monitor=self.monitor, status=NotificationDelivery.FAILED,
                channel__isnull=False,
            ).count(),
            1,
        )

    def test_notification_failure_does_not_fail_monitor_execution(self):
        from monitors.services.normalizer import content_hash

        old_hash = content_hash(b"baseline", "text/html")
        self.monitor.last_content_hash = old_hash
        self.monitor.save(update_fields=["last_content_hash"])
        from monitors.tasks import check_monitor

        fetch = FetchResult(
            status_code=200, response_time_ms=40, content=b"changed!",
            content_type="text/html",
        )
        with mock.patch("monitors.tasks.fetch_url", return_value=fetch), mock.patch(
            # Phase E (D7): the check task now hands off via
            # deliver_monitor_event.delay — same guarantee under test:
            # an exploding notifier must not fail the monitor task.
            "monitors.tasks.deliver_monitor_event.delay",
            side_effect=RuntimeError("notify exploded"),
        ):
            result = check_monitor(str(self.monitor.id))
        self.assertEqual(result["status"], "changed")
        self.assertTrue(
            MonitorCheck.objects.filter(monitor=self.monitor).exists()
        )

    def test_bounded_retry_with_exponential_backoff(self):
        channel = make_channel(self.user, url="https://example.com/flaky")
        with mock.patch.object(
            notify_services, "RETRY_BACKOFF_BASE_SECONDS", 0.5
        ), mock.patch("httpx.post", return_value=FakeResponse(503)), mock.patch(
            "notifications.services.time.sleep"
        ) as sleep:
            result = notify_services.deliver_to_channel(
                channel, "S", "M", monitor=self.monitor, event_type="change"
            )
        self.assertFalse(result["ok"])
        self.assertEqual(result["attempts"], 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(
            [c.args[0] for c in sleep.call_args_list], [0.5, 1.0]
        )

    def test_no_secret_leakage_in_logs(self):
        secret_url = "https://example.com/hooks/super-secret-value-xyz"
        channel = make_channel(self.user, url=secret_url)
        check = make_check(self.monitor)
        MonitorAlertChannel.objects.create(monitor=self.monitor, channel=channel)
        with self.assertLogs("notifications.services", level="INFO") as logs, mock.patch(
            "httpx.post", return_value=FakeResponse(200)
        ):
            notify_services.dispatch_monitor_event(
                self.monitor, check, NotificationEvent.CHANGE
            )
        combined = "\n".join(logs.output)
        self.assertNotIn("super-secret-value-xyz", combined)
        self.assertNotIn(secret_url, combined)

    def test_delivery_result_exposed_not_faked(self):
        # A provider rejection must surface as failure, never success.
        with mock.patch("httpx.post", return_value=FakeResponse(403)):
            result = notify_services.deliver_to_channel(
                self.bad, "S", "M", monitor=self.monitor, event_type="change"
            )
        self.assertFalse(result["ok"])
        self.assertTrue(result["permanent"])
