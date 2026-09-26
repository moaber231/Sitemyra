"""Page classification and same-site monitoring-target discovery.

**Pure module** — no network, no database. It turns a URL plus an
extraction result (and optionally the raw HTML) into:

* a page *kind* (``product``, ``pricing``, ``changelog``, ...),
* a list of other public pages on the same site worth monitoring,
* a factual "why this matters" string for each suggestion.

The relevance number is a **ranking heuristic for ordering links**, not a
business, quality or health score. It is computed from observable
properties only (kind weight, path depth, link-text specificity) and is
documented in :data:`KIND_WEIGHTS` so it can be audited.
"""

import re

from bs4 import BeautifulSoup

from .page_facts import decode_html
from .urls import (
    absolute,
    display_host,
    host_of,
    is_excluded_path,
    normalize_url,
    path_segments,
    same_origin,
)

# --------------------------------------------------------------------------
# Page kinds
# --------------------------------------------------------------------------

PRODUCT = "product"
PRICING = "pricing"
FEATURES = "features"
VARIANTS = "variants"
REVIEWS = "reviews"
FAQ = "faq"
DOCS = "docs"
CHANGELOG = "changelog"
BLOG = "blog"
CAREERS = "careers"
PROMOTIONS = "promotions"
HOMEPAGE = "homepage"
LEGAL = "legal"
SUPPORT = "support"
OTHER = "other"

KIND_LABELS = {
    PRODUCT: "Product",
    PRICING: "Pricing",
    FEATURES: "Features",
    VARIANTS: "Product variants",
    REVIEWS: "Reviews",
    FAQ: "FAQ",
    DOCS: "Documentation",
    CHANGELOG: "Changelog",
    BLOG: "Blog",
    CAREERS: "Careers",
    PROMOTIONS: "Promotions",
    HOMEPAGE: "Homepage & messaging",
    LEGAL: "Legal & policies",
    SUPPORT: "Support",
    OTHER: "Other public pages",
}

# Human-readable "what a change here means", used to build the rationale.
KIND_SIGNALS = {
    PRODUCT: "Price, availability, variants and product copy are published on this page.",
    PRICING: "Plans, prices and packaging are published on this page.",
    FEATURES: "The capability list is published on this page.",
    VARIANTS: "Variant and option lists are published on this page.",
    REVIEWS: "Ratings, review counts and review content are published here.",
    FAQ: "Answers to common buying questions are published here.",
    DOCS: "Product documentation is published on this site.",
    CHANGELOG: "Release notes are published on this site.",
    BLOG: "Editorial content is published on this site.",
    CAREERS: "Open roles are published on this site.",
    PROMOTIONS: "Active offers and promotions are published here.",
    HOMEPAGE: "Primary positioning and messaging live here.",
    LEGAL: "Policy pages are published on this site.",
    SUPPORT: "Support content is published on this site.",
    OTHER: "This page was not classified further.",
}

# Ordering heuristic weights. Deliberately simple and auditable: a
# pricing page is surfaced above a blog index because a pricing change is
# the signal most users mean when they say "watch this competitor".
KIND_WEIGHTS = {
    PRODUCT: 100,
    PRICING: 95,
    PROMOTIONS: 80,
    FEATURES: 78,
    VARIANTS: 70,
    CHANGELOG: 68,
    HOMEPAGE: 66,
    REVIEWS: 62,
    DOCS: 60,
    FAQ: 50,
    CAREERS: 48,
    BLOG: 45,
    SUPPORT: 35,
    LEGAL: 20,
    OTHER: 25,
}

