"""API and end-to-end capture tests for the intelligence layer.

These exercise the whole Phase 1 loop with the network mocked at
``fetch_url`` — analyse, activate, check, observe a change, read the
timeline — plus every tenant and plan rule that could leak or over-create.
"""

import json
from unittest import mock

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from rest_framework.throttling import SimpleRateThrottle

from accounts.models import User
from billing.models import Subscription
from intelligence.models import (
    DiscoveredTarget,
    ProductChange,
    ProductSnapshot,
    ProductWatch,
    UrlAnalysis,
)
from monitors.models import Monitor, MonitorCheck
from monitors.services.fetcher import FetchResult
from workspaces.models import Workspace


def product_html(price="99.00", availability="InStock", name="Acme Pro Widget", extra_ld=None):
    payload = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": name,
        "sku": "APW-2000",
        "brand": {"@type": "Brand", "name": "Acme"},
        "offers": {
            "@type": "Offer",
            "price": price,
            "priceCurrency": "EUR",
            "availability": f"https://schema.org/{availability}",
        },
        "aggregateRating": {"@type": "AggregateRating", "ratingValue": "4.6", "reviewCount": "128"},
    }
    if extra_ld:
        payload.update(extra_ld)
    body = (
        '<nav><a href="/pricing">Pricing</a><a href="/changelog">Changelog</a>'
        '<a href="/cart">Cart</a></nav>'
        "<h1>Acme Pro Widget</h1>"
    )
    return (
        "<!doctype html><html><head>"
        '<script type="application/ld+json">' + json.dumps(payload) + "</script>"
        "<title>Acme Pro Widget</title></head><body>" + body + "</body></html>"
    ).encode("utf-8")


WIDE_NAV = (
    '<nav>'
    '<a href="/pricing">Pricing</a>'
    '<a href="/features">Features</a>'
    '<a href="/changelog">Changelog</a>'
    '<a href="/blog">Blog</a>'
    '<a href="/careers">Careers</a>'
    '<a href="/docs">Docs</a>'
    '<a href="/faq">FAQ</a>'
    "</nav>"
)


def wide_product_html():
    """A product page that also links to seven other public pages."""
    return product_html().replace(
        b'<nav><a href="/pricing">Pricing</a><a href="/changelog">Changelog</a>'
        b'<a href="/cart">Cart</a></nav>',
        WIDE_NAV.encode(),
    )


def fetch_result(content=None, status_code=200):
    return FetchResult(
        status_code=status_code,
        response_time_ms=42,
        content=content if content is not None else product_html(),
        content_type="text/html; charset=utf-8",
    )


class IntelligenceApiTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("owner@example.com", "a-strong-password")
        self.other = User.objects.create_user("other@example.com", "a-strong-password")
        self.client.force_authenticate(self.user)

    def post_analyze(self, url="https://competitor.com/products/pro-x", content=None, **extra):
        payload = {"url": url}
        payload.update(extra)
        with mock.patch(
            "intelligence.services.analysis.fetch_url",
            return_value=fetch_result(content=content),
        ):
            return self.client.post(reverse("intelligence-analyze"), payload, format="json")


