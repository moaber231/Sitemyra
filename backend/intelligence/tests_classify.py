"""Classification and target-discovery tests.

Pins two properties that matter more than coverage: classification always
carries a factual rationale, and discovery never proposes a page outside
the submitted origin or inside a cart/account/legal path.
"""

from django.test import SimpleTestCase

from intelligence.services.classify import (
    CAREERS,
    CHANGELOG,
    FAQ,
    HOMEPAGE,
    PRICING,
    PRODUCT,
    PROMOTIONS,
    classify_page,
    discover_targets,
)
from intelligence.services.page_facts import extract_page_facts
from intelligence.services.urls import (
    is_excluded_path,
    normalize_url,
    registrable_domain,
    same_origin,
    same_site,
)


def facts_for(body: str, url: str, head: str = "") -> dict:
    content = (
        "<!doctype html><html><head>" + head + "</head><body>" + body + "</body></html>"
    ).encode("utf-8")
    return extract_page_facts(content, "text/html", url)


class UrlHelperTests(SimpleTestCase):
    def test_normalize_accepts_a_bare_hostname(self):
        self.assertEqual(normalize_url("competitor.com"), "https://competitor.com/")
        self.assertEqual(normalize_url("  https://Competitor.com/Path  "), "https://competitor.com/Path")

    def test_normalize_drops_fragment_and_default_port(self):
        self.assertEqual(normalize_url("https://a.example/p#top"), "https://a.example/p")
        self.assertEqual(normalize_url("https://a.example:443/p"), "https://a.example/p")
        self.assertEqual(normalize_url("http://a.example:80/p"), "http://a.example/p")

    def test_normalize_keeps_a_non_default_port_and_query(self):
        # Non-http(s) schemes and unsupported ports are rejected by the
        # fetcher's own validator; normalization must not silently drop them.
        self.assertEqual(normalize_url("https://a.example:8443/p?x=1"), "https://a.example:8443/p?x=1")

    def test_normalize_rejects_unsupported_scheme(self):
        self.assertEqual(normalize_url("ftp://a.example"), "")
        self.assertEqual(normalize_url("javascript:alert(1)"), "")

    def test_registrable_domain_handles_multi_part_suffixes(self):
        self.assertEqual(registrable_domain("https://shop.example.co.uk/p"), "example.co.uk")
        self.assertEqual(registrable_domain("example.com"), "example.com")
        self.assertEqual(registrable_domain("http://127.0.0.1:8000/"), "")

    def test_same_site_counts_subdomains(self):
        self.assertTrue(same_site("https://a.example.com/x", "https://www.example.com/y"))
        self.assertFalse(same_site("https://example.com", "https://example.org"))

    def test_same_origin_is_strict(self):
        self.assertTrue(same_origin("https://a.example.com/x", "https://a.example.com/y"))
        self.assertFalse(same_origin("https://a.example.com", "http://a.example.com"))
        self.assertFalse(same_origin("https://a.example.com", "https://b.example.com"))

    def test_excluded_paths(self):
        self.assertTrue(is_excluded_path("https://a.example/cart"))
        self.assertTrue(is_excluded_path("https://a.example/account/login"))
        self.assertTrue(is_excluded_path("https://a.example/p?cart=1"))
        self.assertFalse(is_excluded_path("https://a.example/products/x"))