# Path fragments -> kind, checked against the tokens of the URL path.
#
# Matching is token-based, never substring-based: "post" must not match
# inside "/support" and "plan" must not match inside "/planted". A segment
# is split on -, _, . and camelCase into the tokens below, and a rule
# fires when one of its needles is a token of the segment.
_PATH_RULES = (
    (CHANGELOG, ("changelog", "changelogs", "release", "releases", "notes", "whatsnew", "updates", "history", "version", "versions")),
    (PRICING, ("pricing", "prices", "plans", "plan", "tariffs", "tarif", "ratecard", "memberships", "billing", "subscribe", "subscription")),
    (PROMOTIONS, ("sale", "sales", "offer", "offers", "deals", "deal", "promotions", "promo", "discounts", "discount", "friday", "coupons", "coupon", "campaigns", "campaign")),
    (CAREERS, ("careers", "career", "jobs", "job", "vacancies", "vacancy", "positions", "hiring", "joinus", "workwithus", "employment")),
    (REVIEWS, ("reviews", "review", "testimonials", "testimonial", "ratings", "rating", "stories", "studystudies", "casestudies", "customers")),
    (FAQ, ("faq", "faqs", "questions", "asked", "helpcenter", "helpcentre")),
    (DOCS, ("docs", "doc", "documentation", "developers", "developer", "api", "reference", "guides", "guide", "manual", "handbook")),
    (BLOG, ("blog", "news", "articles", "article", "posts", "post", "insights", "resources", "press", "magazine", "stories")),
    (VARIANTS, ("variants", "variant", "sizes", "size", "colors", "colours", "color", "colour", "options", "swatches")),
    (PRODUCT, ("product", "products", "p", "item", "items", "shop", "store", "dp", "detail", "details", "buy", "listing", "category", "collection", "collections", "catalog", "catalogue")),
    (FEATURES, ("features", "feature", "capabilities", "capability", "solutions", "platform", "whyus", "compare", "comparison", "alternatives", "vs", "benefits")),
    (SUPPORT, ("contact", "support", "help", "ticket", "tickets", "enquiry", "faq")),
    (LEGAL, ("privacy", "terms", "legal", "imprint", "cookie", "cookies", "refund", "returns", "disclaimer", "policies", "policy")),
)

_TOKEN_SPLIT_RE = re.compile(r"[-_.\s]+")
_TOKEN_CHUNKS_RE = re.compile(r"[a-z]+|\d+")


def _segment_tokens(segment: str):
    """Split a path segment into comparable lowercase tokens."""
    lowered = segment.lower()
    tokens = set()
    for part in _TOKEN_SPLIT_RE.split(lowered):
        if not part:
            continue
        tokens.add(part)
        for chunk in _TOKEN_CHUNKS_RE.findall(part):
            tokens.add(chunk)
    return tokens

_TITLE_RULES = (
    (CHANGELOG, ("changelog", "release notes", "what's new", "whats new", "changelog history")),
    (PRICING, ("pricing", "plans and pricing", "plans & pricing", "choose a plan", "our plans")),
    (CAREERS, ("careers", "open positions", "join our team", "we're hiring", "we are hiring", "vacancies")),
    (PROMOTIONS, ("sale", "deals", "offers", "black friday", "promotion", "discount")),
    (REVIEWS, ("reviews", "testimonials", "customer reviews", "ratings")),
    (FEATURES, ("features", "capabilities", "product overview", "everything you need", "platform")),
    (FAQ, ("faq", "frequently asked", "common questions")),
    (BLOG, ("blog", "news", "insights", "articles", "press")),
    (PRODUCT, ("add to cart", "add to basket", "buy now", "in stock", "product details")),
)

# Structured-data types that imply a product listing page.
_PRODUCT_CONTAINER_TYPES = ("itemlist", "collectionpage", "searchresultspage", "productgroup")


def _classify_from_path(url):
    segments = [segment.lower() for segment in path_segments(url)]
    if not segments:
        return (HOMEPAGE, "high", "The URL is the site root.")
    for kind, needles in _PATH_RULES:
        for segment in segments:
            tokens = _segment_tokens(segment)
            for needle in needles:
                if needle in tokens:
                    exact = segment == needle
                    return (
                        kind,
                        "high" if exact else "medium",
                        f'The URL path contains "/{segment}", which Sitemyra recognises as a {KIND_LABELS[kind].lower()} page.',
                    )
    return (None, "", "")


def _classify_from_title(facts):
    title = str(facts.get("page_title", {}).get("value", "")).lower()
    if not title:
        return (None, "", "")
    for kind, needles in _TITLE_RULES:
        for needle in needles:
            if needle in title:
                return (kind, "medium", f'The page title contains "{needle}".')
    return (None, "", "")


