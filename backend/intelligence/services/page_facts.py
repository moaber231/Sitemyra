"""Structured product extraction from a public HTML page.

**Pure module.** Takes bytes and returns plain JSON-serialisable data.
It performs no network access, touches no database, and imports nothing
from ``monitors`` so it can be unit-tested in isolation.

Design rules (trust / evidence):

* Every extracted value is returned as ``{"value": ..., "method": ...,
  "raw": ...}``. ``method`` names where the value came from
  (``jsonld`` / ``microdata`` / ``opengraph`` / ``attribute`` /
  ``heuristic``) and ``raw`` is the exact text that produced it. Nothing
  is ever asserted without a traceable source.
* When a page carries no usable signal the field is simply absent. We
  never guess a price, an availability state, or a product name.
* Money is parsed with an explicit, documented separator rule and the
  raw string is preserved so a mis-parse is always visible to the user.
"""

import json
import re
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup

# --------------------------------------------------------------------------
# Money + currency
# --------------------------------------------------------------------------

# Symbol -> ISO 4217. Ordered longest-first where prefixes overlap
# (CA$ before $, US$ before $, etc.) so the specific one wins.
CURRENCY_SYMBOLS = (
    ("CA$", "CAD"),
    ("C$", "CAD"),
    ("AU$", "AUD"),
    ("A$", "AUD"),
    ("NZ$", "NZD"),
    ("HK$", "HKD"),
    ("SG$", "SGD"),
    ("MX$", "MXN"),
    ("US$", "USD"),
    ("R$", "BRL"),
    ("CA$", "CAD"),
    ("€", "EUR"),
    ("£", "GBP"),
    ("¥", "JPY"),
    ("₹", "INR"),
    ("₽", "RUB"),
    ("₺", "TRY"),
    ("₩", "KRW"),
    ("₪", "ILS"),
    ("₫", "VND"),
    ("฿", "THB"),
    ("zł", "PLN"),
    ("Kč", "CZK"),
    ("CHF", "CHF"),
    ("kr", "SEK"),
    ("$", "USD"),
)

CURRENCY_CODES = frozenset(
    {
        "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "SEK",
        "NOK", "DKK", "PLN", "CZK", "HUF", "RON", "TRY", "RUB", "UAH",
        "INR", "PKR", "BDT", "LKR", "IDR", "MYR", "SGD", "HKD", "THB",
        "VND", "PHP", "CNY", "KRW", "ILS", "AED", "SAR", "ZAR", "NGN",
        "KES", "EGP", "BRL", "MXN", "ARS", "CLP", "COP", "PEN",
    }
)

# A number with an optional thousands/decimal separator. We deliberately do
# not accept a bare "." or "," group inside the middle of a token so that
# version strings ("v1.2.3") and dates do not become prices.
_MONEY_RE = re.compile(
    r"(?P<amount>\d{1,3}(?:[.,  \s]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)"
)
_CODE_RE = re.compile(r"\b([A-Z]{3})\b")


def _strip_thousands(text: str) -> str:
    return re.sub(r"[  \s]", "", text)


def parse_money(raw):
    """Parse a money string into ``(Decimal|None, currency_or_None)``.

    Separator rule, applied in order:

    1. Both ``.`` and ``,`` present -> the *right-most* one is the decimal
       separator, the other is a thousands separator.
    2. One separator followed by exactly three digits -> thousands.
    3. One separator followed by one or two digits -> decimal.
    4. No separator -> integer.

    Returns ``(None, None)`` rather than raising so a malformed price
    degrades to "not detected".
    """
    if raw is None:
        return (None, None)
    text = str(raw).strip()
    if not text:
        return (None, None)

    currency = None
    upper = text.upper()
    code_match = _CODE_RE.search(upper)
    if code_match and code_match.group(1) in CURRENCY_CODES:
        currency = code_match.group(1)
    for symbol, iso in CURRENCY_SYMBOLS:
        if symbol in text:
            currency = currency or iso
            break

    match = _MONEY_RE.search(_strip_thousands(text).replace(" ", " "))
    if not match:
        return (None, currency)
    amount = match.group("amount")
    if "," in amount and "." in amount:
        if amount.rfind(",") > amount.rfind("."):
            amount = amount.replace(".", "").replace(",", ".")
        else:
            amount = amount.replace(",", "")
    elif "," in amount:
        head, _, tail = amount.rpartition(",")
        if len(tail) == 3 and len(head) <= 3:
            amount = amount.replace(",", "")
        else:
            amount = amount.replace(",", ".")
    elif "." in amount:
        head, _, tail = amount.rpartition(".")
        if len(tail) == 3 and len(head) <= 3:
            amount = amount.replace(".", "")
    try:
        return (Decimal(amount), currency)
    except (InvalidOperation, ValueError):
        return (None, currency)


def _money_text(value) -> str:
    """Render money/rating with exactly two decimals.

    Quantizing (rather than ``normalize()``) matters: a price of
    ``99.00`` must never be stored or displayed as ``99``, and it must
    compare equal to the same price seen through a different extraction
    path. Two decimals covers every currency we read and matches the
    ``Decimal(12, 2)`` / ``Decimal(4, 2)`` snapshot columns.
    """
    if value is None:
        return ""
    try:
        return format(Decimal(str(value)).quantize(Decimal("0.01")), "f")
    except (InvalidOperation, ValueError, TypeError):
        return str(value)


