"""Extraction tests — the evidence contract.

These are the most important tests in Phase 1: they pin down that
Sitemyra reports what the page actually says, records how it read it, and
stays silent when a page says nothing.
"""

from decimal import Decimal

from django.test import SimpleTestCase

from intelligence.services.page_facts import (
    extract_page_facts,
    normalize_availability,
    parse_money,
    summarize_facts,
)


def page(body: str, head: str = "", lang: str = "en") -> bytes:
    return (
        "<!doctype html><html lang=\"{lang}\"><head>{head}</head>"
        "<body>{body}</body></html>"
    ).format(lang=lang, head=head, body=body).encode("utf-8")


def jsonld(payload) -> str:
    import json

    return (
        '<script type="application/ld+json">'
        + json.dumps(payload)
        + "</script>"
    )


class ParseMoneyTests(SimpleTestCase):
    def test_symbols_map_to_iso_codes(self):
        self.assertEqual(parse_money("€129.00"), (Decimal("129.00"), "EUR"))
        self.assertEqual(parse_money("$49"), (Decimal("49"), "USD"))
        self.assertEqual(parse_money("£19.99"), (Decimal("19.99"), "GBP"))

    def test_code_before_or_after_amount(self):
        self.assertEqual(parse_money("USD 19.99"), (Decimal("19.99"), "USD"))
        self.assertEqual(parse_money("19.99 USD"), (Decimal("19.99"), "USD"))

    def test_european_decimal_comma(self):
        self.assertEqual(parse_money("1.299,99"), (Decimal("1299.99"), None))
        self.assertEqual(parse_money("49,90"), (Decimal("49.90"), None))

    def test_us_thousands_separator(self):
        self.assertEqual(parse_money("$1,299.99"), (Decimal("1299.99"), "USD"))
        # A single separator followed by exactly three digits is thousands.
        self.assertEqual(parse_money("1.299")[0], Decimal("1299"))

    def test_unparseable_returns_none_not_exception(self):
        self.assertEqual(parse_money("free"), (None, None))
        self.assertEqual(parse_money(""), (None, None))
        self.assertEqual(parse_money(None), (None, None))

    def test_currency_only_keeps_the_code(self):
        self.assertEqual(parse_money("Contact us")[1], None)


class AvailabilityTests(SimpleTestCase):
    def test_schema_urls(self):
        self.assertEqual(
            normalize_availability("https://schema.org/InStock"), "in_stock"
        )
        self.assertEqual(
            normalize_availability("https://schema.org/OutOfStock"),
            "out_of_stock",
        )
        self.assertEqual(
            normalize_availability("https://schema.org/Discontinued"),
            "discontinued",
        )

    def test_human_text(self):
        self.assertEqual(normalize_availability("Only 3 left in stock"), "low_stock")
        self.assertEqual(normalize_availability("Currently unavailable"), "out_of_stock")
        self.assertEqual(normalize_availability("Add to cart"), "in_stock")

    def test_absence_is_unknown_not_in_stock(self):
        # The single most important property here: we never invent stock.
        self.assertEqual(normalize_availability(""), "unknown")
        self.assertEqual(normalize_availability("Some text"), "unknown")


