"""Product diff, severity and explanation tests.

The severity ladder is the part of Sitemyra a user is most likely to act
on, so it is pinned here rule by rule — including the cases where the
diff must stay silent.
"""

from decimal import Decimal

from django.test import SimpleTestCase

from intelligence.services.product_diff import (
    CRITICAL,
    IMPORTANT,
    INFORMATIONAL,
    MINOR,
    confidence_for,
    diff_snapshots,
    discount_percent,
    explain,
    format_change_line,
    severity_of,
    summarize,
)


def state(**overrides):
    """Build a facts-shaped map: ``price=("99.00", "jsonld")``."""
    facts = {}
    for key, value in overrides.items():
        if isinstance(value, tuple):
            raw, method = value
        else:
            raw, method = value, "jsonld"
        facts[key] = {"value": raw, "method": method, "raw": f"raw:{raw}"}
    return facts


def only(previous, current, field_name):
    changes = diff_snapshots(previous, current, source_url="https://x.example/p")
    return [change for change in changes if change["field"] == field_name]


class DiffSilenceTests(SimpleTestCase):
    def test_first_observation_never_produces_a_change(self):
        # A brand new product watch must not alert "everything changed".
        self.assertEqual(diff_snapshots(None, state(price="99.00")), [])
        self.assertEqual(diff_snapshots({}, state(price="99.00")), [])

    def test_identical_state_produces_nothing(self):
        snapshot = state(price="99.00", availability="in_stock")
        self.assertEqual(diff_snapshots(snapshot, dict(snapshot)), [])

    def test_a_field_that_appears_for_the_first_time_is_not_a_change(self):
        # Extraction flakiness must not read as a competitor action.
        changes = diff_snapshots(state(price="99.00"), state(price="99.00", rating="4.5"))
        self.assertEqual(changes, [])

    def test_a_field_that_never_had_a_value_can_vanish_silently(self):
        changes = diff_snapshots(state(price="99.00", rating=""), state(price="99.00"))
        self.assertEqual(changes, [])


class PriceDiffTests(SimpleTestCase):
    def test_large_decrease_is_important(self):
        changes = only(state(price="129.00"), state(price="99.00"), "price")
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["severity"], IMPORTANT)
        self.assertIn("decreased", changes[0]["basis"])
        self.assertIn("23.3%", changes[0]["basis"])
        self.assertEqual(changes[0]["before"], "129.00")
        self.assertEqual(changes[0]["after"], "99.00")

    def test_large_increase_is_important(self):
        changes = only(state(price="49.00"), state(price="59.00"), "price")
        self.assertEqual(changes[0]["severity"], IMPORTANT)
        self.assertIn("increased", changes[0]["basis"])

    def test_small_move_is_informational(self):
        changes = only(state(price="100.00"), state(price="102.00"), "price")
        self.assertEqual(changes[0]["severity"], INFORMATIONAL)

    def test_equivalent_decimal_spellings_are_equal(self):
        # "99" and "99.00" are the same price; reading it through a
        # different extraction path must not raise a false alarm.
        self.assertEqual(
            only(state(price="99.00"), state(price=("99", "heuristic")), "price"), []
        )

    def test_currency_change_is_reported(self):
        changes = only(state(price="99.00", currency="EUR"), state(price="99.00", currency="USD"), "currency")
        self.assertEqual(changes[0]["severity"], IMPORTANT)

    def test_a_different_reading_path_downgrades_confidence(self):
        changes = only(
            state(price=("100.00", "jsonld")),
            state(price=("80.00", "heuristic")),
            "price",
        )
        self.assertEqual(changes[0]["severity"], INFORMATIONAL)
        self.assertIn("confirm on the page", changes[0]["basis"])

    def test_price_disappearing_is_reported(self):
        changes = only(state(price="99.00", availability="in_stock"), state(availability="in_stock"), "price")
        self.assertEqual(len(changes), 1)
        self.assertIn("no longer published", format_change_line(changes[0]))


class AvailabilityDiffTests(SimpleTestCase):
    def test_in_stock_to_out_of_stock_is_critical(self):
        changes = only(
            state(availability="in_stock"), state(availability="out_of_stock"), "availability"
        )
        self.assertEqual(changes[0]["severity"], CRITICAL)
        self.assertIn("out of stock", changes[0]["basis"])

    def test_in_stock_to_low_stock_is_important(self):
        changes = only(
            state(availability="in_stock"), state(availability="low_stock"), "availability"
        )
        self.assertEqual(changes[0]["severity"], IMPORTANT)

    def test_recovery_is_informational(self):
        changes = only(
            state(availability="low_stock"), state(availability="in_stock"), "availability"
        )
        self.assertEqual(changes[0]["severity"], INFORMATIONAL)

    def test_summary_line_is_readable(self):
        changes = only(
            state(availability="in_stock"), state(availability="out_of_stock"), "availability"
        )
        self.assertEqual(
            format_change_line(changes[0]),
            "Availability: in stock → out of stock",
        )