# --------------------------------------------------------------------------
# Availability
# --------------------------------------------------------------------------

AVAILABILITY_STATES = (
    "in_stock",
    "low_stock",
    "out_of_stock",
    "backorder",
    "preorder",
    "discontinued",
    "unknown",
)

_AVAILABILITY_URL_MAP = (
    ("outofstock", "out_of_stock"),
    ("out_of_stock", "out_of_stock"),
    ("soldout", "out_of_stock"),
    ("sold_out", "out_of_stock"),
    ("discontinued", "discontinued"),
    ("preorder", "preorder"),
    ("pre-order", "preorder"),
    ("backorder", "backorder"),
    ("back-order", "backorder"),
    ("presale", "preorder"),
    ("instock", "in_stock"),
    ("in_stock", "in_stock"),
    ("limitedavailability", "low_stock"),
    ("limited_availability", "low_stock"),
    ("lowstock", "low_stock"),
    ("low_stock", "low_stock"),
    ("onlineonly", "in_stock"),
    ("available", "in_stock"),
)

_AVAILABILITY_TEXT_MAP = (
    ("out of stock", "out_of_stock"),
    ("outofstock", "out_of_stock"),
    ("sold out", "out_of_stock"),
    ("soldout", "out_of_stock"),
    ("currently unavailable", "out_of_stock"),
    ("unavailable", "out_of_stock"),
    ("no longer available", "discontinued"),
    ("discontinued", "discontinued"),
    ("backorder", "backorder"),
    ("back order", "backorder"),
    ("pre-order", "preorder"),
    ("preorder", "preorder"),
    ("pre order", "preorder"),
    ("low stock", "low_stock"),
    ("only a few", "low_stock"),
    ("only \\d+ left", "low_stock"),
    ("limited stock", "low_stock"),
    ("almost gone", "low_stock"),
    ("in stock", "in_stock"),
    ("in stock now", "in_stock"),
    ("available now", "in_stock"),
    ("ready to ship", "in_stock"),
    ("add to cart", "in_stock"),
    ("add to basket", "in_stock"),
    ("buy now", "in_stock"),
)


def normalize_availability(raw) -> str:
    """Map schema.org availability URLs or human text to a known state.

    Order matters and is deliberate: human text is matched first, so
    "Currently unavailable" resolves to ``out_of_stock`` before the
    looser identifier map can see the "available" substring inside it.
    The identifier map then catches schema.org values such as
    ``https://schema.org/InStock``, which have no spaces to match on.

    Returns ``"unknown"`` rather than ``"in_stock"`` when nothing matches:
    absence of evidence is not evidence of availability.
    """
    if not raw:
        return "unknown"
    text = str(raw).strip().lower()
    if not text:
        return "unknown"
    for pattern, state in _AVAILABILITY_TEXT_MAP:
        if re.search(pattern, text):
            return state
    for needle, state in _AVAILABILITY_URL_MAP:
        if needle in text:
            return state
    return "unknown"


# --------------------------------------------------------------------------
# Small value wrapper — the evidence contract
# --------------------------------------------------------------------------


def field(value, method: str, raw) -> dict:
    """Build the ``{value, method, raw}`` evidence record."""
    if value is None:
        return {}
    if isinstance(value, Decimal):
        value = _money_text(value)
    if isinstance(value, (list, tuple)):
        value = [item if not isinstance(item, Decimal) else _money_text(item) for item in value]
    text = "" if raw is None else str(raw)
    return {
        "value": value,
        "method": method,
        "raw": text[:280],
    }


def _first(*candidates):
    for candidate in candidates:
        if candidate:
            return candidate
    return None


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if item is not None]
    return [value]


def _scalar(value):
    """Flatten a schema.org value that may be a dict/list wrapper."""
    value = _as_list(value)
    if not value:
        return None
    head = value[0]
    if isinstance(head, dict):
        return _scalar(head.get("name") or head.get("@value") or head.get("value"))
    return head


def _type_names(node) -> list:
    if not isinstance(node, dict):
        return []
    raw_type = node.get("@type") or node.get("type")
    names = []
    for item in _as_list(raw_type):
        if isinstance(item, str):
            names.append(item.rsplit("/", 1)[-1].rsplit("#", 1)[-1].lower())
    return names


def _iter_nodes(node, depth: int = 0):
    """Yield every dict node reachable through @graph / lists / values."""
    if depth > 6:
        return
    if isinstance(node, list):
        for item in node:
            yield from _iter_nodes(item, depth + 1)
        return
    if not isinstance(node, dict):
        return
    yield node
    for key in ("@graph", "mainEntity", "mainEntityOfPage", "itemListElement", "hasVariant", "isVariantOf"):
        if key in node:
            yield from _iter_nodes(node.get(key), depth + 1)


def _json_ld_documents(soup):
    """Parse every ``application/ld+json`` block, tolerating bad JSON.

    A single malformed block never discards the valid ones — storefront
    themes routinely emit broken JSON-LD alongside good data.
    """
    documents = []
    for script in soup.find_all("script", attrs={"type": True}):
        script_type = (script.get("type") or "").strip().lower()
        if "ld+json" not in script_type:
            continue
        raw = script.string or script.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            documents.append(json.loads(raw))
        except (ValueError, TypeError):
            # Some sites wrap JSON-LD in CDATA markers or a JS comment.
            cleaned = re.sub(r"^<!--|-->$", "", raw).strip()
            cleaned = re.sub(r"^//\s*<!\[CDATA\[|\]\]>\s*$", "", cleaned).strip()
            try:
                documents.append(json.loads(cleaned))
            except (ValueError, TypeError):
                continue
    return documents