class ClassificationTests(SimpleTestCase):
    def assert_rationale_is_factual(self, kind, confidence, rationale):
        self.assertIn(kind, {
            PRODUCT, PRICING, "features", "variants", "reviews", FAQ,
            "docs", CHANGELOG, "blog", CAREERS, PROMOTIONS, HOMEPAGE,
            "legal", "support", "other",
        })
        self.assertIn(confidence, {"high", "medium", "low"})
        self.assertTrue(rationale, "every classification must explain itself")
        self.assertLess(len(rationale), 600)

    def test_product_url_with_structured_data(self):
        url = "https://shop.example.com/products/pro-x"
        facts = facts_for("", url, head='<script type="application/ld+json">{"@type":"Product","name":"X"}</script>')
        kind, confidence, rationale = classify_page(url, facts)
        self.assertEqual(kind, PRODUCT)
        self.assertEqual(confidence, "high")
        self.assertIn("schema.org", rationale)
        self.assertIn("product", rationale.lower())

    def test_pricing_path(self):
        url = "https://example.com/pricing"
        kind, confidence, rationale = classify_page(url, {})
        self.assertEqual(kind, PRICING)
        self.assert_rationale_is_factual(kind, confidence, rationale)

    def test_changelog_path(self):
        kind, _c, rationale = classify_page("https://example.com/changelog", {})
        self.assertEqual(kind, CHANGELOG)
        self.assertIn("changelog", rationale.lower())

    def test_careers_path(self):
        kind, _c, _r = classify_page("https://example.com/careers", {})
        self.assertEqual(kind, CAREERS)

    def test_homepage(self):
        kind, confidence, rationale = classify_page("https://example.com/", {})
        self.assertEqual(kind, HOMEPAGE)
        self.assertEqual(confidence, "high")
        self.assert_rationale_is_factual(kind, confidence, rationale)

    def test_a_price_on_a_features_page_reads_as_pricing(self):
        url = "https://example.com/features"
        facts = facts_for("", url, head='<script type="application/ld+json">{"@type":"Product","offers":{"price":"10.00"}}</script>')
        kind, _c, _r = classify_page(url, facts)
        self.assertEqual(kind, PRICING)

    def test_a_heuristic_detection_is_never_described_as_structured(self):
        # Trust rule: the rationale must quote the signals the extractor
        # actually recorded, not a stronger claim.
        url = "https://shop.example/thing_1"
        facts = facts_for(
            '<h1>Widget</h1><p class="price_color">$19.99</p>'
            '<p class="instock availability">In stock</p>',
            url,
        )
        kind, confidence, rationale = classify_page(url, facts)
        self.assertEqual(kind, PRODUCT)
        self.assertEqual(confidence, "medium")
        self.assertNotIn("structured data", rationale.lower())
        self.assertIn("availability", rationale.lower())

    def test_structured_detection_says_so(self):
        url = "https://shop.example/p/x"
        facts = facts_for(
            "",
            url,
            head='<script type="application/ld+json">{"@type":"Product","name":"X"}</script>',
        )
        _kind, _confidence, rationale = classify_page(url, facts)
        self.assertIn("structured data", rationale.lower())

    def test_unknown_page_classifies_as_other_and_says_so(self):
        kind, confidence, rationale = classify_page("https://example.com/x/y/z", {})
        self.assertEqual(kind, "other")
        self.assertEqual(confidence, "low")
        self.assertIn("could not classify", rationale.lower())

    def test_token_matching_never_fires_on_a_substring(self):
        # Regression: "post" (blog) must not match inside "/support", and
        # "plan" (pricing) must not match inside "/planted".
        self.assertEqual(classify_page("https://example.com/support", {})[0], "support")
        self.assertEqual(classify_page("https://example.com/blog/post-1", {})[0], "blog")
        self.assertEqual(classify_page("https://example.com/planted-trees", {})[0], "other")

    def test_hyphenated_paths_are_split_into_tokens(self):
        self.assertEqual(classify_page("https://example.com/release-notes", {})[0], CHANGELOG)
        self.assertEqual(classify_page("https://example.com/plans-and-rates", {})[0], PRICING)
        self.assertEqual(classify_page("https://example.com/open-positions", {})[0], CAREERS)


class DiscoveryTests(SimpleTestCase):
    body = (
        '<a href="/pricing">Pricing</a>'
        '<a href="/changelog">Changelog</a>'
        '<a href="/blog/hello">Blog</a>'
        '<a href="/cart">Cart</a>'
        '<a href="/account/login">Login</a>'
        '<a href="/privacy">Privacy</a>'
        '<a href="https://other.example/pricing">Competitor pricing</a>'
        '<a href="https://facebook.com/acme">Social</a>'
        '<a href="mailto:hi@example.com">Mail</a>'
        '<a href="/products/pro-y">Pro Y</a>'
        '<a href="/pricing#plans">Pricing anchor</a>'
    )

    def targets(self, url="https://example.com/products/pro-x"):
        return discover_targets(url, self.body.encode("utf-8"), "text/html", {})

    def kinds(self):
        return {target["kind"] for target in self.targets()}

    def test_finds_the_expected_pages(self):
        self.assertIn(PRICING, self.kinds())
        self.assertIn(CHANGELOG, self.kinds())
        self.assertIn("blog", self.kinds())

    def test_never_proposes_cart_login_or_legal(self):
        for target in self.targets():
            self.assertNotIn("/cart", target["url"])
            self.assertNotIn("/account", target["url"])
            self.assertNotIn("/privacy", target["url"])

    def test_never_leaves_the_origin(self):
        for target in self.targets():
            self.assertTrue(same_origin("https://example.com/", target["url"]), target["url"])

    def test_deduplicates_anchors_and_fragments(self):
        urls = [target["url"] for target in self.targets()]
        self.assertEqual(len(urls), len(set(urls)))

    def test_pricing_outranks_blog(self):
        ordered = sorted(self.targets(), key=lambda item: -item["relevance"])
        kinds = [target["kind"] for target in ordered]
        self.assertLess(kinds.index(PRICING), kinds.index("blog"))

    def test_every_target_explains_itself(self):
        for target in self.targets():
            self.assertTrue(target["why"], target["url"])
            self.assertLess(len(target["why"]), 500)

    def test_link_text_is_used_when_the_path_is_unhelpful(self):
        targets = discover_targets(
            "https://example.com/",
            b'<a href="/x/y">See our prices</a>',
            "text/html",
            {},
        )
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]["kind"], PRICING)
        self.assertIn("See our prices", targets[0]["why"])

    def test_a_helpful_path_beats_link_text(self):
        targets = discover_targets(
            "https://example.com/",
            b'<a href="/plans-and-rates">See our prices</a>',
            "text/html",
            {},
        )
        self.assertEqual(targets[0]["kind"], PRICING)
        self.assertIn("/plans-and-rates", targets[0]["why"])

    def test_respects_the_limit(self):
        body = "".join(f'<a href="/page-{index}">Page {index}</a>' for index in range(80))
        targets = discover_targets("https://example.com/", body.encode("utf-8"), "text/html", {})
        self.assertLessEqual(len(targets), 20)

    def test_no_content_returns_nothing(self):
        self.assertEqual(discover_targets("https://example.com/", None), [])