class CollectionDiffTests(SimpleTestCase):
    def test_variants_added(self):
        changes = only(
            state(variants=["S", "M"]),
            state(variants=["S", "M", "L"]),
            "variants",
        )
        self.assertEqual(changes[0]["severity"], MINOR)
        self.assertIn("1 new variant", changes[0]["basis"])

    def test_variants_removed_is_important(self):
        changes = only(
            state(variants=["S", "M", "L"]),
            state(variants=["S"]),
            "variants",
        )
        self.assertEqual(changes[0]["severity"], IMPORTANT)
        self.assertIn("no longer listed", changes[0]["basis"])

    def test_variant_order_is_not_a_change(self):
        self.assertEqual(
            only(state(variants=["S", "M"]), state(variants=["M", "S"]), "variants"), []
        )

    def test_badges_added(self):
        changes = only(state(badges=["New"]), state(badges=["New", "Sale"]), "badges")
        self.assertIn("added sale", changes[0]["basis"].lower())

    def test_specs_added_and_removed(self):
        changes = only(
            state(specs={"Warranty": "2 years"}),
            state(specs={"Battery": "3000 mAh"}),
            "specs",
        )
        self.assertIn("added", changes[0]["basis"])
        self.assertIn("removed", changes[0]["basis"])

    def test_review_count_drop_is_important(self):
        changes = only(state(review_count="128"), state(review_count="100"), "review_count")
        self.assertEqual(changes[0]["severity"], IMPORTANT)
        self.assertIn("fell", changes[0]["basis"])

    def test_review_count_growth_is_informational(self):
        changes = only(state(review_count="100"), state(review_count="140"), "review_count")
        self.assertEqual(changes[0]["severity"], INFORMATIONAL)


class OrderingTests(SimpleTestCase):
    def test_most_severe_change_sorts_first(self):
        changes = diff_snapshots(
            state(price="100.00", availability="in_stock", name="Old name"),
            state(price="60.00", availability="out_of_stock", name="New name"),
            source_url="https://x.example/p",
        )
        self.assertEqual(changes[0]["field"], "availability")
        self.assertEqual(severity_of(changes), CRITICAL)

    def test_every_change_records_source_and_rule(self):
        changes = diff_snapshots(
            state(price="100.00"), state(price="60.00"), source_url="https://x.example/p"
        )
        for change in changes:
            self.assertEqual(change["source_url"], "https://x.example/p")
            self.assertTrue(change["rule"].startswith("rule:"))
            self.assertTrue(change["basis"])

    def test_detected_at_is_carried(self):
        changes = diff_snapshots(
            state(price="100.00"),
            state(price="60.00"),
            detected_at="2026-09-26T10:00:00+00:00",
        )
        self.assertEqual(changes[0]["detected_at"], "2026-09-26T10:00:00+00:00")


class ExplanationTests(SimpleTestCase):
    def build(self):
        return diff_snapshots(
            state(price="129.00", availability="in_stock"),
            state(price="99.00", availability="low_stock"),
            source_url="https://x.example/p",
            detected_at="2026-09-26T10:00:00+00:00",
        )

    def test_explanation_has_every_required_block(self):
        explanation = explain(self.build(), product_name="Acme Pro Widget")
        for key in ("what_changed", "why_it_may_matter", "what_to_check", "confidence", "basis", "evidence"):
            self.assertIn(key, explanation)
            self.assertTrue(explanation[key], f"{key} is empty")

    def test_explanation_names_the_product_and_the_numbers(self):
        explanation = explain(self.build(), product_name="Acme Pro Widget")
        self.assertIn("Acme Pro Widget", explanation["what_changed"])
        self.assertIn("99.00", explanation["what_changed"])
        self.assertIn("129.00", explanation["what_changed"])

    def test_explanation_preserves_evidence(self):
        explanation = explain(self.build(), product_name="Acme Pro Widget")
        self.assertEqual(len(explanation["evidence"]), 2)
        for entry in explanation["evidence"]:
            self.assertEqual(entry["source_url"], "https://x.example/p")
            self.assertIn("before", entry)
            self.assertIn("after", entry)
            self.assertIn("rule", entry)

    def test_why_it_matters_does_not_prescribe_a_business_decision(self):
        explanation = explain(self.build(), product_name="Acme Pro Widget")
        for forbidden in ("you should", "we recommend", "you must", "guaranteed"):
            self.assertNotIn(forbidden, explanation["why_it_may_matter"].lower())
            self.assertNotIn(forbidden, explanation["what_to_check"].lower())

    def test_no_changes_yields_an_explicit_no_op(self):
        explanation = explain([], product_name="Acme Pro Widget")
        self.assertIn("No product fields changed", explanation["what_changed"])
        # "Nothing changed" is itself a single-extraction observation, so it
        # is never reported as high confidence.
        self.assertEqual(explanation["confidence"], "medium")

    def test_confidence_follows_the_extraction_path(self):
        self.assertEqual(confidence_for(self.build()), "high")
        heuristic = [
            {
                "field": "price",
                "label": "Price",
                "before": "1",
                "after": "2",
                "severity": MINOR,
                "category": "pricing",
                "rule": "rule:price",
                "basis": "x",
                "methods": {"after": "heuristic"},
            }
        ]
        self.assertEqual(confidence_for(heuristic), "low")


class SummaryTests(SimpleTestCase):
    def test_summary_reports_currency_for_prices(self):
        changes = only(state(price="129.00"), state(price="99.00"), "price")
        self.assertEqual(
            format_change_line(changes[0], currency="EUR"), "Price: EUR 129.00 → EUR 99.00"
        )

    def test_summary_caps_the_lines_and_says_how_many_were_left(self):
        changes = diff_snapshots(
            state(price="100.00", name="A", brand="B", sku="C", condition="New"),
            state(price="90.00", name="A2", brand="B2", sku="C2", condition="Refurbished"),
        )
        text = summarize(changes, currency="EUR", limit=2)
        lines = text.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertIn("more field(s) changed", lines[-1])

    def test_discount_percent(self):
        self.assertEqual(
            discount_percent("129.00", "99.00"), (Decimal("30") / Decimal("129")) * Decimal("100")
        )
        self.assertIsNone(discount_percent(None, "99.00"))
        self.assertIsNone(discount_percent("99.00", "129.00"))
        self.assertIsNone(discount_percent("0", "0"))