class JsonLdExtractionTests(SimpleTestCase):
    payload = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Acme Pro Widget",
        "description": "A widget for professionals.",
        "sku": "APW-2000",
        "brand": {"@type": "Brand", "name": "Acme"},
        "image": ["https://cdn.example.com/apw.jpg"],
        "offers": {
            "@type": "Offer",
            "price": "99.00",
            "priceCurrency": "EUR",
            "availability": "https://schema.org/InStock",
        },
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": "4.6",
            "reviewCount": "128",
        },
        "additionalProperty": [
            {"@type": "PropertyValue", "name": "Warranty", "value": "2 years"},
            {"@type": "PropertyValue", "name": "Weight", "value": "1.2 kg"},
        ],
    }

    def test_reads_every_documented_field(self):
        content = page("", head=jsonld(self.payload) + "<title>Buy</title>")
        facts = extract_page_facts(content, "text/html", "https://shop.example.com/p/apw")

        self.assertTrue(facts["product_detected"])
        self.assertEqual(facts["name"]["value"], "Acme Pro Widget")
        self.assertEqual(facts["sku"]["value"], "APW-2000")
        self.assertEqual(facts["brand"]["value"], "Acme")
        self.assertEqual(facts["price"]["value"], "99.00")
        self.assertEqual(facts["currency"]["value"], "EUR")
        self.assertEqual(facts["availability"]["value"], "in_stock")
        self.assertEqual(facts["rating"]["value"], "4.60")
        self.assertEqual(facts["review_count"]["value"], 128)
        self.assertEqual(facts["specs"]["value"]["Warranty"], "2 years")
        self.assertEqual(facts["images"]["value"], ["https://cdn.example.com/apw.jpg"])

    def test_every_value_carries_method_and_raw_evidence(self):
        facts = extract_page_facts(page("", head=jsonld(self.payload)))
        for field in ("name", "price", "availability", "rating"):
            entry = facts[field]
            self.assertIn(entry["method"], {"jsonld", "microdata", "opengraph", "heuristic", "html"})
            self.assertTrue(entry["raw"], f"{field} has no raw evidence")

    def test_graph_wrapper(self):
        content = page(
            "",
            head=jsonld({"@context": "https://schema.org", "@graph": [self.payload]}),
        )
        facts = extract_page_facts(content)
        self.assertEqual(facts["name"]["value"], "Acme Pro Widget")

    def test_malformed_block_does_not_discard_valid_one(self):
        broken = '<script type="application/ld+json">{ not json </script>'
        content = page("", head=broken + jsonld(self.payload))
        facts = extract_page_facts(content)
        self.assertEqual(facts["name"]["value"], "Acme Pro Widget")

    def test_aggregate_offer_low_price(self):
        content = page(
            "",
            head=jsonld(
                {
                    "@type": "Product",
                    "name": "Bundle",
                    "offers": {
                        "@type": "AggregateOffer",
                        "lowPrice": "49.00",
                        "priceCurrency": "GBP",
                    },
                }
            ),
        )
        facts = extract_page_facts(content)
        self.assertEqual(facts["price"]["value"], "49.00")
        self.assertEqual(facts["currency"]["value"], "GBP")

    def test_variants_from_has_variant(self):
        content = page(
            "",
            head=jsonld(
                {
                    "@type": "Product",
                    "name": "Shirt",
                    "hasVariant": [
                        {"@type": "Product", "name": "Small", "offers": {"price": "10.00"}},
                        {"@type": "Product", "name": "Large", "offers": {"price": "12.00"}},
                    ],
                }
            ),
        )
        facts = extract_page_facts(content)
        labels = [item["label"] for item in facts["variants"]["value"]]
        self.assertEqual(labels, ["Small", "Large"])

    def test_shipping_details(self):
        content = page(
            "",
            head=jsonld(
                {
                    "@type": "Product",
                    "name": "Widget",
                    "offers": {
                        "@type": "Offer",
                        "price": "10.00",
                        "shippingDetails": {
                            "@type": "OfferShippingDetails",
                            "shippingRate": {"value": "4.50", "unitText": "EUR"},
                        },
                    },
                }
            ),
        )
        facts = extract_page_facts(content)
        self.assertEqual(facts["shipping"]["value"]["cost"], "4.50")


class MicrodataTests(SimpleTestCase):
    body = (
        '<div itemscope itemtype="https://schema.org/Product">'
        '<h1 itemprop="name">Micro Widget</h1>'
        '<span itemprop="price" content="19.99"></span>'
        '<meta itemprop="priceCurrency" content="USD">'
        '<link itemprop="availability" href="https://schema.org/InStock">'
        '<span itemprop="aggregateRating" itemscope>'
        '<meta itemprop="ratingValue" content="4.1">'
        '<meta itemprop="reviewCount" content="7">'
        "</span></div>"
    )

    def test_microdata_is_read(self):
        facts = extract_page_facts(page(self.body), "text/html", "https://x.example/p")
        self.assertEqual(facts["name"]["value"], "Micro Widget")
        self.assertEqual(facts["name"]["method"], "microdata")
        self.assertEqual(facts["price"]["value"], "19.99")
        self.assertEqual(facts["availability"]["value"], "in_stock")
        self.assertEqual(facts["review_count"]["value"], 7)
        self.assertTrue(facts["product_detected"])