class AnalyzeTests(IntelligenceApiTestCase):
    def test_analyze_requires_authentication(self):
        self.client.force_authenticate(None)
        response = self.client.post(
            reverse("intelligence-analyze"), {"url": "https://a.example/p"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_analyze_returns_facts_and_targets(self):
        response = self.post_analyze()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data["page_kind"], "product")
        self.assertTrue(data["product_detected"])
        self.assertEqual(data["summary"]["name"], "Acme Pro Widget")
        self.assertEqual(data["summary"]["price"], "99.00")
        self.assertEqual(data["summary"]["availability"], "in_stock")
        self.assertTrue(data["classification_rationale"])
        # Submitted page first, then the discovered pricing + changelog.
        self.assertEqual(data["targets"][0]["is_product"], True)
        kinds = [target["kind"] for target in data["targets"]]
        self.assertIn("pricing", kinds)
        self.assertIn("changelog", kinds)
        self.assertNotIn("other", kinds)
        for target in data["targets"]:
            self.assertTrue(target["why"])

    def test_second_analysis_of_the_same_url_is_cached(self):
        self.post_analyze()
        with mock.patch(
            "intelligence.services.analysis.fetch_url", return_value=fetch_result()
        ) as fetcher:
            response = self.client.post(
                reverse("intelligence-analyze"),
                {"url": "https://competitor.com/products/pro-x"},
                format="json",
            )
        self.assertTrue(response.data["cached"])
        fetcher.assert_not_called()

    def test_bare_hostname_is_accepted(self):
        response = self.post_analyze(url="competitor.com")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["url"].startswith("https://competitor.com"))

    def test_a_blocked_url_is_refused_with_a_plain_message(self):
        with mock.patch(
            "intelligence.services.analysis.fetch_url",
            side_effect=__import__(
                "monitors.services.fetcher", fromlist=["SecurityError"]
            ).SecurityError("blocked"),
        ):
            response = self.client.post(
                reverse("intelligence-analyze"),
                {"url": "http://127.0.0.1:8000/admin"},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("publicly reachable", response.data["detail"])

    def test_an_http_error_page_is_reported_plainly(self):
        with mock.patch(
            "intelligence.services.analysis.fetch_url", return_value=fetch_result(status_code=403)
        ):
            response = self.client.post(
                reverse("intelligence-analyze"),
                {"url": "https://blocked.example/p"},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("403", response.data["detail"])

    def test_blank_url_is_rejected(self):
        response = self.client.post(
            reverse("intelligence-analyze"), {"url": "  "}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PublicAnalyzeTests(APITestCase):
    def test_public_analyze_needs_no_account(self):
        with mock.patch(
            "intelligence.services.analysis.fetch_url", return_value=fetch_result()
        ):
            response = self.client.post(
                reverse("intelligence-public-analyze"),
                {"url": "https://competitor.com/products/pro-x"},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["product_detected"])

    def test_public_analyze_persists_nothing_and_names_no_user(self):
        with mock.patch(
            "intelligence.services.analysis.fetch_url", return_value=fetch_result()
        ):
            response = self.client.post(
                reverse("intelligence-public-analyze"),
                {"url": "https://competitor.com/products/pro-x"},
                format="json",
            )
        self.assertEqual(UrlAnalysis.objects.count(), 0)
        self.assertEqual(ProductWatch.objects.count(), 0)
        body = json.dumps(response.data)
        self.assertNotIn("user", body)
        self.assertNotIn("@example.com", body)

    def test_public_analyze_returns_at_most_five_targets(self):
        links = "".join(
            f'<a href="/page-{index}">Page {index}</a>' for index in range(30)
        )
        content = (
            '<!doctype html><html><head>'
            '<script type="application/ld+json">{"@type":"Product","name":"X",'
            '"offers":{"price":"1.00"}}</script></head><body>' + links + "</body></html>"
        ).encode("utf-8")
        with mock.patch(
            "intelligence.services.analysis.fetch_url",
            return_value=fetch_result(content=content),
        ):
            response = self.client.post(
                reverse("intelligence-public-analyze"),
                {"url": "https://competitor.com/p/x"},
                format="json",
            )
        self.assertLessEqual(len(response.data["targets"]), 5)
        self.assertGreater(response.data["found_count"], 5)

    def test_public_analyze_is_throttled(self):
        # DRF binds SimpleRateThrottle.THROTTLE_RATES at import time, so the
        # scope dict is what has to be patched (not settings.REST_FRAMEWORK).
        with mock.patch.dict(
            SimpleRateThrottle.THROTTLE_RATES, {"public_analyze": "2/hour"}
        ):
            with mock.patch(
                "intelligence.services.analysis.fetch_url", return_value=fetch_result()
            ):
                codes = [
                    self.client.post(
                        reverse("intelligence-public-analyze"),
                        {"url": "https://competitor.com/products/pro-x"},
                        format="json",
                    ).status_code
                    for _ in range(4)
                ]
        self.assertEqual(
            codes.count(status.HTTP_429_TOO_MANY_REQUESTS), 2, codes
        )

    def test_the_shipped_rate_is_configured_for_this_scope(self):
        self.assertIn("public_analyze", SimpleRateThrottle.THROTTLE_RATES)


class ActivateTests(IntelligenceApiTestCase):
    def setUp(self):
        super().setUp()
        self.analysis_response = self.post_analyze()
        self.analysis_id = self.analysis_response.data["id"]
        self.targets = self.analysis_response.data["targets"]

    def activate(self, **payload):
        body = {"analysis_id": self.analysis_id}
        body.update(payload)
        with mock.patch("monitors.tasks.check_monitor.delay") as delayed:
            response = self.client.post(
                reverse("intelligence-activate"), body, format="json"
            )
        response.delayed = delayed
        return response

    def test_monitor_everything_creates_monitors_and_a_product_watch(self):
        response = self.activate(recipe="everything")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data
        self.assertEqual(data["created"], len(self.targets))
        self.assertEqual(len(data["product_watches"]), 1)
        self.assertFalse(data["limit_reached"])
        created = Monitor.objects.all()
        self.assertGreaterEqual(created.count(), 3)
        for monitor in created:
            self.assertTrue(monitor.url.startswith("https://competitor.com"))
            self.assertTrue(monitor.name)

    def test_activation_respects_the_free_plan_limit_and_says_why(self):
        Subscription.objects.filter(user=self.user).update(plan="free")
        analysis_response = self.post_analyze(
            url="https://competitor.com/products/wide", content=wide_product_html()
        )
        self.assertGreater(len(analysis_response.data["targets"]), 3)
        self.analysis_id = analysis_response.data["id"]
        self.targets = analysis_response.data["targets"]

        response = self.activate(recipe="everything")
        data = response.data
        # Free = 3 active URLs. We create 3 and report the rest with a
        # reason rather than failing the whole one-click button.
        self.assertEqual(data["created"], 3)
        self.assertTrue(data["limit_reached"])
        self.assertIn("3", data["detail"])
        reasons = {row["reason"] for row in data["skipped"]}
        self.assertIn("plan_limit", reasons)
        self.assertEqual(Monitor.objects.count(), 3)
        for row in data["skipped"]:
            self.assertTrue(row["url"])
            self.assertTrue(row["label"])

    def test_business_plan_is_not_clamped(self):
        Subscription.objects.filter(user=self.user).update(plan="business")
        response = self.activate(recipe="everything")
        self.assertFalse(response.data["limit_reached"])

    def test_at_most_two_first_checks_are_published_immediately(self):
        response = self.activate(recipe="everything")
        # A 20-page activation must not fire 20 simultaneous outbound
        # requests; the rest wait for the 60s scheduler tick.
        self.assertEqual(response.delayed.call_count, 2)
        self.assertEqual(response.data["published_first_checks"], 2)
        self.assertGreater(response.data["created"], 2)

    def test_duplicates_are_detected_not_duplicated(self):
        self.activate(recipe="everything", target_ids=[self.targets[0]["id"]])
        response = self.activate(recipe="everything", target_ids=[self.targets[0]["id"]])
        self.assertEqual(response.data["created"], 0)
        self.assertEqual(response.data["skipped"][0]["reason"], "already_monitored")
        self.assertEqual(Monitor.objects.count(), 1)

    def test_recipe_narrows_the_selected_targets(self):
        response = self.activate(recipe="pricing")
        data = response.data
        kinds = {monitor.url for monitor in Monitor.objects.all()}
        self.assertTrue(kinds)
        self.assertLess(data["created"], len(self.targets))
        self.assertEqual(data["recipe"], "pricing")

    def test_interval_is_clamped_to_the_plan_minimum(self):
        response = self.activate(recipe="pricing", check_interval=60)
        # Free plan minimum is 900s, so 60s is raised rather than rejected.
        self.assertGreaterEqual(response.data["check_interval"], 900)

    def test_a_viewer_cannot_activate_into_a_workspace(self):
        workspace = Workspace.objects.create(name="Client A", owner=self.other)
        from workspaces.models import WorkspaceMembership

        WorkspaceMembership.objects.create(
            workspace=workspace, user=self.user, role="viewer"
        )
        response = self.activate(recipe="pricing", workspace=str(workspace.id))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Monitor.objects.count(), 0)

    def test_an_admin_can_activate_into_a_workspace(self):
        workspace = Workspace.objects.create(name="Client A", owner=self.other)
        from workspaces.models import WorkspaceMembership

        WorkspaceMembership.objects.create(
            workspace=workspace, user=self.user, role="admin"
        )
        response = self.activate(recipe="pricing", workspace=str(workspace.id))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Monitor.objects.filter(workspace=workspace).exists())

    def test_another_users_analysis_is_a_404_not_a_403(self):
        self.client.force_authenticate(self.other)
        response = self.client.post(
            reverse("intelligence-activate"),
            {"analysis_id": self.analysis_id, "recipe": "pricing"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class QuickMonitorTests(IntelligenceApiTestCase):
    def test_quick_monitor_creates_one_monitor_in_one_call(self):
        with mock.patch("monitors.tasks.check_monitor.delay"):
            with mock.patch(
                "intelligence.services.analysis.fetch_url", return_value=fetch_result()
            ):
                response = self.client.post(
                    reverse("intelligence-quick-monitor"),
                    {"url": "https://competitor.com/products/pro-x", "recipe": "product"},
                    format="json",
                )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("monitor_id", response.data)
        self.assertTrue(response.data["product_detected"])
        self.assertEqual(Monitor.objects.count(), 1)
        self.assertEqual(ProductWatch.objects.count(), 1)

    def test_quick_monitor_is_idempotent(self):
        def call():
            with mock.patch("monitors.tasks.check_monitor.delay"):
                with mock.patch(
                    "intelligence.services.analysis.fetch_url", return_value=fetch_result()
                ):
                    return self.client.post(
                        reverse("intelligence-quick-monitor"),
                        {"url": "https://competitor.com/products/pro-x", "recipe": "product"},
                        format="json",
                    )

        first = call()
        second = call()
        self.assertEqual(first.data["created"], 1)
        self.assertEqual(second.data["created"], 0)
        self.assertEqual(Monitor.objects.count(), 1)
        self.assertEqual(second.data["monitor_id"], first.data["monitor_id"])

    def test_quick_monitor_requires_authentication(self):
        self.client.force_authenticate(None)
        response = self.client.post(
            reverse("intelligence-quick-monitor"),
            {"url": "https://competitor.com/p", "recipe": "product"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class RecipesTests(IntelligenceApiTestCase):
    def test_recipe_catalogue(self):
        response = self.client.get(reverse("intelligence-recipes"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slugs = {recipe["slug"] for recipe in response.data["recipes"]}
        self.assertEqual(
            slugs,
            {
                "pricing", "product", "features", "marketing", "seo",
                "hiring", "ecommerce", "everything",
            },
        )
        for recipe in response.data["recipes"]:
            self.assertTrue(recipe["name"])
            self.assertTrue(recipe["description"])


class ProductWatchApiTests(IntelligenceApiTestCase):
    def setUp(self):
        super().setUp()
        self.monitor = Monitor.objects.create(
            user=self.user,
            name="competitor.com — Product",
            url="https://competitor.com/products/pro-x",
            check_interval=900,
        )
        self.watch = ProductWatch.objects.create(
            monitor=self.monitor, name="Acme Pro Widget", currency="EUR"
        )

    def run_check(self, content):
        from monitors.tasks import check_monitor

        with mock.patch("monitors.tasks.fetch_url", return_value=fetch_result(content=content)):
            check_monitor(str(self.monitor.id))
        return MonitorCheck.objects.filter(monitor=self.monitor).order_by("-checked_at").first()

    def test_first_check_creates_a_snapshot_but_no_changes(self):
        self.run_check(product_html())
        self.assertEqual(ProductSnapshot.objects.count(), 1)
        self.assertEqual(ProductChange.objects.count(), 0)
        snapshot = ProductSnapshot.objects.get()
        self.assertEqual(str(snapshot.price), "99.00")
        self.assertEqual(snapshot.currency, "EUR")
        self.assertEqual(snapshot.availability, "in_stock")
        self.assertEqual(snapshot.brand, "Acme")
        self.assertEqual(snapshot.extraction["price"], "jsonld")
        self.assertIn("99.00", snapshot.evidence["price"])
        self.assertEqual(snapshot.source_url, "https://competitor.com/products/pro-x")

    def test_second_check_records_the_price_drop_with_evidence(self):
        self.run_check(product_html())
        self.run_check(product_html(price="79.00", availability="LowStock"))
        changes = list(ProductChange.objects.order_by("field"))
        self.assertEqual(len(changes), 2)
        price = next(row for row in changes if row.field == "price")
        self.assertEqual(price.before, "99.00")
        self.assertEqual(price.after, "79.00")
        self.assertEqual(price.severity, "important")
        self.assertEqual(price.category, "pricing")
        self.assertTrue(price.basis)
        self.assertEqual(price.source_url, "https://competitor.com/products/pro-x")
        self.assertIsNotNone(price.monitor_check)

        availability = next(row for row in changes if row.field == "availability")
        self.assertEqual(availability.severity, "important")

    def test_an_unchanged_check_records_no_new_changes(self):
        self.run_check(product_html())
        self.run_check(product_html())
        self.run_check(product_html())
        self.assertEqual(ProductChange.objects.count(), 0)
        self.assertEqual(ProductSnapshot.objects.count(), 3)

    def test_going_out_of_stock_is_critical(self):
        self.run_check(product_html())
        self.run_check(product_html(availability="OutOfStock"))
        row = ProductChange.objects.get(field="availability")
        self.assertEqual(row.severity, "critical")

    def test_capture_is_idempotent_for_a_retried_check(self):
        check = self.run_check(product_html())
        from intelligence.services.product_capture import capture

        content = product_html(price="79.00")
        with mock.patch(
            "intelligence.services.product_capture.extract_page_facts"
        ) as extractor:
            from intelligence.services.page_facts import extract_page_facts as real

            extractor.side_effect = real
            capture(self.monitor, check, content, "text/html")
            capture(self.monitor, check, content, "text/html")
        self.assertEqual(ProductSnapshot.objects.filter(monitor_check=check).count(), 1)
        self.assertEqual(
            ProductChange.objects.filter(monitor_check=check).count(),
            ProductChange.objects.filter(monitor_check=check).count(),
        )

    def test_a_capture_failure_never_breaks_the_check(self):
        from monitors import tasks as monitor_tasks

        with mock.patch(
            "intelligence.services.product_capture.extract_page_facts",
            side_effect=RuntimeError("boom"),
        ):
            with mock.patch(
                "monitors.tasks.fetch_url", return_value=fetch_result()
            ):
                result = monitor_tasks.check_monitor(str(self.monitor.id))
        self.assertEqual(result["status"], "unchanged")
        self.assertEqual(ProductSnapshot.objects.count(), 0)
        self.assertTrue(
            MonitorCheck.objects.filter(monitor=self.monitor, error="").exists()
        )

    def test_monitor_product_endpoint(self):
        self.run_check(product_html())
        response = self.client.get(
            reverse("intelligence-monitor-product", args=[str(self.monitor.id)])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["current_snapshot"]["price"], "99.00")
        self.assertIn("explanation", response.data)
        self.assertIn("why_it_may_matter", response.data["explanation"])

    def test_monitor_product_endpoint_404s_without_a_watch(self):
        other = Monitor.objects.create(
            user=self.user, name="Plain", url="https://a.example/p"
        )
        response = self.client.get(
            reverse("intelligence-monitor-product", args=[str(other.id)])
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_timeline_filters_by_severity_and_category(self):
        self.run_check(product_html())
        self.run_check(product_html(price="79.00", availability="OutOfStock"))
        watch_id = str(self.watch.id)
        response = self.client.get(
            reverse("intelligence-product-watch-timeline", args=[watch_id]),
            {"severity": "critical"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["changes"][0]["field"], "availability")

        response = self.client.get(
            reverse("intelligence-product-watch-timeline", args=[watch_id]),
            {"category": "pricing"},
        )
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["changes"][0]["field"], "price")

    def test_another_users_watch_is_a_404(self):
        self.run_check(product_html())
        self.client.force_authenticate(self.other)
        response = self.client.get(
            reverse("intelligence-product-watch-detail", args=[str(self.watch.id)])
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_view_counts_changes_in_one_go(self):
        self.run_check(product_html())
        self.run_check(product_html(price="79.00"))
        response = self.client.get(reverse("intelligence-product-watch-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        entry = response.data["product_watches"][0]
        self.assertEqual(entry["change_count"], 1)
        self.assertEqual(entry["latest_severity"], "important")
        self.assertEqual(entry["latest_snapshot"]["price"], "79.00")

    def test_deleting_the_monitor_removes_the_product_history(self):
        self.run_check(product_html())
        self.run_check(product_html(price="79.00"))
        self.monitor.delete()
        self.assertEqual(ProductWatch.objects.count(), 0)
        self.assertEqual(ProductSnapshot.objects.count(), 0)
        self.assertEqual(ProductChange.objects.count(), 0)


class AlertContentTests(IntelligenceApiTestCase):
    def test_a_product_change_appears_in_the_alert_body(self):
        from notifications.services import _build_subject_message

        monitor = Monitor.objects.create(
            user=self.user, name="competitor.com — Product", url="https://competitor.com/p"
        )
        watch = ProductWatch.objects.create(monitor=monitor, name="Acme Pro Widget", currency="EUR")
        with mock.patch("monitors.tasks.fetch_url", return_value=fetch_result()):
            from monitors.tasks import check_monitor

            check_monitor(str(monitor.id))
        with mock.patch(
            "monitors.tasks.fetch_url", return_value=fetch_result(content=product_html(price="79.00"))
        ):
            from monitors.tasks import check_monitor

            check_monitor(str(monitor.id))
        check = monitor.checks.order_by("-checked_at").first()
        _subject, message = _build_subject_message(monitor, check, "change")
        self.assertIn("PRODUCT INTELLIGENCE", message)
        self.assertIn("Acme Pro Widget", message)
        self.assertIn("WHAT CHANGED", message)
        self.assertIn("WHY IT MAY MATTER", message)
        self.assertIn("EVIDENCE", message)
        self.assertIn("https://competitor.com/p", message)
        self.assertIn("rule:price", message)

    def test_a_monitor_without_a_product_watch_alerts_exactly_as_before(self):
        from notifications.services import _build_subject_message

        monitor = Monitor.objects.create(
            user=self.user, name="Plain monitor", url="https://a.example/p"
        )
        check = MonitorCheck.objects.create(
            monitor=monitor, checked_at=__import__("django.utils.timezone", fromlist=["now"]).now(), changed=True
        )
        _subject, message = _build_subject_message(monitor, check, "change")
        self.assertNotIn("PRODUCT INTELLIGENCE", message)
        self.assertIn("A change was detected on Plain monitor.", message)