def _offer_objects(offers):
    """Normalise Offer / AggregateOffer / list-of-offers into a list."""
    if offers is None:
        return []
    if isinstance(offers, dict):
        offers = offers.get("offers") if "offers" in offers else [offers]
    result = []
    for offer in _as_list(offers):
        if not isinstance(offer, dict):
            continue
        if isinstance(offer.get("offers"), list):
            result.extend(o for o in offer["offers"] if isinstance(o, dict))
            continue
        result.append(offer)
    return result


# --------------------------------------------------------------------------
# JSON-LD product
# --------------------------------------------------------------------------


def _from_json_ld(documents):
    product = None
    structured_types = []
    for document in documents:
        for node in _iter_nodes(document):
            names = _type_names(node)
            if not names:
                continue
            structured_types.extend(names)
            if product is None and (
                "product" in names or "productgroup" in names or "softwareapplication" in names
            ):
                product = node
    facts = {}
    types = sorted(set(structured_types))
    if product is None:
        return facts, types

    facts["name"] = field(_scalar(product.get("name")), "jsonld", product.get("name"))
    description = _scalar(product.get("description"))
    if description:
        facts["description"] = field(str(description)[:600], "jsonld", description)

    brand = product.get("brand")
    brand_name = _scalar(brand) if brand is not None else None
    if brand_name:
        facts["brand"] = field(brand_name, "jsonld", brand_name)

    sku = _scalar(product.get("sku")) or _scalar(product.get("mpn"))
    if sku:
        facts["sku"] = field(sku, "jsonld", sku)

    images = []
    for image in _as_list(product.get("image")):
        if isinstance(image, dict):
            candidate = image.get("url") or image.get("contentUrl")
        else:
            candidate = image
        if isinstance(candidate, str) and candidate.strip():
            images.append(candidate.strip()[:500])
    if images:
        facts["images"] = field(images[:12], "jsonld", "; ".join(images[:4]))

    offers = _offer_objects(product.get("offers"))
    if offers:
        prices = []
        currencies = []
        availabilities = []
        conditions = []
        valid_through = []
        for offer in offers:
            for key in ("price", "lowPrice", "highPrice", "priceSpecification"):
                spec = offer.get(key)
                if isinstance(spec, dict):
                    candidate = _scalar(spec.get("price")) or _scalar(spec.get("minPrice"))
                else:
                    candidate = spec
                if candidate is not None:
                    prices.append(candidate)
            currency = _scalar(offer.get("priceCurrency")) or _scalar(offer.get("priceCurrency "))
            if currency:
                currencies.append(str(currency).upper()[:8])
            availability = _scalar(offer.get("availability")) or _scalar(offer.get("itemCondition"))
            if availability and "availability" in offer:
                availabilities.append(str(availability))
            elif availability:
                conditions.append(str(availability))
            through = _scalar(offer.get("priceValidUntil")) or _scalar(offer.get("validThrough"))
            if through:
                valid_through.append(str(through))

        if prices:
            head = str(prices[0])
            amount, parsed_currency = parse_money(head)
            if amount is not None:
                facts["price"] = field(amount, "jsonld", head)
                resolved = _first(currencies[0] if currencies else None, parsed_currency)
                if resolved:
                    facts["currency"] = field(resolved, "jsonld", resolved)
        if availabilities:
            state = normalize_availability(availabilities[0])
            if state != "unknown":
                facts["availability"] = field(state, "jsonld", availabilities[0])
        if conditions and "condition" not in facts:
            facts["condition"] = field(conditions[0], "jsonld", conditions[0])
        if valid_through:
            facts["price_valid_until"] = field(valid_through[0], "jsonld", valid_through[0])

    rating = product.get("aggregateRating")
    if isinstance(rating, dict):
        rating_value = _scalar(rating.get("ratingValue"))
        if rating_value is not None:
            try:
                facts["rating"] = field(Decimal(str(rating_value)), "jsonld", rating_value)
            except (InvalidOperation, ValueError):
                pass
        best = _scalar(rating.get("bestRating"))
        if best is not None:
            facts["rating_max"] = field(best, "jsonld", best)
        count = _scalar(rating.get("reviewCount")) or _scalar(rating.get("ratingCount"))
        if count is not None:
            digits = re.sub(r"\D", "", str(count))
            if digits:
                facts["review_count"] = field(int(digits), "jsonld", count)

    specs = {}
    for prop in _as_list(product.get("additionalProperty")):
        if not isinstance(prop, dict):
            continue
        prop_name = _scalar(prop.get("name"))
        if not prop_name:
            continue
        prop_value = _scalar(prop.get("value"))
        if prop_value is None:
            continue
        specs[str(prop_name)[:80]] = str(prop_value)[:200]
    if specs:
        facts["specs"] = field(specs, "jsonld", "; ".join(list(specs)[:6]))

    variants = _variant_list(product)
    if variants:
        facts["variants"] = field(variants[:40], "jsonld", f"{len(variants)} offers/variants")

    shipping = _shipping_from_json_ld(offers)
    if shipping:
        facts["shipping"] = field(shipping, "jsonld", "; ".join(list(shipping)[:5]))

    bundles = _bundles_from_json_ld(product)
    if bundles:
        facts["bundles"] = field(bundles[:12], "jsonld", "; ".join(bundles[:4]))

    return facts, types