class OpenGraphTests(SimpleTestCase):
    def test_opengraph_product_fields(self):
        head = (
            '<meta property="og:title" content="OG Widget">'
            '<meta property="og:description" content="A description.">'
            '<meta property="og:site_name" content="OG Shop">'
            '<meta property="product:price:amount" content="29.00">'
            '<meta property="product:price:currency" content="GBP">'
            '<meta property="product:availability" content="in stock">'
        )
        facts = extract_page_facts(page("", head=head))
        self.assertEqual(facts["page_title"]["value"], "OG Widget")
        self.assertEqual(facts["price"]["value"], "29.00")
        self.assertEqual(facts["currency"]["value"], "GBP")
        self.assertEqual(facts["availability"]["value"], "in_stock")
        self.assertTrue(facts["product_detected"])


class HeuristicTests(SimpleTestCase):
    def test_class_based_price(self):
        body = '<div class="product-price">€ 129,00</div><button>Add to cart</button>'
        facts = extract_page_facts(page(body), "text/html", "https://x.example/p")
        self.assertEqual(facts["price"]["value"], "129.00")
        self.assertEqual(facts["price"]["method"], "heuristic")

    def test_was_and_now_price_pair(self):
        body = (
            '<span class="price--old">€149.00</span>'
            '<span class="price--current">€99.00</span>'
        )
        facts = extract_page_facts(page(body), "text/html", "https://x.example/p")
        self.assertEqual(facts["price"]["value"], "99.00")
        self.assertEqual(facts["list_price"]["value"], "149.00")

    def test_data_price_attribute(self):
        body = '<span data-price="59.90" class="js-price">now</span>'
        facts = extract_page_facts(page(body), "text/html", "https://x.example/p")
        self.assertEqual(facts["price"]["value"], "59.90")

    def test_badges_only_from_promotional_words(self):
        body = (
            '<span class="badge">New arrival</span>'
            '<span class="badge">Free shipping</span>'
            '<span class="badge">Lorem ipsum dolor sit amet consectetur</span>'
        )
        facts = extract_page_facts(page(body), "text/html", "https://x.example/p")
        badges = facts["badges"]["value"]
        self.assertIn("New arrival", badges)
        self.assertIn("Free shipping", badges)
        self.assertEqual(len(badges), 2)

    def test_variant_options_from_a_product_select(self):
        body = (
            '<select class="product-variant-size" name="size">'
            "<option>S</option><option>M</option><option>L</option>"
            "</select>"
        )
        facts = extract_page_facts(page(body), "text/html", "https://x.example/p")
        labels = [item["label"] for item in facts["variants"]["value"]]
        self.assertEqual(labels, ["S", "M", "L"])

    def test_shipping_note(self):
        body = "<p>Free shipping on all orders over 50</p>"
        facts = extract_page_facts(page(body), "text/html", "https://x.example/p")
        self.assertIn("Free shipping", facts["shipping"]["value"]["note"])


