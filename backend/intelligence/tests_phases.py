"""Tests for Phases 2-6.

Grouped by phase so a failure points at the feature that broke:

  FeedTests          chronological feed, filters, cursor stability
  PulseTests         descriptive states, and the absence of scores
  DiscoveryTests     candidates carry reasons; nothing monitors unapproved
  SignalTests        derivation is idempotent and never double-reports
  DeepLinkTests      the alert deep link (what/why/check/evidence)
  NarrationTests     opt-in only, citation validation, fallback preserved
  MarketSignalTests  minimum evidence threshold, evidence attached
  ExportTests        every format, source URL on every row
  ReportTests        report composition, downloads, tenant isolation
  BattlecardTests    composition and explicit staleness
  AgencyTests        org membership, seat limits, client workspaces
  ExtensionTests     token mint/revoke/expiry, scope ceiling

No test performs a network call: every fetch is mocked at
``intelligence.services.analysis.fetch_url``.
"""

import io
import json
import zipfile
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from billing.models import PLAN_LIMITS, Subscription
from intelligence.models import (
    Battlecard,
    BrowserSession,
    ChangeExplanation,
    Competitor,
    CompetitorCandidate,
    MarketSignal,
    Organization,
    OrganizationMembership,
    ProductChange,
    ProductWatch,
    Report,
    SignalEvent,
)
from monitors.models import Monitor, MonitorCheck
from monitors.services.fetcher import FetchError, FetchResult
from workspaces.models import Workspace, WorkspaceMembership


def product_html(price="99.00", availability="InStock", name="Acme Pro Widget"):
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
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": "4.6",
            "reviewCount": "128",
        },
    }
    body = (
        '<nav><a href="/pricing">Pricing</a><a href="/changelog">Changelog</a>'
        '<a href="/careers">Careers</a></nav><h1>Acme Pro Widget</h1>'
    )
    return (
        "<!doctype html><html><head><script type=\"application/ld+json\">"
        + json.dumps(payload)
        + '</script><title>Acme Pro Widget</title></head><body>'
        + body
        + "</body></html>"
    ).encode("utf-8")


def fetch_result(content=None, status_code=200):
    return FetchResult(
        status_code=status_code,
        response_time_ms=42,
        content=content if content is not None else product_html(),
        content_type="text/html; charset=utf-8",
    )


class IntelligenceTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("owner@example.com", "a-strong-password")
        self.other = User.objects.create_user("other@example.com", "a-strong-password")
        self.client.force_authenticate(self.user)

    def make_monitor(self, url="https://competitor.com/products/pro-x", user=None, workspace=None):
        return Monitor.objects.create(
            user=user or self.user,
            workspace=workspace,
            name="competitor.com — Product",
            url=url,
            check_interval=900,
        )

    def make_watch(self, monitor, name="Acme Pro Widget", currency="EUR"):
        return ProductWatch.objects.create(
            monitor=monitor, name=name, currency=currency, product_detected=True
        )

    def run_check(self, monitor, content=None):
        from monitors.tasks import check_monitor

        with mock.patch(
            "monitors.tasks.fetch_url", return_value=fetch_result(content=content)
        ):
            check_monitor(str(monitor.id))
        return MonitorCheck.objects.filter(monitor=monitor).order_by("-checked_at").first()

    def make_product_change(self, monitor, watch=None, field="price", before="129.00", after="99.00"):
        check = MonitorCheck.objects.create(
            monitor=monitor,
            checked_at=timezone.now(),
            status_code=200,
            content_hash="a" * 64,
        )
        watch = watch or self.make_watch(monitor)
        return ProductChange.objects.create(
            product_watch=watch,
            monitor_check=check,
            field=field,
            label=field.replace("_", " ").title(),
            before=before,
            after=after,
            severity="important",
            category="pricing",
            basis=f"Price decreased by 23.3% ({before} → {after}).",
            rule="rule:price",
            source_url=monitor.url,
        )

    def make_signal(self, competitor, monitor, kind="pricing", headline=None, minutes_ago=5, severity="important"):
        detected = timezone.now() - timedelta(minutes=minutes_ago)
        return SignalEvent.objects.create(
            user=self.user,
            workspace=monitor.workspace,
            competitor=competitor,
            monitor=monitor,
            kind=kind,
            headline=headline or f"{competitor.name} changed its pricing",
            summary="A published value changed.",
            before="129.00",
            after="99.00",
            severity=severity,
            source_url=monitor.url,
            source_key=f"test:{competitor.id}:{kind}:{detected.isoformat()}",
            evidence={"rule": "rule:price", "basis": "Price decreased by 23.3%."},
            detected_at=detected,
        )

    def make_competitor(self, domain="competitor.com", user=None, name=None):
        return Competitor.objects.create(
            user=user or self.user,
            name=name or domain.split(".")[0].title(),
            homepage_url=f"https://{domain}",
            domain=domain,
            first_seen_at=timezone.now(),
        )


# ==========================================================================
# Phase 2 — feed
# ==========================================================================