def _variant_list(product) -> list:
    variants = []
    seen = set()
    sources = _as_list(product.get("hasVariant"))
    for item in sources:
        if not isinstance(item, dict):
            continue
        label = _first(
            _scalar(item.get("name")),
            _scalar(item.get("sku")),
        )
        if not label:
            continue
        key = str(label).strip().lower()
        if key in seen:
            continue
        seen.add(key)
        offer = _offer_objects(item.get("offers"))
        entry = {"label": str(label)[:120]}
        if offer:
            amount, currency = parse_money(_scalar(offer[0].get("price")))
            if amount is not None:
                entry["price"] = _money_text(amount)
            offer_currency = _scalar(offer[0].get("priceCurrency"))
            if offer_currency:
                entry["currency"] = str(offer_currency).upper()[:8]
            elif currency:
                entry["currency"] = currency
        properties = {}
        for prop in _as_list(item.get("additionalProperty")):
            if not isinstance(prop, dict):
                continue
            prop_name = _scalar(prop.get("name"))
            prop_value = _scalar(prop.get("value"))
            if prop_name and prop_value is not None:
                properties[str(prop_name)[:60]] = str(prop_value)[:120]
        if properties:
            entry["properties"] = properties
        variants.append(entry)

    # A ProductGroup exposes its variants only as a priced offer list.
    if not variants:
        offers = _offer_objects(product.get("offers"))
        if len(offers) > 1:
            for offer in offers:
                label = _first(_scalar(offer.get("name")), _scalar(offer.get("sku")))
                if not label:
                    continue
                amount, currency = parse_money(_scalar(offer.get("price")))
                entry = {"label": str(label)[:120]}
                if amount is not None:
                    entry["price"] = _money_text(amount)
                offer_currency = _scalar(offer.get("priceCurrency"))
                if offer_currency:
                    entry["currency"] = str(offer_currency).upper()[:8]
                elif currency:
                    entry["currency"] = currency
                variants.append(entry)
    return variants


def _shipping_from_json_ld(offers) -> dict:
    shipping = {}
    for offer in offers:
        details = _as_list(offer.get("shippingDetails"))
        for detail in details:
            if not isinstance(detail, dict):
                continue
            rate = detail.get("shippingRate")
            if isinstance(rate, dict):
                value = _scalar(rate.get("value"))
                if value is not None:
                    amount, _currency = parse_money(value)
                    shipping["cost"] = _money_text(amount) if amount is not None else str(value)
                unit = _scalar(rate.get("unitCode")) or _scalar(rate.get("unitText"))
                if unit:
                    shipping["unit"] = str(unit)[:40]
            destination = _as_list(detail.get("shippingDestination"))
            for dest in destination:
                if isinstance(dest, dict):
                    address = dest.get("address")
                    if isinstance(address, dict):
                        country = _scalar(address.get("addressCountry"))
                        if country:
                            shipping.setdefault("destination", str(country)[:60])
            transit = _scalar(detail.get("deliveryTime"))
            if transit:
                shipping.setdefault("delivery_time", str(transit)[:120])
    return shipping


def _bundles_from_json_ld(product) -> list:
    bundles = []
    for key in ("isRelatedTo", "subjectOf", "variesBy", "isPartOf"):
        for node in _iter_nodes(product.get(key)):
            label = _scalar(node.get("name")) if isinstance(node, dict) else None
            if label:
                bundles.append(str(label)[:120])
    for prop in _as_list(product.get("additionalProperty")):
        if not isinstance(prop, dict):
            continue
        prop_name = str(_scalar(prop.get("name")) or "").lower()
        if any(token in prop_name for token in ("bundle", "includes", "package", "kit", "combo")):
            bundles.append(str(_scalar(prop.get("value")) or prop_name)[:120])
    seen = set()
    unique = []
    for item in bundles:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


# --------------------------------------------------------------------------
# Microdata
# --------------------------------------------------------------------------


def _from_microdata(soup):
    facts = {}
    scope = None
    for element in soup.find_all(attrs={"itemtype": True}):
        itemtype = " ".join(element.get("itemtype") or []).lower()
        if "schema.org/product" in itemtype.replace(" ", "") or itemtype.rstrip("/").endswith("product"):
            scope = element
            break
    if scope is None:
        return facts

    def prop(name):
        node = scope.find(attrs={"itemprop": name})
        if node is None:
            return None
        if node.get("content"):
            return node.get("content")
        if node.has_attr("href"):
            return node.get("href")
        if node.has_attr("src"):
            return node.get("src")
        return node.get_text(" ", strip=True)

    name = prop("name")
    if name:
        facts["name"] = field(str(name)[:200], "microdata", name)
    description = prop("description")
    if description:
        facts["description"] = field(str(description)[:600], "microdata", description)
    sku = prop("sku")
    if sku:
        facts["sku"] = field(str(sku)[:80], "microdata", sku)
    price = prop("price")
    if price:
        amount, currency = parse_money(price)
        if amount is not None:
            facts["price"] = field(amount, "microdata", price)
            if currency:
                facts["currency"] = field(currency, "microdata", price)
    currency = prop("priceCurrency")
    if currency and "currency" not in facts:
        facts["currency"] = field(str(currency).upper()[:8], "microdata", currency)
    availability = prop("availability")
    if availability:
        state = normalize_availability(availability)
        if state != "unknown":
            facts["availability"] = field(state, "microdata", availability)
    rating = prop("ratingValue")
    if rating:
        try:
            facts["rating"] = field(Decimal(str(rating).strip()), "microdata", rating)
        except (InvalidOperation, ValueError):
            pass
    count = prop("reviewCount") or prop("ratingCount")
    if count:
        digits = re.sub(r"\D", "", str(count))
        if digits:
            facts["review_count"] = field(int(digits), "microdata", count)
    images = []
    for node in scope.find_all(attrs={"itemprop": "image"}):
        candidate = node.get("content") or node.get("src") or node.get("href")
        if candidate:
            images.append(str(candidate)[:500])
    if images:
        facts["images"] = field(images[:12], "microdata", images[0])
    return facts