def classify_page(url: str, facts: dict):
    """Return ``(kind, confidence, rationale)`` for a page.

    The rationale lists only observable signals, so it can be shown to the
    user verbatim as the explanation for a classification.
    """
    from_path = _classify_from_path(url)
    from_title = _classify_from_title(facts)

    signals = []
    if from_path[0]:
        signals.append(from_path[2])
    if from_title[0]:
        signals.append(from_title[2])

    detection = facts.get("product_detection") or {}
    is_product = bool(detection.get("detected", facts.get("product_detected")))
    structured = set(facts.get("structured_data_types") or [])
    # Quote the extractor's own recorded signals. This is what keeps the
    # rationale honest: a page detected heuristically is never described as
    # if it had published structured data.
    for signal in detection.get("signals") or []:
        if signal not in signals:
            signals.append(signal)
    is_structured = detection.get("method") == "structured"
    if not signals and is_product:
        signals.append("Product data was found on this page.")

    # A Product URL is decisive: a product page is a product page even when
    # the path also contains "shop" or "collections". A path that clearly
    # signals a different kind (pricing, changelog, careers) still wins,
    # because the structured data then describes an *item on* that page.
    if is_product and from_path[0] in (None, PRODUCT, VARIANTS, HOMEPAGE):
        # Structured data is high confidence; a heuristic read is medium,
        # because it depends on the storefront's markup staying put.
        confidence = "high" if (is_structured and "product" in structured) else "medium"
        return (PRODUCT, confidence, " ".join(signals) or "Product data was found on this page.")

    if from_path[0]:
        kind = from_path[0]
        # A page carrying a price is pricing intelligence even if the path
        # says "features" — we follow the observable evidence.
        if kind in (FEATURES, HOMEPAGE, OTHER) and facts.get("price"):
            signals.append("A price is published on this page.")
            if kind == HOMEPAGE:
                return (HOMEPAGE, "medium", " ".join(signals))
            return (PRICING, "medium", " ".join(signals))
        confidence = from_path[1]
        if from_title[0] == kind and from_title[1] == "high":
            confidence = "high"
        return (kind, confidence, " ".join(signals))

    if from_title[0]:
        return (from_title[0], from_title[1], " ".join(signals))

    if any(name in _PRODUCT_CONTAINER_TYPES for name in structured) and facts.get("price"):
        return (PRODUCT, "medium", "A product listing with prices was found on this page.")

    if facts.get("price"):
        return (PRODUCT, "low", "A price is published on this page but no product structure was detected.")

    return (OTHER, "low", "Sitemyra could not classify this page beyond a public page.")


# --------------------------------------------------------------------------
# Target discovery
# --------------------------------------------------------------------------

MAX_TARGETS = 20
MAX_LINKS_SCANNED = 600

_LINK_TEXT_RULES = (
    (PRICING, ("pricing", "plans", "price", "tariffs")),
    (CAREERS, ("careers", "jobs", "vacancies", "open roles", "hiring")),
    (CHANGELOG, ("changelog", "release notes", "what's new", "whats new", "updates")),
    (FEATURES, ("features", "capabilities", "platform", "solutions", "product")),
    (REVIEWS, ("reviews", "testimonials", "customers", "ratings")),
    (FAQ, ("faq", "frequently asked", "help")),
    (DOCS, ("docs", "documentation", "developers", "api", "guide")),
    (BLOG, ("blog", "news", "insights", "articles", "resources")),
    (PROMOTIONS, ("sale", "deals", "offers", "promotions", "discount")),
)

_SKIP_LINK_HOSTS = (
    "facebook.com", "twitter.com", "x.com", "linkedin.com", "instagram.com",
    "youtube.com", "tiktok.com", "pinterest.com", "reddit.com", "github.com",
    "apple.com", "play.google.com", "google.com", "trustpilot.com",
    "g2.com", "capterra.com", "stripe.com", "paypal.com", "shopify.com",
    "mailto:", "tel:", "javascript:", "#",
)


def _is_external(href: str) -> bool:
    lowered = href.lower()
    if lowered.startswith(_SKIP_LINK_HOSTS):
        return True
    return False


def _classify_link(url: str, link_text: str):
    from_path = _classify_from_path(url)
    if from_path[0] and from_path[0] not in (HOMEPAGE,):
        return (from_path[0], from_path[2])
    lowered = (link_text or "").lower().strip()
    if lowered:
        for kind, needles in _LINK_TEXT_RULES:
            for needle in needles:
                if needle in lowered:
                    return (kind, f'The link is labelled "{link_text.strip()[:60]}" on the page you submitted.')
    return (OTHER, _fallback_why(url, link_text))


def _fallback_why(url: str, link_text: str) -> str:
    """A truthful reason for proposing a page Sitemyra could not type.

    Better than "not classified further": it states the two observable
    facts — the page is linked from the one you submitted, and here is
    what it is labelled — and admits the page type is unknown.
    """
    label = (link_text or "").strip()[:60]
    if label:
        return (
            f'Linked from the page you submitted and labelled "{label}". '
            "Sitemyra could not classify this page type further."
        )
    segments = path_segments(url)
    tail = segments[-1] if segments else "the site root"
    return (
        f"Linked from the page you submitted at /{tail}. Sitemyra could not "
        "classify this page type further."
    )