class PlainHtmlProductPageTests(SimpleTestCase):
    """Storefronts with no structured data at all.

    This is the common real-world case for a small online shop, and it is
    the case Phase 1 has to get right, because a competitor product page
    that yields no price is a product page we cannot watch.
    """

    body = (
        '<ul class="breadcrumb"><li><a href="/">Home</a></li>'
        '<li><a href="/catalogue/books_1/index.html">Books</a></li></ul>'
        '<h1>A Light in the Attic</h1>'
        '<p class="price_color">\u00a351.77</p>'
        '<p class="instock availability"><i class="icon-ok"></i> In stock</p>'
        '<p class="star-rating">Three stars</p>'
        '<p>Hardback</p>'
        '<ul><li><a href="/catalogue/books_1/index.html">Books</a></li></ul>'
    )

    def test_price_availability_and_product_detection(self):
        facts = extract_page_facts(
            page(self.body), "text/html", "https://shop.example/catalogue/x_1/index.html"
        )
        self.assertEqual(facts["price"]["value"], "51.77")
        self.assertEqual(facts["currency"]["value"], "GBP")
        self.assertEqual(facts["availability"]["value"], "in_stock")
        self.assertTrue(facts["product_detected"])

    def test_out_of_stock_is_read(self):
        body = self.body.replace("In stock", "Currently unavailable")
        facts = extract_page_facts(page(body), "text/html", "https://shop.example/p")
        self.assertEqual(facts["availability"]["value"], "out_of_stock")

    def test_a_was_price_is_not_mistaken_for_the_current_price(self):
        body = (
            '<span class="price--old">\u20ac149.00</span>'
            '<span class="price--current">\u20ac99.00</span>'
            '<p class="availability">In stock</p>'
        )
        facts = extract_page_facts(page(body), "text/html", "https://shop.example/p")
        self.assertEqual(facts["price"]["value"], "99.00")
        self.assertEqual(facts["list_price"]["value"], "149.00")

    def test_a_price_mention_inside_a_review_is_not_a_product(self):
        # "It cost \u20ac49 and the seller said in stock" in a <p> with no
        # price/stock class must not make an article a product page.
        body = (
            "<h1>My review of five books</h1>"
            "<p>One of them cost \u20ac49 and the seller said in stock. Great read.</p>"
        )
        facts = extract_page_facts(page(body), "text/html", "https://blog.example/review")
        self.assertNotIn("price", facts)
        self.assertFalse(facts["product_detected"])

    def test_data_price_attribute_wins_over_rendered_text(self):
        body = (
            '<span class="price">from \u20ac199</span>'
            '<span class="js-price" data-price="99.50"></span>'
        )
        facts = extract_page_facts(page(body), "text/html", "https://shop.example/p")
        self.assertEqual(facts["price"]["value"], "99.50")
        self.assertEqual(facts["price"]["method"], "attribute")

    def test_was_price_spelled_as_two_class_words(self):
        # class="old price" must not be read as the current price.
        body = (
            '<span class="old price">\u20ac149.00</span>'
            '<span class="current price">\u20ac99.00</span>'
        )
        facts = extract_page_facts(page(body), "text/html", "https://shop.example/p")
        self.assertEqual(facts["price"]["value"], "99.00")
        self.assertEqual(facts["list_price"]["value"], "149.00")

    def test_priceless_class_does_not_produce_a_price(self):
        body = '<span class="priceless">Priceless</span>'
        facts = extract_page_facts(page(body), "text/html", "https://x.example/p")
        self.assertNotIn("price", facts)


class SilenceTests(SimpleTestCase):
    """A page with nothing to say must produce nothing — no invented data."""

    body = "<h1>About us</h1><p>We sell things since 1999.</p>"

    def test_no_price_no_availability_no_product(self):
        facts = extract_page_facts(page(self.body), "text/html", "https://x.example/about")
        self.assertNotIn("price", facts)
        self.assertNotIn("availability", facts)
        self.assertNotIn("rating", facts)
        self.assertNotIn("variants", facts)
        self.assertFalse(facts["product_detected"])

    def test_title_is_still_captured(self):
        content = page(self.body, head="<title>About us</title>")
        facts = extract_page_facts(content, "text/html", "https://x.example/about")
        self.assertEqual(facts["page_title"]["value"], "About us")

    def test_empty_and_binary_input_does_not_raise(self):
        self.assertIsInstance(extract_page_facts(b""), dict)
        self.assertIsInstance(extract_page_facts(None), dict)
        self.assertIsInstance(extract_page_facts(b"\xff\xfe\x00binary"), dict)

    def test_summarize_returns_values_only(self):
        facts = extract_page_facts(page("", head=jsonld(JsonLdExtractionTests.payload)))
        summary = summarize_facts(facts)
        self.assertEqual(summary["name"], "Acme Pro Widget")
        self.assertNotIn("method", summary)