# --------------------------------------------------------------------------
# OpenGraph / meta
# --------------------------------------------------------------------------


def _meta_map(soup) -> dict:
    values = {}
    for node in soup.find_all("meta"):
        key = node.get("property") or node.get("name") or node.get("itemprop")
        content = node.get("content")
        if not key or content is None:
            continue
        key = key.strip().lower()
        if key and key not in values:
            values[key] = content
    return values


def _from_meta(soup, meta) -> dict:
    facts = {}
    title = meta.get("og:title") or meta.get("twitter:title")
    if title:
        facts["page_title"] = field(str(title)[:250], "opengraph", title)
    description = meta.get("og:description") or meta.get("description") or meta.get("twitter:description")
    if description:
        facts["page_description"] = field(str(description)[:600], "opengraph", description)
    site_name = meta.get("og:site_name")
    if site_name:
        facts["site_name"] = field(str(site_name)[:120], "opengraph", site_name)
    image = meta.get("og:image") or meta.get("twitter:image")
    if image:
        facts["page_image"] = field(str(image)[:500], "opengraph", image)

    amount = meta.get("product:price:amount") or meta.get("og:price:amount") or meta.get("twitter:data1")
    if amount:
        parsed, currency = parse_money(amount)
        if parsed is not None:
            facts["price"] = field(parsed, "opengraph", amount)
    currency = meta.get("product:price:currency") or meta.get("og:price:currency")
    if currency and "currency" not in facts:
        facts["currency"] = field(str(currency).upper()[:8], "opengraph", currency)
    availability = meta.get("product:availability") or meta.get("og:availability") or meta.get("product:availability:state")
    if availability:
        state = normalize_availability(availability)
        if state != "unknown":
            facts["availability"] = field(state, "opengraph", availability)

    # Some storefronts expose a compare-at price as plain meta.
    compare = meta.get("product:original_price:amount") or meta.get("og:price:standard_amount")
    if compare:
        parsed, _currency = parse_money(compare)
        if parsed is not None:
            facts["list_price"] = field(parsed, "opengraph", compare)
    return facts


# --------------------------------------------------------------------------
# Heuristics (last resort, and always labelled as such)
# --------------------------------------------------------------------------

# Class / attribute signals for the *current* price.
#
# This list is a FALLBACK. The primary path is the token rule in
# _find_price_element, which generalises to the long tail of storefront
# class names (price_color, special-price, currentCost, ...) instead of
# chasing each one.
_PRICE_HINTS = (
    'itemprop="price"',
    "price--current",
    "price-current",
    "current-price",
    "product-price",
    "product__price",
    "price_final",
    "js-price",
    "a-price",
    "pdp-price",
    "offer-price",
    "sale-price",
    "our-price",
    "currentcost",
    "pricenow",
    "special-price",
)

# Class tokens that mark the *current* price, with a specificity weight.
# Matched against whole tokens, never substrings, so "priceless" cannot
# match "price".
_PRICE_TOKENS = (
    ("price", 10),
    ("productprice", 14),
    ("pricecurrent", 18),
    ("currentprice", 18),
    ("saleprice", 18),
    ("ourprice", 18),
    ("offerprice", 18),
    ("specialprice", 16),
    ("finalprice", 16),
    ("pricenow", 18),
    ("pricecolor", 16),
    ("pricevalue", 16),
    ("buyprice", 16),
    ("cost", 8),
    ("currentcost", 16),
    ("amount", 6),
)

# Signals for the *previous / compare-at* price.
_LIST_PRICE_HINTS = (
    "price--old",
    "price--regular",
    "price--compare",
    "compare-at",
    "list-price",
    "listprice",
    "regular-price",
    "old-price",
    "was-price",
    "price-was",
    "strikethrough",
    "line-through",
    "original-price",
    "data-original-price",
    "data-price-strike",
)

_LIST_PRICE_TOKENS = (
    ("oldprice", 18),
    ("wasprice", 18),
    ("compareat", 18),
    ("compareatprice", 18),
    ("listprice", 18),
    ("regularprice", 18),
    ("originalprice", 18),
    ("strikethrough", 18),
    ("linethrough", 18),
    ("pricestrike", 18),
)

# Class tokens that mark a dedicated availability / stock statement. Used
# for the HTML availability pass and for product detection, so a price
# mentioned inside a blog paragraph is never read as stock.
_STOCK_TOKENS = (
    "availability",
    "instock",
    "outofstock",
    "stock",
    "stockstatus",
    "productavailability",
    "available",
    "soldout",
    "backorder",
    "preorder",
    "inventory",
)