def _relevance(kind: str, url: str, link_text: str) -> int:
    """Deterministic ordering heuristic (1-99). See module docstring.

    Capped at 99 on purpose: the submitted page owns relevance 100 and is
    identified separately by ``is_primary``, so a discovered page can never
    tie with it and be mistaken for the page the user pasted.
    """
    score = KIND_WEIGHTS.get(kind, KIND_WEIGHTS[OTHER])
    depth = len(path_segments(url))
    if depth <= 1:
        score += 4
    elif depth >= 5:
        score -= min(12, (depth - 4) * 4)
    if link_text:
        score += 3 if len(link_text) <= 40 else 0
    if kind in (LEGAL, SUPPORT, OTHER):
        score -= 10
    return max(1, min(99, score))


def discover_targets(url: str, content=None, content_type: str = "", facts: dict = None, limit: int = MAX_TARGETS):
    """Find other public pages on the same site worth monitoring.

    Only same-origin links are considered. Transactional, account and
    social links are excluded. The submitted page itself is never
    returned as a target.
    """
    facts = facts or {}
    if content is None:
        return []
    if isinstance(content, str):
        html = content
    else:
        html = decode_html(bytes(content or b""), content_type or "")
    soup = BeautifulSoup(html, "html.parser")

    submitted = normalize_url(url)
    base = facts.get("canonical_url", {}).get("value") or url
    seen = {submitted}
    targets = []

    for anchor in soup.find_all("a", href=True, limit=MAX_LINKS_SCANNED):
        href = anchor.get("href") or ""
        if not href or _is_external(href):
            continue
        candidate = absolute(base, href)
        normalized = normalize_url(candidate)
        if not normalized or normalized in seen:
            continue
        if not same_origin(url, normalized):
            continue
        if is_excluded_path(normalized):
            continue
        seen.add(normalized)
        kind, why = _classify_link(normalized, anchor.get_text(" ", strip=True))
        targets.append(
            {
                "url": normalized,
                "kind": kind,
                "label": _target_label(kind, normalized, anchor.get_text(" ", strip=True)),
                "why": why or KIND_SIGNALS.get(kind, KIND_SIGNALS[OTHER]),
                "confidence": "high" if why.startswith("The URL path") else "medium",
                "relevance": _relevance(kind, normalized, anchor.get_text(" ", strip=True)),
                "is_product": False,
                "is_primary": False,
            }
        )
        if len(targets) >= limit * 2:
            break

    targets.sort(key=lambda item: (-item["relevance"], len(item["url"])))
    return targets[:limit]


def _target_label(kind: str, url: str, link_text: str) -> str:
    segments = path_segments(url)
    tail = segments[-1] if segments else ""
    slug = tail.replace("-", " ").replace("_", " ").replace("%20", " ").strip()
    if link_text and 2 <= len(link_text.strip()) <= 60:
        return f"{KIND_LABELS.get(kind, KIND_SIGNALS[OTHER])} — {link_text.strip()}"
    if slug and len(slug) <= 60 and not slug.isdigit():
        return f"{KIND_LABELS.get(kind, KIND_LABELS_DEFAULT)} — {slug}"
    return f"{KIND_LABELS.get(kind, 'Page')} — {display_host(url)}"


KIND_LABELS_DEFAULT = "Page"


def build_targets(url: str, kind: str, confidence: str, rationale: str, facts: dict, related):
    """Assemble the submitted page plus discovered targets into one list.

    The submitted page is always first and carries its classification
    rationale, so the user can see *why* Sitemyra decided what it did.
    """
    primary_label = KIND_LABELS.get(kind, KIND_LABELS[OTHER])
    host = display_host(url)
    product_name = facts.get("name", {}).get("value")
    if kind == PRODUCT and product_name:
        primary_label = f"Product — {str(product_name)[:80]}"

    targets = [
        {
            "url": normalize_url(url),
            "kind": kind,
            "label": primary_label,
            "why": rationale or KIND_SIGNALS.get(kind, KIND_SIGNALS[OTHER]),
            "confidence": confidence,
            "relevance": 100,
            "is_product": kind == PRODUCT,
            "is_primary": True,
        }
    ]

    seen = {targets[0]["url"]}
    for target in related:
        if target["url"] in seen:
            continue
        seen.add(target["url"])
        entry = dict(target)
        entry["site"] = host
        targets.append(entry)
    return targets


def describe_site(url: str) -> str:
    return display_host(url)


def is_same_site_target(base_url: str, target_url: str) -> bool:
    return host_of(base_url) == host_of(target_url)