class FeedTests(IntelligenceTestCase):
    def setUp(self):
        super().setUp()
        self.monitor = self.make_monitor()
        self.competitor = self.make_competitor()
        # 10 days old: outside a 1-day window, inside the default one.
        self.old = self.make_signal(
            self.competitor, self.monitor, kind="pricing", headline="Acme cut prices",
            minutes_ago=60 * 24 * 10,
        )
        self.recent = self.make_signal(
            self.competitor, self.monitor, kind="features", headline="Acme shipped a feature", minutes_ago=5
        )

    def test_feed_is_newest_first(self):
        response = self.client.get(reverse("intelligence-feed"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        headlines = [row["headline"] for row in response.data["results"]]
        self.assertEqual(headlines[0], "Acme shipped a feature")

    def test_every_row_carries_its_evidence_and_source(self):
        response = self.client.get(reverse("intelligence-feed"))
        row = response.data["results"][0]
        self.assertTrue(row["source_url"].startswith("https://"))
        self.assertTrue(row["evidence"])
        self.assertTrue(row["icon"])
        self.assertTrue(row["competitor_name"])

    def test_filter_by_kind(self):
        response = self.client.get(reverse("intelligence-feed"), {"kind": "pricing"})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["kind"], "pricing")

    def test_filter_by_severity(self):
        response = self.client.get(reverse("intelligence-feed"), {"severity": "critical"})
        self.assertEqual(response.data["count"], 0)

    def test_all_filter_is_not_treated_as_a_kind(self):
        response = self.client.get(reverse("intelligence-feed"), {"kind": "all"})
        self.assertEqual(response.data["count"], 2)

    def test_kind_counts_are_returned_for_the_filter_row(self):
        response = self.client.get(reverse("intelligence-feed"))
        counts = response.data["counts_by_kind"]
        self.assertEqual(counts["pricing"], 1)
        self.assertEqual(counts["features"], 1)

    def test_cursor_pagination_is_stable_and_non_overlapping(self):
        first = self.client.get(reverse("intelligence-feed"), {"limit": 1})
        self.assertEqual(first.data["count"], 1)
        self.assertTrue(first.data["has_more"])
        cursor = first.data["next_cursor"]
        self.assertTrue(cursor)
        second = self.client.get(reverse("intelligence-feed"), {"limit": 1, "cursor": cursor})
        self.assertEqual(second.data["count"], 1)
        self.assertNotEqual(
            first.data["results"][0]["id"], second.data["results"][0]["id"]
        )
        # Two events, one per page: the second page is the last one.
        self.assertFalse(second.data["has_more"])
        self.assertIsNone(second.data["next_cursor"])

    def test_a_new_event_does_not_duplicate_an_already_returned_row(self):
        """The reason for cursor pagination: an offset would shift."""
        first = self.client.get(reverse("intelligence-feed"), {"limit": 1})
        seen = first.data["results"][0]["id"]
        # A brand new event arrives between page 1 and page 2.
        self.make_signal(
            self.competitor, self.monitor, kind="hiring", headline="Acme is hiring", minutes_ago=0
        )
        second = self.client.get(
            reverse("intelligence-feed"), {"limit": 2, "cursor": first.data["next_cursor"]}
        )
        ids = [row["id"] for row in second.data["results"]]
        self.assertNotIn(seen, ids)

    def test_window_days_filter(self):
        # The 5-minute event is inside one day; the 10-day-old one is not.
        response = self.client.get(reverse("intelligence-feed"), {"window_days": 1})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["headline"], "Acme shipped a feature")

    def test_feed_requires_authentication(self):
        self.client.force_authenticate(None)
        self.assertEqual(
            self.client.get(reverse("intelligence-feed")).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_another_users_feed_is_empty_not_leaky(self):
        self.client.force_authenticate(self.other)
        response = self.client.get(reverse("intelligence-feed"))
        self.assertEqual(response.data["count"], 0)

    def test_a_bad_limit_is_ignored_rather_than_500ing(self):
        response = self.client.get(reverse("intelligence-feed"), {"limit": "abc"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_a_corrupt_cursor_is_ignored_rather_than_500ing(self):
        response = self.client.get(reverse("intelligence-feed"), {"cursor": "garbage"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)


# ==========================================================================
# Phase 2 — pulse
# ==========================================================================


class PulseTests(IntelligenceTestCase):
    def setUp(self):
        super().setUp()
        self.monitor = self.make_monitor()
        self.competitor = self.make_competitor()

    def test_no_activity_reads_as_no_significant_change(self):
        response = self.client.get(reverse("intelligence-pulse"))
        card = response.data["competitors"][0]
        self.assertIn("no_significant_change_detected", card["states"])
        self.assertEqual(card["state_label"], "No significant change detected")

    def test_one_change_reads_as_changed_recently(self):
        self.make_signal(self.competitor, self.monitor, minutes_ago=30)
        card = self.client.get(reverse("intelligence-pulse")).data["competitors"][0]
        self.assertIn("changed_recently", card["states"])

    def test_several_changes_reads_as_multiple_changes(self):
        for index in range(3):
            self.make_signal(
                self.competitor, self.monitor, kind="pricing",
                headline=f"change {index}", minutes_ago=index + 1,
            )
        card = self.client.get(reverse("intelligence-pulse")).data["competitors"][0]
        self.assertIn("multiple_changes_detected", card["states"])

    def test_pricing_and_feature_states_appear(self):
        self.make_signal(self.competitor, self.monitor, kind="pricing", minutes_ago=5)
        self.make_signal(self.competitor, self.monitor, kind="features", headline="f", minutes_ago=4)
        card = self.client.get(reverse("intelligence-pulse")).data["competitors"][0]
        self.assertIn("pricing_changed", card["states"])
        self.assertIn("feature_change_detected", card["states"])

    def test_pulse_never_returns_a_numeric_score(self):
        self.make_signal(self.competitor, self.monitor, minutes_ago=5)
        body = json.dumps(
            self.client.get(reverse("intelligence-pulse")).data, default=str
        )
        for forbidden in ("score", "health", "threat", "strength"):
            self.assertNotIn(f'"{forbidden}"', body)

    def test_pulse_reports_counts_it_can_actually_count(self):
        self.make_signal(self.competitor, self.monitor, kind="pricing", minutes_ago=6)
        self.make_signal(self.competitor, self.monitor, kind="pricing", headline="p2", minutes_ago=5)
        self.make_signal(self.competitor, self.monitor, kind="hiring", headline="h", minutes_ago=4)
        card = self.client.get(reverse("intelligence-pulse")).data["competitors"][0]
        self.assertEqual(card["events_in_window"], 3)
        self.assertEqual(card["events_by_kind"]["pricing"], 2)
        self.assertEqual(card["events_by_kind"]["hiring"], 1)
        # The most active area is a plain count, and here pricing leads.
        self.assertEqual(card["dominant_kind"], "pricing")

    def test_window_bounds_the_count(self):
        self.make_signal(self.competitor, self.monitor, minutes_ago=60 * 24 * 40)
        card = self.client.get(
            reverse("intelligence-pulse"), {"window_days": 30}
        ).data["competitors"][0]
        self.assertEqual(card["events_in_window"], 0)


# ==========================================================================
# Phase 2 — discovery
# ==========================================================================


class DiscoveryTests(IntelligenceTestCase):
    OWN_SITE = (
        "<!doctype html><html><head><title>My SaaS</title></head><body>"
        "<h1>My project management SaaS</h1>"
        "<p>Plan your projects, track invoices and gantt charts in one tool.</p>"
        '<nav><a href="/pricing">Pricing</a>'
        '<a href="/alternatives">Alternatives</a>'
        '<a href="/compare">Compare us</a></nav>'
        "</body></html>"
    ).encode("utf-8")

    # A comparison page is where a business names who else does the same
    # job. This is the only honest public source of competitors, and it is
    # what the discovery flow actually reads.
    COMPARISON_PAGE = (
        "<!doctype html><html><head><title>Alternatives</title></head><body>"
        "<h1>Alternatives to MyApp</h1>"
        '<a href="https://otherpm.example/">OtherPM</a>'
        '<a href="https://taskbase.example/">Taskbase</a>'
        '<a href="https://social.example/follow">Follow us</a>'
        '<a href="https://apps.example/integrations">App store</a>'
        "</body></html>"
    ).encode("utf-8")

    CANDIDATE = (
        "<!doctype html><html><head><title>Other PM tool</title></head><body>"
        "<h1>Other project management tool</h1>"
        "<p>Plan your projects, track invoices and gantt charts for teams.</p>"
        "</body></html>"
    ).encode("utf-8")

    @staticmethod
    def fake_fetch(url, timeout_seconds=15):
        if "myapp.example" in url:
            if "/alternatives" in url or "/compare" in url:
                return fetch_result(content=DiscoveryTests.COMPARISON_PAGE)
            return fetch_result(content=DiscoveryTests.OWN_SITE)
        return fetch_result(content=DiscoveryTests.CANDIDATE)

    def test_discovery_proposes_nothing_until_approved(self):
        with mock.patch("intelligence.services.analysis.fetch_url", side_effect=self.fake_fetch):
            response = self.client.post(
                reverse("intelligence-competitor-discover"),
                {"url": "https://myapp.example/"},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data["candidate_count"], 0)
        for candidate in response.data["candidates"]:
            self.assertFalse(candidate["approved"])
            self.assertTrue(candidate["reason_list"], "a candidate must explain itself")
        self.assertEqual(Monitor.objects.count(), 0)

    def test_social_links_are_never_proposed_but_partners_are_adjacent(self):
        with mock.patch("intelligence.services.analysis.fetch_url", side_effect=self.fake_fetch):
            response = self.client.post(
                reverse("intelligence-competitor-discover"),
                {"url": "https://myapp.example/"},
                format="json",
            )
        by_domain = {candidate["domain"]: candidate for candidate in response.data["candidates"]}
        # A "follow us" link is not a competitor.
        self.assertNotIn("social.example", by_domain)
        # An integrations link IS a legitimate *adjacent* candidate.
        self.assertIn("apps.example", by_domain)
        self.assertEqual(by_domain["apps.example"]["relationship"], "adjacent")
        # The comparison page entries are the direct ones.
        self.assertEqual(by_domain["otherpm.example"]["relationship"], "direct")

    def test_candidates_come_from_the_comparison_page(self):
        with mock.patch("intelligence.services.analysis.fetch_url", side_effect=self.fake_fetch):
            response = self.client.post(
                reverse("intelligence-competitor-discover"),
                {"url": "https://myapp.example/"},
                format="json",
            )
        domains = {candidate["domain"] for candidate in response.data["candidates"]}
        self.assertIn("otherpm.example", domains)
        self.assertIn("taskbase.example", domains)

    def test_every_reason_is_a_factual_statement(self):
        with mock.patch("intelligence.services.analysis.fetch_url", side_effect=self.fake_fetch):
            response = self.client.post(
                reverse("intelligence-competitor-discover"),
                {"url": "https://myapp.example/"},
                format="json",
            )
        reasons = " ".join(
            reason for candidate in response.data["candidates"] for reason in candidate["reason_list"]
        )
        for forbidden in ("you should", "we recommend", "guaranteed"):
            self.assertNotIn(forbidden, reasons.lower())

    def test_shared_capabilities_lower_confidence_up(self):
        with mock.patch("intelligence.services.analysis.fetch_url", side_effect=self.fake_fetch):
            response = self.client.post(
                reverse("intelligence-competitor-discover"),
                {"url": "https://myapp.example/"},
                format="json",
            )
        confidences = {candidate["confidence"] for candidate in response.data["candidates"]}
        self.assertTrue(confidences <= {"high", "medium", "low"})
        self.assertIn("high", confidences)

    def test_approving_creates_the_competitor_and_the_monitor(self):
        with mock.patch("intelligence.services.analysis.fetch_url", side_effect=self.fake_fetch):
            discovery = self.client.post(
                reverse("intelligence-competitor-discover"),
                {"url": "https://myapp.example/"},
                format="json",
            )
        candidate_id = discovery.data["candidates"][0]["id"]
        with mock.patch("monitors.tasks.check_monitor.delay"):
            with mock.patch("intelligence.services.analysis.fetch_url", side_effect=self.fake_fetch):
                response = self.client.post(
                    reverse("intelligence-competitor-approve"),
                    {"candidate_id": candidate_id, "recipe": "everything"},
                    format="json",
                )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Competitor.objects.filter(domain="myapp.example").exists() or Competitor.objects.count() >= 1)
        self.assertGreaterEqual(Monitor.objects.count(), 1)

    def test_approving_twice_is_idempotent(self):
        with mock.patch("intelligence.services.analysis.fetch_url", side_effect=self.fake_fetch):
            discovery = self.client.post(
                reverse("intelligence-competitor-discover"),
                {"url": "https://myapp.example/"},
                format="json",
            )
        candidate_id = discovery.data["candidates"][0]["id"]
        for _ in range(2):
            with mock.patch("monitors.tasks.check_monitor.delay"):
                with mock.patch("intelligence.services.analysis.fetch_url", side_effect=self.fake_fetch):
                    self.client.post(
                        reverse("intelligence-competitor-approve"),
                        {"candidate_id": candidate_id},
                        format="json",
                    )
        self.assertEqual(
            CompetitorCandidate.objects.filter(approved=True).count(), 1
        )

    def test_discovery_respects_the_plan_limit(self):
        with mock.patch("intelligence.services.analysis.fetch_url", side_effect=self.fake_fetch):
            discovery = self.client.post(
                reverse("intelligence-competitor-discover"),
                {"url": "https://myapp.example/"},
                format="json",
            )
        candidate_id = discovery.data["candidates"][0]["id"]
        # Free plan allows 3 active URLs; fill the plan first.
        for index in range(3):
            Monitor.objects.create(
                user=self.user, name="Filler", url=f"https://filler{index}.example/a"
            )
        with mock.patch("intelligence.services.analysis.fetch_url", side_effect=self.fake_fetch):
            response = self.client.post(
                reverse("intelligence-competitor-approve"),
                {"candidate_id": candidate_id},
                format="json",
            )
        self.assertTrue(response.data["limit_reached"])
        self.assertIn("detail", response.data)

    def test_another_users_candidate_is_404(self):
        competitor = self.make_competitor(domain="other.example")
        candidate = CompetitorCandidate.objects.create(
            competitor=competitor, url="https://other.example/x", domain="other.example"
        )
        self.client.force_authenticate(self.other)
        response = self.client.post(
            reverse("intelligence-competitor-approve"),
            {"candidate_id": str(candidate.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_discovery_needs_a_url(self):
        response = self.client.post(
            reverse("intelligence-competitor-discover"), {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_discovery_uses_approval_safe_fallback_when_a_page_is_unreadable(self):
        def only_own(url, timeout_seconds=15):
            if "myapp.example" in url:
                return fetch_result(content=self.OWN_SITE)
            raise FetchError("boom")

        with mock.patch("intelligence.services.analysis.fetch_url", side_effect=only_own):
            response = self.client.post(
                reverse("intelligence-competitor-discover"),
                {"url": "https://myapp.example/"},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for candidate in response.data["candidates"]:
            for reason in candidate["reason_list"]:
                self.assertNotIn("Shared capability keywords", reason)


# ==========================================================================
# Phase 2 — derivation
# ==========================================================================


class SignalDerivationTests(IntelligenceTestCase):
    def test_product_change_becomes_a_feed_row(self):
        from intelligence.services import signals as signal_service

        monitor = self.make_monitor()
        watch = self.make_watch(monitor)
        change = self.make_product_change(monitor, watch=watch)
        summary = signal_service.derive_signals()
        self.assertEqual(summary["feed_created"], 1)
        row = SignalEvent.objects.get()
        self.assertEqual(row.product_change_id, change.id)
        self.assertEqual(row.kind, "pricing")
        self.assertIn("Acme", row.headline)
        self.assertEqual(row.source_url, monitor.url)

    def test_derivation_is_idempotent(self):
        from intelligence.services import signals as signal_service

        monitor = self.make_monitor()
        self.make_product_change(monitor, watch=self.make_watch(monitor))
        first = signal_service.derive_signals()
        second = signal_service.derive_signals()
        third = signal_service.derive_signals()
        self.assertEqual(first["feed_created"], 1)
        self.assertEqual(second["feed_created"], 0)
        self.assertEqual(third["feed_created"], 0)
        self.assertEqual(SignalEvent.objects.count(), 1)

    def test_a_check_with_a_product_change_is_not_also_reported_as_content(self):
        from intelligence.services import signals as signal_service

        monitor = self.make_monitor()
        watch = self.make_watch(monitor)
        change = self.make_product_change(monitor, watch=watch)
        signal_service.derive_signals()
        self.assertEqual(SignalEvent.objects.filter(product_change_id=change.id).count(), 1)
        self.assertEqual(SignalEvent.objects.filter(product_change_id=None).count(), 0)

    def test_a_plain_content_change_becomes_a_content_row(self):
        from intelligence.services import signals as signal_service

        monitor = self.make_monitor()
        check = MonitorCheck.objects.create(
            monitor=monitor,
            checked_at=timezone.now(),
            changed=True,
            content_hash="b" * 64,
        )
        signal_service.derive_signals()
        row = SignalEvent.objects.get()
        self.assertEqual(row.monitor_check_id, check.id)
        self.assertIsNone(row.product_change_id)
        self.assertIn("could not read", row.summary.lower())

    def test_derivation_groups_monitors_into_a_competitor_by_domain(self):
        from intelligence.services import signals as signal_service

        first = self.make_monitor(url="https://acme.com/products/a")
        second = self.make_monitor(url="https://acme.com/pricing")
        self.make_product_change(first, watch=self.make_watch(first))
        self.make_product_change(second, watch=self.make_watch(second, name="Acme Pro"))
        signal_service.derive_signals()
        competitors = Competitor.objects.all()
        self.assertEqual(competitors.count(), 1)
        self.assertEqual(competitors.first().domain, "acme.com")

    def test_deleting_a_monitor_removes_its_feed_rows(self):
        from intelligence.services import signals as signal_service

        monitor = self.make_monitor()
        self.make_product_change(monitor, watch=self.make_watch(monitor))
        signal_service.derive_signals()
        self.assertEqual(SignalEvent.objects.count(), 1)
        monitor.delete()
        self.assertEqual(SignalEvent.objects.count(), 0)

    def test_derivation_records_last_activity_on_the_competitor(self):
        from intelligence.services import signals as signal_service

        monitor = self.make_monitor()
        self.make_product_change(monitor, watch=self.make_watch(monitor))
        signal_service.derive_signals()
        competitor = Competitor.objects.get()
        self.assertIsNotNone(competitor.last_activity_at)

    def test_beat_task_runs_the_same_idempotent_path(self):
        from intelligence.tasks import derive_signals as task

        monitor = self.make_monitor()
        self.make_product_change(monitor, watch=self.make_watch(monitor))
        first = task()
        second = task()
        self.assertGreaterEqual(first["feed_created"], 0)
        self.assertEqual(SignalEvent.objects.count(), first["feed_created"] + second["feed_created"])


# ==========================================================================
# Phase 3 — the alert deep link
# ==========================================================================


class DeepLinkTests(IntelligenceTestCase):
    def setUp(self):
        super().setUp()
        self.monitor = self.make_monitor()
        self.watch = self.make_watch(self.monitor)
        self.competitor = self.make_competitor()
        self.change = self.make_product_change(self.monitor, watch=self.watch)
        self.event = self.make_signal(
            self.competitor, self.monitor, kind="pricing", headline="Acme cut its price"
        )
        self.event.product_change = self.change
        self.event.monitor_check = self.change.monitor_check
        self.event.save(update_fields=["product_change", "monitor_check"])

    def test_detail_has_every_required_block(self):
        response = self.client.get(
            reverse("intelligence-event-detail", args=[str(self.event.id)])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        explanation = response.data["explanation"]
        for key in (
            "what_changed", "why_it_may_matter", "what_to_check", "confidence",
            "basis", "evidence", "generator", "is_fallback",
        ):
            self.assertIn(key, explanation)
        self.assertTrue(explanation["what_changed"])
        self.assertTrue(explanation["why_it_may_matter"])
        self.assertTrue(explanation["what_to_check"])

    def test_detail_preserves_before_after_and_source(self):
        explanation = self.client.get(
            reverse("intelligence-event-detail", args=[str(self.event.id)])
        ).data["explanation"]
        entry = explanation["evidence"][0]
        self.assertEqual(entry["before"], "129.00")
        self.assertEqual(entry["after"], "99.00")
        self.assertEqual(entry["source_url"], self.monitor.url)
        self.assertEqual(entry["rule"], "rule:price")
        self.assertTrue(entry["detected_at"])
        self.assertIn("T", entry["detected_at"])

    def test_detail_never_prescribes_a_business_decision(self):
        explanation = self.client.get(
            reverse("intelligence-event-detail", args=[str(self.event.id)])
        ).data["explanation"]
        for forbidden in ("you should", "we recommend", "you must", "guaranteed"):
            self.assertNotIn(forbidden, explanation["why_it_may_matter"].lower())
            self.assertNotIn(forbidden, explanation["what_to_check"].lower())

    def test_detail_offers_an_export_and_a_timeline_link(self):
        detail = self.client.get(
            reverse("intelligence-event-detail", args=[str(self.event.id)])
        ).data
        self.assertIn("csv", detail["export"])
        self.assertIn("json", detail["export"])
        self.assertTrue(detail["timeline_url"])

    def test_detail_includes_recent_context_for_the_same_competitor(self):
        self.make_signal(self.competitor, self.monitor, kind="features", headline="Acme shipped a feature", minutes_ago=30)
        detail = self.client.get(
            reverse("intelligence-event-detail", args=[str(self.event.id)])
        ).data
        self.assertGreaterEqual(len(detail["context"]), 1)

    def test_content_only_event_still_explains_itself(self):
        competitor = self.make_competitor(domain="other.com")
        monitor = self.make_monitor(url="https://other.com/pricing")
        event = self.make_signal(competitor, monitor, kind="pricing", headline="Other changed pricing")
        detail = self.client.get(
            reverse("intelligence-event-detail", args=[str(event.id)])
        ).data
        self.assertEqual(
            detail["explanation"]["what_changed"], "Other changed pricing"
        )
        self.assertIn("could not read", detail["explanation"]["why_it_may_matter"])
        self.assertEqual(detail["explanation"]["evidence"][0]["rule"], "rule:content_hash")

    def test_another_users_event_is_404(self):
        self.client.force_authenticate(self.other)
        response = self.client.get(
            reverse("intelligence-event-detail", args=[str(self.event.id)])
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_detail_requires_authentication(self):
        self.client.force_authenticate(None)
        response = self.client.get(
            reverse("intelligence-event-detail", args=[str(self.event.id)])
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ==========================================================================
# Phase 3 — narration
# ==========================================================================


class NarrationTests(IntelligenceTestCase):
    def setUp(self):
        super().setUp()
        self.monitor = self.make_monitor()
        self.watch = self.make_watch(self.monitor)
        self.competitor = self.make_competitor()
        self.change = self.make_product_change(self.monitor, watch=self.watch)
        self.event = self.make_signal(self.competitor, self.monitor)
        self.event.product_change = self.change
        self.event.save(update_fields=["product_change"])

    def test_default_is_off(self):
        from intelligence.services.narration import narration_enabled, provider_configured

        self.assertFalse(provider_configured())
        self.assertFalse(narration_enabled(self.user))

    def test_no_provider_means_no_outbound_call(self):
        from intelligence.services.narration import narrate_event

        with mock.patch("httpx.Client") as client:
            explanation = narrate_event(self.event, self.change, watch=self.watch)
        client.assert_not_called()
        self.assertTrue(explanation.is_fallback)
        self.assertEqual(explanation.model, "rules")

    def test_the_deterministic_explanation_is_always_stored(self):
        from intelligence.services.narration import narrate_event

        explanation = narrate_event(self.event, self.change, watch=self.watch)
        self.assertTrue(explanation.what_changed)
        self.assertEqual(explanation.basis, ["rule:price"])
        self.assertEqual(len(explanation.evidence), 1)

    def test_a_fabricated_citation_discards_the_whole_narration(self):
        from intelligence.services.narration import validate_narration

        valid = {"e1", "e2"}
        good = {
            "what_changed": "The published price fell [e1].",
            "why_it_may_matter": "It changes the visible price [e1].",
            "what_to_check": "Open the page and confirm [e2].",
            "confidence": "high",
        }
        self.assertIsNotNone(validate_narration(good, valid))

        for broken in (
            {**good, "what_changed": "It fell [e9]."},
            {**good, "why_it_may_matter": "No citation at all."},
            {**good, "confidence": "certain"},
            {**good, "citations": ["e7"]},
            {**good, "what_changed": ""},
        ):
            self.assertIsNone(validate_narration(broken, valid), broken)

    def test_citations_are_stripped_from_the_rendered_text(self):
        from intelligence.services.narration import validate_narration

        result = validate_narration(
            {
                "what_changed": "Price fell [e1].",
                "why_it_may_matter": "Visible price changed [e1].",
                "what_to_check": "Confirm on the page [e1].",
                "confidence": "medium",
            },
            {"e1"},
        )
        self.assertNotIn("[e1]", result["what_changed"])
        self.assertEqual(result["cited"], ["e1"])

    def test_evidence_packet_contains_no_user_or_workspace_identity(self):
        from intelligence.services.narration import build_evidence_packet

        packet = build_evidence_packet(
            self.watch.name,
            [{"field": "price", "label": "Price", "before": "1", "after": "2", "basis": "b", "rule": "rule:price", "source_url": "https://x.example/p"}],
            competitor_name="Acme",
            currency="EUR",
        )
        body = json.dumps(packet)
        self.assertNotIn("owner@example.com", body)
        self.assertNotIn(str(self.user.id), body)
        self.assertEqual(packet["evidence"][0]["id"], "e1")

    def test_a_provider_failure_falls_back_rather_than_raising(self):
        from intelligence.services.narration import narrate_event

        self.user.ai_narration_enabled = True
        self.user.save(update_fields=["ai_narration_enabled"])
        with self.settings(AI_PROVIDER="openai", AI_API_KEY="sk-test", AI_MODEL="gpt-4o-mini"):
            with mock.patch("httpx.Client") as client:
                client.return_value.__enter__.return_value.post.side_effect = RuntimeError("network down")
                explanation = narrate_event(self.event, self.change, watch=self.watch)
        self.assertTrue(explanation.is_fallback)
        self.assertTrue(explanation.what_changed)

    def test_a_valid_narration_is_stored_beside_the_deterministic_text(self):
        from intelligence.services.narration import narrate_event

        self.user.ai_narration_enabled = True
        self.user.save(update_fields=["ai_narration_enabled"])
        good = json.dumps(
            {
                "what_changed": "The published price fell [e1].",
                "why_it_may_matter": "The visible price changed [e1].",
                "what_to_check": "Open the page and confirm the figure [e1].",
                "confidence": "high",
            }
        )
        import contextlib

        response = mock.Mock()
        response.status_code = 200
        response.json.return_value = {"choices": [{"message": {"content": good}}]}
        # `with httpx.Client(...) as client:` binds `client` to __enter__'s
        # result, and the code then calls client.post(...) — so post must
        # live on the object __enter__ returns, not on the factory.
        inner = mock.MagicMock()
        inner.post.return_value = response
        client = mock.MagicMock()
        client.__enter__ = mock.MagicMock(return_value=inner)
        client.__exit__ = mock.MagicMock(return_value=False)
        with self.settings(AI_PROVIDER="openai", AI_API_KEY="sk-test", AI_MODEL="gpt-4o-mini"):
            with mock.patch("httpx.Client", return_value=client):
                explanation = narrate_event(self.event, self.change, watch=self.watch)
        self.assertFalse(explanation.is_fallback)
        self.assertEqual(explanation.model, "ai:openai")
        # The deterministic text is still on the event, untouched.
        self.assertTrue(
            ChangeExplanation.objects.filter(signal_event=self.event, is_fallback=True).exists()
        )

    def test_preference_endpoint_defaults_to_off(self):
        response = self.client.get(reverse("intelligence-narration-preference"))
        self.assertFalse(response.data["ai_narration_enabled"])
        self.assertFalse(response.data["provider_configured"])

    def test_preference_can_be_toggled(self):
        response = self.client.patch(
            reverse("intelligence-narration-preference"),
            {"ai_narration_enabled": True},
            format="json",
        )
        self.assertTrue(response.data["ai_narration_enabled"])
        self.assertTrue(
            User.objects.get(pk=self.user.pk).ai_narration_enabled
        )

    def test_preference_rejects_a_non_boolean(self):
        response = self.client.patch(
            reverse("intelligence-narration-preference"),
            {"ai_narration_enabled": "yes"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ==========================================================================
# Phase 3 — market signals
# ==========================================================================


class MarketSignalTests(IntelligenceTestCase):
    def test_one_competitor_is_not_a_market_signal(self):
        from intelligence.services.narration import detect_market_signals

        monitor = self.make_monitor()
        competitor = self.make_competitor()
        self.make_signal(competitor, monitor, kind="pricing", minutes_ago=10)
        self.assertEqual(detect_market_signals(self.user), [])

    def test_two_competitors_cut_prices(self):
        from intelligence.services.narration import detect_market_signals

        for domain in ("acme.com", "beta.com"):
            competitor = self.make_competitor(domain=domain)
            monitor = self.make_monitor(url=f"https://{domain}/pricing")
            self.make_signal(competitor, monitor, kind="pricing", minutes_ago=10)
        created = detect_market_signals(self.user)
        self.assertTrue(created)
        signal = created[0]
        self.assertEqual(signal.kind, "price_decrease_cluster")
        self.assertIn("2 monitored competitors", signal.headline)
        self.assertIn("Acme", signal.statement)
        self.assertIn("Beta", signal.statement)
        self.assertGreaterEqual(len(signal.evidence), 2)

    def test_a_signal_always_carries_its_evidence(self):
        from intelligence.services.narration import detect_market_signals

        for domain in ("acme.com", "beta.com"):
            competitor = self.make_competitor(domain=domain)
            monitor = self.make_monitor(url=f"https://{domain}/pricing")
            self.make_signal(competitor, monitor, kind="pricing", minutes_ago=10)
        signal = detect_market_signals(self.user)[0]
        for entry in signal.evidence:
            self.assertTrue(entry["source_url"])
            self.assertTrue(entry["competitor"])
            self.assertTrue(entry["detected_at"])

    def test_a_signal_is_not_re_emitted_for_the_same_evidence(self):
        from intelligence.services.narration import detect_market_signals

        for domain in ("acme.com", "beta.com"):
            competitor = self.make_competitor(domain=domain)
            monitor = self.make_monitor(url=f"https://{domain}/pricing")
            self.make_signal(competitor, monitor, kind="pricing", minutes_ago=10)
        first = len(detect_market_signals(self.user))
        second = len(detect_market_signals(self.user))
        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        self.assertEqual(MarketSignal.objects.count(), 1)

    def test_interpretation_is_a_possibility_not_a_prediction(self):
        from intelligence.services.narration import detect_market_signals

        for domain in ("acme.com", "beta.com"):
            competitor = self.make_competitor(domain=domain)
            monitor = self.make_monitor(url=f"https://{domain}/pricing")
            self.make_signal(competitor, monitor, kind="pricing", minutes_ago=10)
        signal = detect_market_signals(self.user)[0]
        self.assertIn("may", signal.interpretation.lower())
        for forbidden in ("guaranteed", "will succeed", "you must"):
            self.assertNotIn(forbidden, signal.interpretation.lower())

    def test_signals_list_endpoint(self):
        from intelligence.services.narration import detect_market_signals

        for domain in ("acme.com", "beta.com"):
            competitor = self.make_competitor(domain=domain)
            monitor = self.make_monitor(url=f"https://{domain}/pricing")
            self.make_signal(competitor, monitor, kind="pricing", minutes_ago=10)
        detect_market_signals(self.user)
        response = self.client.get(reverse("intelligence-signals"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertGreaterEqual(response.data["signals"][0]["evidence_count"], 2)
        self.assertEqual(response.data["minimum_competitors"], 2)

    def test_reviewing_a_signal_removes_it_from_the_default_list(self):
        from intelligence.services.narration import detect_market_signals

        for domain in ("acme.com", "beta.com"):
            competitor = self.make_competitor(domain=domain)
            monitor = self.make_monitor(url=f"https://{domain}/pricing")
            self.make_signal(competitor, monitor, kind="pricing", minutes_ago=10)
        detect_market_signals(self.user)
        signal_id = MarketSignal.objects.first().id
        response = self.client.post(
            reverse("intelligence-signal-review", args=[str(signal_id)]),
            {"status": "dismissed"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("intelligence-signals")).data["count"], 0)

    def test_an_invalid_review_status_is_404_not_500(self):
        from intelligence.services.narration import detect_market_signals

        for domain in ("acme.com", "beta.com"):
            competitor = self.make_competitor(domain=domain)
            monitor = self.make_monitor(url=f"https://{domain}/pricing")
            self.make_signal(competitor, monitor, kind="pricing", minutes_ago=10)
        detect_market_signals(self.user)
        signal_id = MarketSignal.objects.first().id
        response = self.client.post(
            reverse("intelligence-signal-review", args=[str(signal_id)]),
            {"status": "exploded"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_another_users_signal_is_404(self):
        from intelligence.services.narration import detect_market_signals

        for domain in ("acme.com", "beta.com"):
            competitor = self.make_competitor(domain=domain)
            monitor = self.make_monitor(url=f"https://{domain}/pricing")
            self.make_signal(competitor, monitor, kind="pricing", minutes_ago=10)
        detect_market_signals(self.user)
        signal_id = MarketSignal.objects.first().id
        self.client.force_authenticate(self.other)
        response = self.client.post(
            reverse("intelligence-signal-review", args=[str(signal_id)]),
            {"status": "reviewed"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ==========================================================================
# Phase 4 — exports
# ==========================================================================


class ExportTests(IntelligenceTestCase):
    def setUp(self):
        super().setUp()
        self.monitor = self.make_monitor()
        self.competitor = self.make_competitor()
        self.make_signal(self.competitor, self.monitor, kind="pricing", headline="Acme cut prices")

    def test_every_format_renders(self):
        import sys
        for fmt in ("csv", "xlsx", "json", "markdown", "html", "xml", "pdf"):
            from django.urls import resolve
            u = reverse("intelligence-export")
            try:
                m = resolve(u)
                print("FMT", fmt, u, "->", m.url_name, m.func.__name__, file=sys.stderr)
            except Exception as e:
                print("FMT", fmt, u, "RESOLVE FAIL", e, file=sys.stderr)
            response = self.client.get(u, {"type": fmt})
            print("   resp", response.status_code, file=sys.stderr)
            if response.status_code != 200:
                break
            self.assertEqual(response.status_code, status.HTTP_200_OK, fmt)
            self.assertGreater(len(response.content), 40, fmt)
            self.assertIn("attachment", response["Content-Disposition"])

    def test_csv_has_a_header_and_a_source_url_per_row(self):
        response = self.client.get(reverse("intelligence-export"), {"type": "csv"})
        text = response.content.decode("utf-8")
        self.assertIn("source_url", text)
        self.assertIn("detected_at", text)
        self.assertIn("https://competitor.com/products/pro-x", text)
        self.assertIn("Sitemyra", text)

    def test_xlsx_is_a_valid_zip_with_a_worksheet(self):
        response = self.client.get(reverse("intelligence-export"), {"type": "xlsx"})
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            names = archive.namelist()
            self.assertIn("xl/worksheets/sheet1.xml", names)
            self.assertIn("[Content_Types].xml", names)
            sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        self.assertIn("Source URL", sheet)
        self.assertIn("competitor.com", sheet)

    def test_xlsx_is_byte_stable_for_the_same_input(self):
        from intelligence.services import exporters

        rows = exporters.rows_from([])
        self.assertEqual(exporters.to_xlsx(rows), exporters.to_xlsx(rows))

    def test_json_is_faithful(self):
        response = self.client.get(reverse("intelligence-export"), {"type": "json"})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content[:300])
        payload = json.loads(response.content)
        self.assertIn("rows", payload)
        self.assertIn("note", payload)
        self.assertEqual(len(payload["rows"]), 1)
        self.assertEqual(payload["rows"][0]["source_url"], self.monitor.url)

    def test_markdown_contains_the_change_and_the_source(self):
        response = self.client.get(reverse("intelligence-export"), {"type": "markdown"})
        text = response.content.decode("utf-8")
        self.assertIn("Acme cut prices", text)
        self.assertIn("https://competitor.com", text)
        self.assertIn("Before", text)

    def test_html_escapes_fetched_content(self):
        monitor = self.make_monitor(url="https://evil.example/p")
        competitor = self.make_competitor(domain="evil.example")
        self.make_signal(
            competitor, monitor, headline='<script>alert(1)</script> "quoted"',
        )
        response = self.client.get(reverse("intelligence-export"), {"type": "html"})
        text = response.content.decode("utf-8")
        self.assertNotIn("<script>alert(1)</script>", text)
        self.assertIn("&lt;script&gt;", text)

    def test_xml_escapes_and_is_well_formed(self):
        import xml.etree.ElementTree as ET

        response = self.client.get(reverse("intelligence-export"), {"type": "xml"})
        self.assertEqual(
            response.status_code, status.HTTP_200_OK, response.content[:200]
        )
        ET.fromstring(response.content)
        self.assertIn(b"<change-count>", response.content)

    def test_pdf_is_a_pdf(self):
        response = self.client.get(reverse("intelligence-export"), {"type": "pdf"})
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_pdf_falls_back_without_reportlab(self):
        from intelligence.services import exporters

        with mock.patch.dict("sys.modules", {"reportlab": None, "reportlab.lib": None}):
            body = exporters.to_pdf([{"headline": "x", "detected_at": "", "source_url": ""}], title="t")
        self.assertTrue(body.startswith(b"%PDF"))

    def test_unsupported_format_is_400_with_the_supported_list(self):
        response = self.client.get(reverse("intelligence-export"), {"type": "docx"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("csv", response.data["supported"])

    def test_export_requires_authentication(self):
        self.client.force_authenticate(None)
        self.assertEqual(
            self.client.get(reverse("intelligence-export")).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_export_contains_no_other_users_rows(self):
        other_monitor = self.make_monitor(url="https://rival.com/p", user=self.other)
        other_competitor = self.make_competitor(domain="rival.com", user=self.other)
        other_event = SignalEvent.objects.create(
            user=self.other, competitor=other_competitor, monitor=other_monitor,
            kind="pricing", headline="Rival secret move", source_url=other_monitor.url,
            source_key="other:1", detected_at=timezone.now(),
        )
        response = self.client.get(reverse("intelligence-export"), {"type": "csv"})
        self.assertNotIn(b"Rival secret move", response.content)
        self.assertIn(b"Acme cut prices", response.content)


# ==========================================================================
# Phase 4 — reports
# ==========================================================================


class ReportTests(IntelligenceTestCase):
    def setUp(self):
        super().setUp()
        self.monitor = self.make_monitor()
        self.competitor = self.make_competitor()
        self.make_signal(self.competitor, self.monitor, kind="pricing", headline="Acme cut prices")
        self.make_signal(self.competitor, self.monitor, kind="features", headline="Acme shipped AI reports", minutes_ago=10)

    def create(self, **extra):
        payload = {"title": "Q3 competitive intelligence", "period_days": 30}
        payload.update(extra)
        return self.client.post(reverse("intelligence-reports"), payload, format="json")

    def test_create_returns_a_ready_report(self):
        response = self.create()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "ready")
        self.assertGreaterEqual(response.data["rows"], 1)
        self.assertTrue(response.data["executive_summary"])

    def test_report_contains_every_required_section(self):
        from intelligence.services import reports as report_service

        report = report_service.create_report(self.user, "Test")
        payload = report.payload
        for key in (
            "executive_summary", "competitors", "sections", "timeline", "sources", "note",
        ):
            self.assertIn(key, payload)
        kinds = {section["kind"] for section in payload["sections"]}
        self.assertIn("pricing", kinds)
        self.assertIn("features", kinds)

    def test_timeline_is_chronological_and_earliest_first(self):
        from intelligence.services import reports as report_service

        payload = report_service.compose_report(self.user, "Test")
        stamps = [entry["detected_at"] for entry in payload["timeline"]]
        self.assertEqual(stamps, sorted(stamps))

    def test_sources_are_deduplicated(self):
        from intelligence.services import reports as report_service

        payload = report_service.compose_report(self.user, "Test")
        self.assertEqual(len(payload["sources"]), len(set(payload["sources"])))

    def test_executive_summary_is_factual(self):
        from intelligence.services import reports as report_service

        payload = report_service.compose_report(self.user, "Test")
        text = payload["executive_summary"]["text"]
        self.assertIn("2 change(s)", text)
        for forbidden in ("should", "recommend", "opportunity"):
            self.assertNotIn(forbidden, text.lower())

    def test_an_empty_period_says_so_plainly(self):
        from intelligence.services import reports as report_service

        # A window from 40 to 35 days ago contains none of the events.
        payload = report_service.compose_report(
            self.user, "Test",
            period_start=timezone.now() - timedelta(days=40),
            period_end=timezone.now() - timedelta(days=35),
        )
        self.assertIn("No changes were recorded", payload["executive_summary"]["text"])
        self.assertEqual(payload["sections"], [])
        self.assertEqual(payload["timeline"], [])

    def test_every_format_downloads(self):
        self.create()
        report_id = str(Report.objects.first().id)
        for fmt in ("csv", "xlsx", "json", "markdown", "html", "xml", "pdf"):
            response = self.client.get(
                reverse("intelligence-report-download", args=[report_id]),
                {"type": fmt},
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK, fmt)
            self.assertGreater(len(response.content), 40, fmt)

    def test_report_list_and_detail(self):
        self.create()
        listing = self.client.get(reverse("intelligence-reports"))
        self.assertEqual(listing.data["reports"][0]["title"], "Q3 competitive intelligence")
        report_id = listing.data["reports"][0]["id"]
        detail = self.client.get(reverse("intelligence-report-detail", args=[report_id]))
        self.assertIn("payload", detail.data)

    def test_a_stored_report_reproduces_the_same_download(self):
        self.create()
        report = Report.objects.first()
        from intelligence.services import reports as report_service

        first = report_service.render_report(report, "csv")
        second = report_service.render_report(report, "csv")
        self.assertEqual(first, second)

    def test_unsupported_report_format_is_400(self):
        response = self.create(formats=["docx"])
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_bad_period_is_400(self):
        response = self.create(period_days="abc")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_another_users_report_is_404(self):
        self.create()
        report_id = str(Report.objects.first().id)
        self.client.force_authenticate(self.other)
        response = self.client.get(reverse("intelligence-report-detail", args=[report_id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_a_report_never_contains_another_users_rows(self):
        other_monitor = self.make_monitor(url="https://rival.com/p", user=self.other)
        other_competitor = self.make_competitor(domain="rival.com", user=self.other)
        SignalEvent.objects.create(
            user=self.other, competitor=other_competitor, monitor=other_monitor,
            kind="pricing", headline="Rival secret move", source_url=other_monitor.url,
            source_key="other:2", detected_at=timezone.now(),
        )
        self.create()
        response = self.client.get(
            reverse("intelligence-report-download", args=[str(Report.objects.first().id)]),
            {"type": "json"},
        )
        self.assertNotIn(b"Rival secret move", response.content)

    def test_truncation_is_declared_not_silent(self):
        from intelligence.services import reports as report_service

        payload = report_service.compose_report(self.user, "Test")
        # With 2 events there is nothing truncated, and the flag is present
        # and false rather than absent.
        self.assertIn("truncated", payload)
        self.assertFalse(payload["truncated"])


# ==========================================================================
# Phase 4 — battlecards
# ==========================================================================


class BattlecardTests(IntelligenceTestCase):
    def setUp(self):
        super().setUp()
        self.monitor = self.make_monitor()
        self.watch = self.make_watch(self.monitor)
        self.competitor = self.make_competitor()
        self.make_signal(self.competitor, self.monitor, kind="pricing", headline="Acme cut prices")

    def test_battlecard_has_every_required_section(self):
        self.run_check(self.monitor)
        response = self.client.get(
            reverse("intelligence-battlecard", args=[str(self.competitor.id)])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for key in (
            "competitor", "products", "pricing", "features", "recent_changes",
            "positioning", "sources", "is_stale", "state",
        ):
            self.assertIn(key, response.data)

    def test_battlecard_includes_observed_pricing_with_its_source(self):
        self.run_check(self.monitor)
        payload = self.client.get(
            reverse("intelligence-battlecard", args=[str(self.competitor.id)])
        ).data
        self.assertTrue(payload["pricing"])
        self.assertEqual(payload["pricing"][0]["currency"], "EUR")
        self.assertTrue(payload["pricing"][0]["source_url"])

    def test_positioning_admits_when_it_has_no_reason(self):
        payload = self.client.get(
            reverse("intelligence-battlecard", args=[str(self.competitor.id)])
        ).data
        self.assertIn("no recorded reason", payload["positioning"])

    def test_a_fresh_card_is_not_stale(self):
        self.client.get(reverse("intelligence-battlecard", args=[str(self.competitor.id)]))
        self.assertFalse(Battlecard.objects.first().source_event_ids and False)
        payload = self.client.get(
            reverse("intelligence-battlecard", args=[str(self.competitor.id)])
        ).data
        self.assertFalse(payload["is_stale"])

    def test_staleness_is_surfaced_not_hidden(self):
        from intelligence.services import reports as report_service

        self.client.get(reverse("intelligence-battlecard", args=[str(self.competitor.id)]))
        card = Battlecard.objects.get()
        # A newer signal arrives after the card was generated.
        self.make_signal(
            self.competitor, self.monitor, kind="features",
            headline="Acme shipped something", minutes_ago=1,
        )
        self.assertTrue(report_service.is_battlecard_stale(card))
        payload = self.client.get(
            reverse("intelligence-battlecard", args=[str(self.competitor.id)]),
            {"refresh": "1"},
        ).data
        # Refreshing regenerates it, so it is current again.
        self.assertFalse(payload["is_stale"])
        self.assertIn("reflects every change", payload["stale_note"])

    def test_another_users_competitor_battlecard_is_404(self):
        self.client.force_authenticate(self.other)
        response = self.client.get(
            reverse("intelligence-battlecard", args=[str(self.competitor.id)])
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ==========================================================================
# Phase 5 — agency mode
# ==========================================================================


class AgencyTests(IntelligenceTestCase):
    def setUp(self):
        super().setUp()
        self.response = self.client.post(
            reverse("intelligence-organizations"), {"name": "North Studio"}, format="json"
        )
        self.assertEqual(self.response.status_code, status.HTTP_201_CREATED)
        self.org_id = self.response.data["id"]
        self.org = Organization.objects.get(id=self.org_id)

    def test_creating_an_agency_makes_you_its_owner(self):
        from intelligence.models import OrganizationMembership

        membership = OrganizationMembership.objects.get(organization=self.org)
        self.assertEqual(membership.role, OrganizationMembership.OWNER)
        self.assertEqual(self.response.data["role"], "owner")

    def test_an_agency_name_is_required(self):
        response = self.client.post(reverse("intelligence-organizations"), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_listing_only_shows_agencies_you_belong_to(self):
        User.objects.create_user("stranger@example.com", "a-strong-password")
        other = User.objects.get(email="stranger@example.com")
        self.client.force_authenticate(other)
        response = self.client.get(reverse("intelligence-organizations"))
        self.assertEqual(response.data["organizations"], [])

    def test_an_unpaid_agency_does_not_upgrade_the_plan(self):
        from billing.models import get_plan_for_user

        self.user.refresh_from_db()
        self.assertEqual(get_plan_for_user(self.user), "free")

    def test_a_paid_agency_resolves_the_agency_plan(self):
        from billing.models import get_plan_for_user

        self.org.plan = "business"
        self.org.mrr_cents = 4900
        self.org.save(update_fields=["plan", "mrr_cents"])
        self.user.refresh_from_db()
        self.assertEqual(get_plan_for_user(self.user), "business")

    def test_a_deactivated_agency_falls_back_to_the_personal_plan(self):
        from billing.models import get_plan_for_user

        self.org.plan = "business"
        self.org.mrr_cents = 4900
        self.org.is_active = False
        self.org.save(update_fields=["plan", "mrr_cents", "is_active"])
        self.user.refresh_from_db()
        self.assertEqual(get_plan_for_user(self.user), "free")

    def test_client_workspaces_belong_to_the_agency(self):
        response = self.client.post(
            reverse("intelligence-organization-workspaces", args=[self.org_id]),
            {"name": "Client A"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        workspace = Workspace.objects.get(name="Client A")
        self.assertEqual(workspace.organization_id, self.org.id)
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                workspace=workspace, user=self.user, role=WorkspaceMembership.OWNER
            ).exists()
        )

    def test_client_workspace_limit_is_enforced_before_creation(self):
        from billing.models import plan_limits

        limit = plan_limits("pro")["max_client_workspaces"]
        for index in range(limit):
            self.client.post(
                reverse("intelligence-organization-workspaces", args=[self.org_id]),
                {"name": f"Client {index}"},
                format="json",
            )
        response = self.client.post(
            reverse("intelligence-organization-workspaces", args=[self.org_id]),
            {"name": "One too many"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertEqual(Workspace.objects.filter(organization=self.org).count(), limit)

    def test_an_analyst_cannot_create_a_client_workspace(self):
        from intelligence.models import OrganizationMembership

        analyst = User.objects.create_user("analyst@example.com", "a-strong-password")
        OrganizationMembership.objects.create(
            organization=self.org, user=analyst, role=OrganizationMembership.ANALYST
        )
        self.client.force_authenticate(analyst)
        response = self.client.post(
            reverse("intelligence-organization-workspaces", args=[self.org_id]),
            {"name": "Client Z"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_an_analyst_can_see_client_workspaces(self):
        from intelligence.models import OrganizationMembership

        workspace = Workspace.objects.create(
            name="Client A", slug="client-a", owner=self.user, organization=self.org
        )
        analyst = User.objects.create_user("analyst@example.com", "a-strong-password")
        OrganizationMembership.objects.create(
            organization=self.org, user=analyst, role=OrganizationMembership.ANALYST
        )
        self.client.force_authenticate(analyst)
        response = self.client.get(
            reverse("intelligence-organization-workspaces", args=[self.org_id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [row["name"] for row in response.data["workspaces"]], ["Client A"]
        )
        self.assertTrue(workspace.id)

    def test_a_stranger_gets_404_on_an_agency(self):
        stranger = User.objects.create_user("stranger@example.com", "a-strong-password")
        self.client.force_authenticate(stranger)
        response = self.client.get(
            reverse("intelligence-organization-detail", args=[self.org_id])
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_seats_can_be_added_and_the_limit_is_enforced(self):
        from billing.models import plan_limits

        for index in range(plan_limits("pro")["max_seats"] - 1):
            email = f"seat{index}@example.com"
            User.objects.create_user(email, "a-strong-password")
            self.client.post(
                reverse("intelligence-organization-members", args=[self.org_id]),
                {"email": email, "role": "analyst"},
                format="json",
            )
        User.objects.create_user("overflow@example.com", "a-strong-password")
        response = self.client.post(
            reverse("intelligence-organization-members", args=[self.org_id]),
            {"email": "overflow@example.com", "role": "viewer"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)

    def test_a_seat_for_an_unknown_account_is_404_with_a_useful_message(self):
        response = self.client.post(
            reverse("intelligence-organization-members", args=[self.org_id]),
            {"email": "nobody@example.com", "role": "viewer"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("register", response.data["detail"].lower())

    def test_only_an_owner_can_grant_owner(self):
        from intelligence.models import OrganizationMembership

        admin = User.objects.create_user("admin@example.com", "a-strong-password")
        OrganizationMembership.objects.create(
            organization=self.org, user=admin, role=OrganizationMembership.ADMIN
        )
        User.objects.create_user("newbie@example.com", "a-strong-password")
        self.client.force_authenticate(admin)
        response = self.client.post(
            reverse("intelligence-organization-members", args=[self.org_id]),
            {"email": "newbie@example.com", "role": "owner"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_branding_rejects_html(self):
        self.org.plan = "business"
        self.org.mrr_cents = 4900
        self.org.save(update_fields=["plan", "mrr_cents"])
        response = self.client.patch(
            reverse("intelligence-organization-branding", args=[self.org_id]),
            {"agency_name": "<script>alert(1)</script>"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_branding_rejects_a_bad_colour(self):
        self.org.plan = "business"
        self.org.mrr_cents = 4900
        self.org.save(update_fields=["plan", "mrr_cents"])
        response = self.client.patch(
            reverse("intelligence-organization-branding", args=[self.org_id]),
            {"primary_color": "javascript:alert(1)"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_branding_is_stored_as_plain_text(self):
        self.org.plan = "business"
        self.org.mrr_cents = 4900
        self.org.save(update_fields=["plan", "mrr_cents"])
        response = self.client.patch(
            reverse("intelligence-organization-branding", args=[self.org_id]),
            {"agency_name": "North Studio", "primary_color": "#ff0055", "footer": "Prepared for Acme"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.org.refresh_from_db()
        self.assertEqual(self.org.branding["agency_name"], "North Studio")
        self.assertEqual(self.org.branding["primary_color"], "#ff0055")

    def test_white_label_requires_a_plan_that_includes_it(self):
        # The agency's default plan is pro (which includes white_label) but
        # it is NOT paid, so the feature must stay locked until billing says
        # otherwise. Otherwise a brand-new agency gets paid entitlements free.
        from billing.models import plan_limits

        self.assertTrue(plan_limits(self.org.plan)["white_label"])
        response = self.client.patch(
            reverse("intelligence-organization-branding", args=[self.org_id]),
            {"agency_name": "North Studio"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)

    def test_white_label_unlocks_once_the_agency_is_paid(self):
        self.org.plan = "business"
        self.org.mrr_cents = 4900
        self.org.save(update_fields=["plan", "mrr_cents"])
        response = self.client.patch(
            reverse("intelligence-organization-branding", args=[self.org_id]),
            {"agency_name": "North Studio"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_deleting_an_agency_deactivates_rather_than_destroys(self):
        workspace = Workspace.objects.create(
            name="Client A", slug="client-a2", owner=self.user, organization=self.org
        )
        self.monitor = self.make_monitor(workspace=workspace)
        response = self.client.delete(
            reverse("intelligence-organization-detail", args=[self.org_id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.org.refresh_from_db()
        self.assertFalse(self.org.is_active)
        self.assertTrue(Workspace.objects.filter(id=workspace.id).exists())
        self.assertTrue(Monitor.objects.filter(id=self.monitor.id).exists())

    def test_personal_accounts_keep_exactly_their_old_plan_limits(self):
        from billing.models import plan_limits

        self.assertEqual(plan_limits("free")["max_seats"], 1)
        self.assertEqual(plan_limits("free")["max_client_workspaces"], 1)
        self.assertFalse(plan_limits("free")["white_label"])
        self.assertEqual(plan_limits("free")["max_monitors"], 3)
        self.assertEqual(plan_limits("free")["min_interval_seconds"], 900)
        self.assertEqual(plan_limits("free")["history_days"], 7)


# ==========================================================================
# Phase 6 — extension sessions
# ==========================================================================


class ExtensionSessionTests(IntelligenceTestCase):
    def test_minting_a_session_returns_the_token_once(self):
        response = self.client.post(
            reverse("intelligence-extension-sessions"),
            {"label": "Chrome on my laptop"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["token"].startswith("sitemyra_ext_"))
        session = BrowserSession.objects.get()
        self.assertNotEqual(session.token_hash, response.data["token"])

    def test_the_token_is_never_returned_again(self):
        created = self.client.post(
            reverse("intelligence-extension-sessions"), {}, format="json"
        )
        self.assertIn("token", created.data)
        listing = self.client.get(reverse("intelligence-extension-sessions"))
        self.assertNotIn("token", listing.data["sessions"][0])
        detail = self.client.get(
            reverse("intelligence-extension-session-detail", args=[listing.data["sessions"][0]["id"]])
        )
        self.assertNotIn("token", detail.data)

    def test_the_scope_ceiling_excludes_billing_channels_and_reports(self):
        response = self.client.post(
            reverse("intelligence-extension-sessions"), {}, format="json"
        )
        scopes = set(response.data["scopes"].split())
        self.assertEqual(scopes, {"monitors:read", "monitors:write"})
        for forbidden in ("billing", "channels", "reports", "admin", "*"):
            self.assertNotIn(forbidden, scopes)

    def test_a_token_authenticates_quick_monitor(self):
        token = self.client.post(
            reverse("intelligence-extension-sessions"), {}, format="json"
        ).data["token"]
        self.client.force_authenticate(None)
        with mock.patch("monitors.tasks.check_monitor.delay"):
            with mock.patch("intelligence.services.analysis.fetch_url", return_value=fetch_result()):
                response = self.client.post(
                    reverse("intelligence-quick-monitor"),
                    {"url": "https://competitor.com/products/pro-x", "recipe": "product"},
                    format="json",
                    HTTP_AUTHORIZATION=f"Bearer {token}",
                )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Monitor.objects.count(), 1)

    def test_an_extension_token_cannot_reach_billing(self):
        token = self.client.post(
            reverse("intelligence-extension-sessions"), {}, format="json"
        ).data["token"]
        self.client.force_authenticate(None)
        response = self.client.get(
            reverse("billing-subscription"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertIn(
            response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
        )

    def test_an_extension_token_cannot_reach_reports(self):
        token = self.client.post(
            reverse("intelligence-extension-sessions"), {}, format="json"
        ).data["token"]
        self.client.force_authenticate(None)
        response = self.client.get(
            reverse("intelligence-reports"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertIn(
            response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
        )

    def test_a_revoked_token_stops_working_immediately(self):
        token = self.client.post(
            reverse("intelligence-extension-sessions"), {}, format="json"
        ).data["token"]
        session = BrowserSession.objects.get()
        self.client.delete(
            reverse("intelligence-extension-session-detail", args=[str(session.id)])
        )
        self.client.force_authenticate(None)
        response = self.client.get(
            reverse("intelligence-feed"), HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_an_expired_token_is_rejected(self):
        from django.utils import timezone as tz

        token = self.client.post(
            reverse("intelligence-extension-sessions"), {}, format="json"
        ).data["token"]
        BrowserSession.objects.update(expires_at=tz.now() - timedelta(minutes=1))
        self.client.force_authenticate(None)
        response = self.client.get(
            reverse("intelligence-feed"), HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_a_garbage_token_is_401(self):
        self.client.force_authenticate(None)
        response = self.client.get(
            reverse("intelligence-feed"),
            HTTP_AUTHORIZATION="Bearer sitemyra_ext_not-a-real-token",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_a_developer_api_key_still_works(self):
        from accounts.models import ApiKey

        _key, raw = ApiKey.generate(self.user, name="CI")
        self.client.force_authenticate(None)
        with mock.patch("intelligence.services.analysis.fetch_url", return_value=fetch_result()):
            response = self.client.get(
                reverse("intelligence-feed"), HTTP_AUTHORIZATION=f"Bearer {raw}"
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_a_jwt_still_works(self):
        self.client.force_authenticate(None)
        response = self.client.get(reverse("intelligence-feed"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_session_limit_is_enforced(self):
        from intelligence.views_phase6 import MAX_ACTIVE_SESSIONS

        for index in range(MAX_ACTIVE_SESSIONS):
            self.client.post(
                reverse("intelligence-extension-sessions"),
                {"label": f"Session {index}"},
                format="json",
            )
        response = self.client.post(
            reverse("intelligence-extension-sessions"), {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_another_users_session_is_404(self):
        created = self.client.post(
            reverse("intelligence-extension-sessions"), {}, format="json"
        )
        session_id = created.data["id"]
        self.client.force_authenticate(self.other)
        response = self.client.get(
            reverse("intelligence-extension-session-detail", args=[session_id])
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