_BADGE_HINTS = ("badge", "ribbon", "label", "tag", "pill", "chip")
_BADGE_WORDS = (
    "new", "sale", "bestseller", "best seller", "popular", "limited",
    "exclusive", "trending", "top rated", "staff pick", "premium",
    "free shipping", "free trial", "beta", "coming soon", "clearance",
    "discount", "offer", "deal", "recommended",
)

_SHIPPING_WORDS = (
    "free shipping", "free delivery", "free express", "next day delivery",
    "next-day delivery", "same day delivery", "dispatched within",
    "ships in", "shipping:", "delivery:", "no shipping cost",
)

_TRACKED = (
    "name", "description", "brand", "sku", "price", "list_price", "currency",
    "availability", "condition", "rating", "rating_max", "review_count",
    "variants", "images", "specs", "shipping", "badges", "bundles",
    "page_title", "page_description", "site_name", "page_image",
    "price_valid_until",
)


_CLASS_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")
_MAX_PRICE = Decimal("1000000")


def _class_tokens(element):
    """Lowercased alphanumeric class tokens of an element.

    Individual tokens are returned, plus the compacted form of each class
    value *and* of the whole class attribute, so all three of these resolve:

      class="price_color"   -> {"price", "color", "pricecolor"}
      class="old price"     -> {"old", "price", "oldprice"}
      class="was--price"    -> {"was", "price", "wasprice"}

    Storefronts spell the same idea every way, and this is what lets the
    token rules generalise instead of chasing a list of class names.
    """
    values = [str(value).lower() for value in (element.get("class") or [])]
    tokens = set()
    for raw in values:
        compact = "".join(_CLASS_TOKEN_SPLIT_RE.split(raw))
        if compact:
            tokens.add(compact)
        for part in _CLASS_TOKEN_SPLIT_RE.split(raw):
            if part:
                tokens.add(part)
    whole = "".join(_CLASS_TOKEN_SPLIT_RE.split(" ".join(values)))
    if whole:
        tokens.add(whole)
    return tokens


def _element_hints(element) -> str:
    parts = []
    for attribute in (
        "class",
        "id",
        "data-testid",
        "data-test",
        "itemprop",
        "data-price",
        "data-original-price",
        "data-product-price",
    ):
        value = element.get(attribute)
        if value:
            parts.append(str(value))
    return " ".join(parts).lower()


# Specific substrings that mark a compare-at / was-price element. Long and
# distinctive on purpose, so "old" alone can never exclude a legitimate
# current-price element.
_LIST_PRICE_MARKERS = (
    "oldprice",
    "priceold",
    "wasprice",
    "pricewas",
    "strikethrough",
    "linethrough",
    "compareat",
    "listprice",
    "regularprice",
    "originalprice",
    "pricestrike",
    "msrp",
    "rrp",
)


def _is_list_price_tokens(tokens) -> bool:
    """True when these class tokens mark a compare-at / was-price element."""
    return any(
        marker in token
        for token in tokens
        for marker in _LIST_PRICE_MARKERS
    )


def _best_token_match(soup, token_table, exclude_list_price=False):
    """Highest-specificity element whose class tokens match a price signal.

    Token-based on purpose: chasing an explicit list of storefront class
    names misses most of the long tail, and a plain substring match on
    "price" would also fire on "priceless" or on a paragraph that merely
    mentions a number.

    When one element matches several tokens the HIGHEST weight wins, so
    table order cannot change the result.
    """
    best = None
    best_weight = 0
    for element in soup.find_all(attrs={"class": True}, limit=4000):
        tokens = _class_tokens(element)
        if not tokens:
            continue
        if exclude_list_price and _is_list_price_tokens(tokens):
            continue
        weight = 0
        for token, token_weight in token_table:
            if token in tokens and token_weight > weight:
                weight = token_weight
        if not weight:
            continue
        text = element.get_text(" ", strip=True)
        amount, _currency = parse_money(text)
        if amount is None or not 0 < amount < _MAX_PRICE:
            continue
        if weight > best_weight:
            best = (element, text)
            best_weight = weight
    return best or (None, "")


def _find_price_element(soup):
    found = _best_token_match(soup, _PRICE_TOKENS, exclude_list_price=True)
    if found[0] is not None:
        return found
    for hint in _PRICE_HINTS:
        needle = hint.lower()
        for element in soup.find_all(attrs={"class": True}):
            if needle in " ".join(element.get("class") or []).lower():
                text = element.get_text(" ", strip=True)
                amount, _currency = parse_money(text)
                if amount is not None and 0 < amount < _MAX_PRICE:
                    return element, text
        for element in soup.find_all(attrs={"data-price": True}):
            if needle in _element_hints(element):
                text = element.get("data-price")
                amount, _currency = parse_money(text)
                if amount is not None:
                    return element, str(text)
    return (None, "")


def _find_list_price_element(soup):
    found = _best_token_match(soup, _LIST_PRICE_TOKENS)
    if found[0] is not None:
        return found
    for hint in _LIST_PRICE_HINTS:
        needle = hint.lower()
        for element in soup.find_all(attrs={"class": True}):
            if needle in " ".join(element.get("class") or []).lower():
                text = element.get_text(" ", strip=True)
                amount, _currency = parse_money(text)
                if amount is not None and 0 < amount < _MAX_PRICE:
                    return element, text
    return (None, "")


def _find_stock_element(soup):
    """Element that states availability, judged by class tokens only.

    Requiring a stock-ish class token is what stops a price mentioned in a
    review or a blog post from being read as a stock signal.
    """
    for element in soup.find_all(attrs={"class": True}, limit=4000):
        if not _class_tokens(element) & set(_STOCK_TOKENS):
            continue
        text = element.get_text(" ", strip=True)
        if 0 < len(text) <= 80:
            return element, text
    return (None, "")


def _heuristic_prices(soup, facts) -> None:
    if "price" not in facts:
        # A machine-readable data attribute always beats rendered text.
        for attribute in ("data-price", "data-product-price", "data-sale-price"):
            for element in soup.find_all(attrs={attribute: True}, limit=40):
                amount, currency = parse_money(element.get(attribute))
                if amount is not None and 0 < amount < _MAX_PRICE:
                    facts["price"] = field(
                        amount, "attribute", f'{attribute}="{element.get(attribute)}"'
                    )
                    if currency:
                        facts["currency"] = field(currency, "attribute", element.get(attribute))
                    break
            if "price" in facts:
                break
    if "price" not in facts:
        element, text = _find_price_element(soup)
        if element is not None:
            amount, currency = parse_money(text)
            if amount is not None:
                facts["price"] = field(amount, "heuristic", text[:120])
                if currency and "currency" not in facts:
                    facts["currency"] = field(currency, "heuristic", text[:120])
    if "list_price" not in facts:
        _element, text = _find_list_price_element(soup)
        if text:
            amount, _currency = parse_money(text)
            if amount is not None and ("price" not in facts or amount > Decimal(str(facts["price"]["value"]))):
                facts["list_price"] = field(amount, "heuristic", text[:120])


def _heuristic_availability(soup, facts) -> None:
    """Read a stock statement from a dedicated availability element."""
    if "availability" in facts:
        return
    _element, text = _find_stock_element(soup)
    if not text:
        return
    state = normalize_availability(text)
    if state != "unknown":
        facts["availability"] = field(state, "heuristic", text[:120])


def _heuristic_badges(soup) -> list:
    badges = []
    seen = set()
    for element in soup.find_all(attrs={"class": True}, limit=4000):
        classes = " ".join(element.get("class") or []).lower()
        if not any(hint in classes for hint in _BADGE_HINTS):
            continue
        text = element.get_text(" ", strip=True)
        if not text or len(text) > 40:
            continue
        lowered = text.lower()
        if not any(word in lowered for word in _BADGE_WORDS):
            continue
        key = lowered.strip()
        if key in seen:
            continue
        seen.add(key)
        badges.append(text)
        if len(badges) >= 8:
            break
    return badges


def _heuristic_shipping(soup) -> dict:
    shipping = {}
    for word in _SHIPPING_WORDS:
        for element in soup.find_all(string=lambda text: text and word in str(text).lower()):
            snippet = str(element).strip()
            if 0 < len(snippet) <= 160:
                shipping.setdefault("note", snippet)
                break
        if "note" in shipping:
            break
    return shipping


def _heuristic_variants(soup) -> list:
    """Read ``<option>`` labels from selects that look like variant pickers."""
    variants = []
    seen = set()
    for select in soup.find_all("select", limit=12):
        select_hint = _element_hints(select)
        options = select.find_all("option", limit=60)
        labels = [option.get_text(" ", strip=True) for option in options]
        labels = [label for label in labels if label and not label.lower().startswith(("select", "choose", "option"))]
        if len(labels) < 2:
            continue
        if not any(token in select_hint for token in ("variant", "size", "colour", "color", "option", "attribute", "swatch", "product")):
            continue
        for label in labels[:40]:
            key = label.lower()
            if key in seen:
                continue
            seen.add(key)
            variants.append({"label": label[:120]})
        if variants:
            break
    return variants


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def decode_html(content: bytes, content_type: str = "") -> str:
    charset = ""
    match = re.search(r"charset=([^\s;]+)", content_type or "", re.IGNORECASE)
    if match:
        charset = match.group(1).strip().strip('"\'')
    for encoding in filter(None, (charset, "utf-8")):
        try:
            return content.decode(encoding)
        except (LookupError, UnicodeError):
            continue
    return content.decode("utf-8", errors="replace")


def extract_page_facts(content, content_type: str = "", url: str = "") -> dict:
    """Extract evidence-backed product facts from a public HTML page.

    ``content`` may be ``bytes`` or ``str``. The return value is always
    JSON-serialisable and never contains raw HTML.
    """
    if isinstance(content, str):
        html = content
    else:
        html = decode_html(bytes(content or b""), content_type or "")

    soup = BeautifulSoup(html, "html.parser")
    meta = _meta_map(soup)
    documents = _json_ld_documents(soup)

    product, structured_types = _from_json_ld(documents)
    microdata = _from_microdata(soup)
    open_graph = _from_meta(soup, meta)

    # Precedence, strongest evidence first. Each source is consulted only
    # for fields the stronger source did not supply.
    facts = {}
    for source in (product, microdata, open_graph):
        for key, value in source.items():
            if key not in facts and value:
                facts[key] = value

    _heuristic_prices(soup, facts)
    _heuristic_availability(soup, facts)

    if "badges" not in facts:
        badges = _heuristic_badges(soup)
        if badges:
            facts["badges"] = field(badges, "heuristic", "; ".join(badges[:4]))
    if "variants" not in facts:
        variants = _heuristic_variants(soup)
        if variants:
            facts["variants"] = field(variants, "heuristic", f"{len(variants)} options")
    if "shipping" not in facts:
        shipping = _heuristic_shipping(soup)
        if shipping:
            facts["shipping"] = field(shipping, "heuristic", shipping.get("note", ""))

    if "name" not in facts:
        # Fall back through progressively weaker sources so a plain-HTML
        # product page still gets a usable name instead of "Unnamed product".
        heading = soup.find("h1")
        if heading and heading.get_text(strip=True):
            facts["name"] = field(
                heading.get_text(" ", strip=True)[:250], "html", heading.get_text(" ", strip=True)
            )
    if "name" not in facts:
        fallback = facts.get("page_title", {}).get("value")
        if fallback:
            facts["name"] = field(str(fallback)[:250], "html", fallback)

    title_tag = soup.find("title")
    if title_tag and title_tag.get_text(strip=True):
        facts.setdefault("page_title", field(title_tag.get_text(strip=True)[:250], "html", title_tag.get_text(strip=True)))
    canonical = soup.find("link", attrs={"rel": "canonical"})
    if canonical and canonical.get("href"):
        facts["canonical_url"] = field(str(canonical.get("href"))[:500], "html", canonical.get("href"))
    if not facts.get("page_description"):
        description = soup.find("meta", attrs={"name": "description"})
        if description and description.get("content"):
            facts["page_description"] = field(
                str(description.get("content"))[:600], "html", description.get("content")
            )

    result = {key: facts[key] for key in _TRACKED if facts.get(key)}
    result["opengraph_type"] = (meta.get("og:type") or "").strip()[:60]
    result["structured_data_types"] = structured_types[:24]
    result["product_detection"] = _product_detection(facts, structured_types, meta, soup)
    result["product_detected"] = result["product_detection"]["detected"]
    result["extraction_methods"] = sorted({value["method"] for value in result.values() if isinstance(value, dict) and "method" in value})
    if url:
        result["source_url"] = url
    return result


_PRODUCT_TYPES = ("product", "productgroup", "softwareapplication", "offer", "aggregateoffer")


_BUY_PHRASES = (
    "add to cart",
    "add to basket",
    "add to bag",
    "buy now",
    "add to wishlist",
    "select options",
    "choose an option",
    "in stock",
    "out of stock",
    "only a few left",
)


def _product_detection(facts, structured_types, meta, soup) -> dict:
    """Decide whether this page is a product page, and say why.

    Returns ``{"detected": bool, "method": "structured"|"heuristic"|"",
    "signals": [...]}``. The signals are the exact reasons, so the
    classification rationale shown to a user can never claim structured
    data that the page did not actually publish.

    The strong signals come first and are unambiguous. The weak signals
    (a price in a price-marked element plus a stock statement in a
    stock-marked element) are deliberately conservative: both halves must
    be in dedicated elements, so a price or the words "in stock" inside a
    review or a blog post never turn an article into a product page.
    """
    signals = []

    for name in structured_types:
        if name in _PRODUCT_TYPES:
            signals.append(f"The page publishes schema.org {name} structured data.")
            return {"detected": True, "method": "structured", "signals": signals}

    for element in soup.find_all(attrs={"itemtype": True}, limit=50):
        itemtype = " ".join(element.get("itemtype") or []).lower().replace(" ", "")
        if "schema.org/product" in itemtype:
            signals.append("The page publishes schema.org Product microdata.")
            return {"detected": True, "method": "structured", "signals": signals}

    if meta.get("product:price:amount"):
        signals.append("The page publishes a product:price:amount meta tag.")
        return {"detected": True, "method": "structured", "signals": signals}
    og_type = (meta.get("og:type") or "").lower()
    if og_type in ("product", "product.item"):
        signals.append(f'The page declares og:type "{og_type}".')
        return {"detected": True, "method": "structured", "signals": signals}

    if facts.get("variants") and facts.get("price"):
        signals.append("The page publishes a price together with a variant list.")
        return {"detected": True, "method": "structured", "signals": signals}

    if not facts.get("price"):
        return {"detected": False, "method": "", "signals": signals}

    title = str(facts.get("page_title", {}).get("value", "")).lower()
    matched = [phrase for phrase in _BUY_PHRASES if phrase in title]
    if matched:
        signals.append(f'The page title says "{matched[0]}".')
        _price_element, _stock_element = _find_price_element(soup), _find_stock_element(soup)
        if _price_element is not None:
            signals.append("A price is published on the page.")
        return {"detected": True, "method": "heuristic", "signals": signals}

    price_element, price_text = _find_price_element(soup)
    stock_element, stock_text = _find_stock_element(soup)
    if price_element is not None and stock_element is not None:
        signals.append(
            f'A price is published in an element marked "{_element_hints(price_element)[:60]}" '
            "and the page states its availability in a dedicated stock element."
        )
        return {"detected": True, "method": "heuristic", "signals": signals}

    return {"detected": False, "method": "", "signals": signals}


def summarize_facts(facts: dict) -> dict:
    """Flat, UI-friendly view of an extraction result (values only)."""
    summary = {}
    for key, value in facts.items():
        if isinstance(value, dict) and "value" in value:
            summary[key] = value["value"]
        else:
            summary[key] = value
    return summary


def field_method(facts: dict, key: str) -> str:
    entry = facts.get(key)
    if isinstance(entry, dict):
        return entry.get("method", "")
    return ""


def field_raw(facts: dict, key: str) -> str:
    entry = facts.get(key)
    if isinstance(entry, dict):
        return entry.get("raw", "")
    return ""
