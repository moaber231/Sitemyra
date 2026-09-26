"""Feature 2 — proposing competitors, with the evidence attached.

The user submits **their own** site. Sitemyra looks at what that page
already links to and publishes, and proposes candidates. That is the
honest version of "competitor discovery" without a paid data broker, a
search API, or any scraping of a third party's private systems:

* a page the user calls "alternatives", "competitors", "compare" or
  "versus" is the site telling us who it competes with;
* publicly declared category and capability keywords give the factual
  signals behind each candidate.

**Every candidate is a proposal.** Nothing is monitored until the user
approves it, and every reason attached to a candidate is a verifiable
statement they can click through to.

If we cannot find public signals, we say so. We never invent candidates.
"""

import logging
import re
from urllib.parse import urljoin, urlparse

from django.db import transaction
from django.utils import timezone

from .classify import FEATURES, OTHER, PRODUCT, _segment_tokens
from .urls import display_host, normalize_url, registrable_domain, same_origin, same_site

logger = logging.getLogger(__name__)

MAX_CANDIDATES = 12

# Page kinds that mean "this site names its competitors here".
_ALTERNATIVES_TOKENS = ("alternatives", "alternative", "competitors", "competitor", "compare", "comparison", "versus", "vs")

# Word-boundary keyword classification into a relationship. Deliberately a
# short, auditable list — the reasons we emit quote what was matched.
_DIRECT_HINTS = ("competitor", "competitors", "alternative", "alternatives", "versus", "vs", "compare")
_ADJACENT_HINTS = ("integrations", "integrate", "partners", "partnership", "ecosystem", "connect", "directory", "app-store", "apps")

_STOPWORDS = frozenset(
    {
        "the", "and", "for", "with", "your", "our", "you", "are", "was", "that",
        "this", "from", "all", "any", "can", "how", "what", "why", "who", "not",
        "but", "get", "use", "new", "one", "two", "per", "has", "have", "its",
    }
)

# Generic e-commerce/SaaS words that on their own prove nothing about
# competitive relationship. Excluded from the capability keywords.
_CATEGORY_NOISE = frozenset(
    {
        "product", "products", "service", "services", "home", "page", "index",
        "html", "http", "https", "www", "com", "net", "org", "login", "signup",
        "cart", "account", "privacy", "terms", "cookie", "cookies", "blog",
        "news", "about", "contact", "search", "category", "categories",
    }
)


def _keywords(text, limit=12):
    if not text:
        return []
    words = re.findall(r"[a-z][a-z0-9+\-]{2,}", str(text).lower())
    counts = {}
    for word in words:
        if word in _STOPWORDS or word in _CATEGORY_NOISE or len(word) < 3:
            continue
        counts[word] = counts.get(word, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [word for word, _count in ordered[:limit]]


def classify_relationship(url: str, link_text: str, page_kind: str, shared_keywords):
    """Return ``(relationship, reasons)`` from observable signals only."""
    reasons = []
    haystack = f"{url} {link_text}".lower()
    tokens = set()
    for segment in re.split(r"[^a-z0-9]+", haystack):
        if segment:
            tokens.add(segment)

    if tokens & set(_DIRECT_HINTS) or page_kind in ("comparison",):
        relationship = "direct"
        reasons.append(
            "The page is linked from a section Sitemyra recognises as naming "
            "alternatives or competitors."
        )
    elif tokens & set(_ADJACENT_HINTS):
        relationship = "adjacent"
        reasons.append(
            "The page is linked from an integrations, partners or ecosystem "
            "section."
        )
    else:
        relationship = "alternative"
        reasons.append("The page is publicly linked from the site you submitted.")

    if shared_keywords:
        reasons.append(
            "Shared capability keywords: "
            + ", ".join(f"“{word}”" for word in shared_keywords[:6])
            + "."
        )
    if page_kind:
        reasons.append(f"Page type Sitemyra detected: {page_kind}.")
    return relationship, reasons


def _shared_keywords(own_text, candidate_text, limit=6):
    own = set(_keywords(own_text, limit=60))
    other = set(_keywords(candidate_text, limit=60))
    shared = sorted(own & other)
    return shared[:limit]


# Path/label tokens that mean "this page names who else does the same job".
_COMPARISON_TOKENS = (
    "alternatives",
    "alternative",
    "competitors",
    "competitor",
    "compare",
    "comparison",
    "versus",
    "vs",
    "why-switch",
    "switch",
)

# Path/label tokens that mean "this link leaves the site to talk to
# somebody about the article", not "this is a company we compete with".
_SOCIAL_TOKENS = (
    "follow", "share", "twitter", "facebook", "linkedin", "instagram",
    "youtube", "tiktok", "pinterest", "reddit", "mastodon", "bluesky",
    "subscribe", "newsletter", "rss", "feed", "whatsapp", "telegram",
)

# Hosts that are never a competitor: social, app stores, review sites and
# payment/checkout infrastructure.
_NEVER_A_COMPETITOR_HOSTS = frozenset(
    {
        "facebook.com", "twitter.com", "x.com", "linkedin.com", "instagram.com",
        "youtube.com", "tiktok.com", "pinterest.com", "reddit.com", "github.com",
        "gitlab.com", "apple.com", "play.google.com", "google.com", "bing.com",
        "trustpilot.com", "g2.com", "capterra.com", "stripe.com", "paypal.com",
        "shopify.com", "wix.com", "squarespace.com", "mailchimp.com", "hubspot.com",
        "zapier.com", "producthunt.com", "crunchbase.com", "wikipedia.org",
    }
)

# Path tokens that mean "this outbound link is a partner, not a rival".
_PARTNER_TOKENS = (
    "integrations", "integrate", "partners", "partnership", "ecosystem",
    "connect", "apps", "app-store", "addons", "extensions", "marketplace",
)

MAX_HUBS = 2
MAX_CANDIDATES = 12


def _tokens_of(url, label=""):
    text = f"{url} {label}".lower()
    return set(re.split(r"[^a-z0-9]+", text)) - {""}


def _is_comparison_hub(target) -> bool:
    return bool(_tokens_of(target.get("url", ""), target.get("label", "")) & set(_COMPARISON_TOKENS))


def _is_partner_link(url, label="") -> bool:
    return bool(_tokens_of(url, label) & set(_PARTNER_TOKENS))


def _is_never_a_competitor(url) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    for blocked in _NEVER_A_COMPETITOR_HOSTS:
        if host == blocked or host.endswith("." + blocked):
            return True
    return False


def _external_links(html, base_url, own_domain):
    """Same-origin-external links from a page, deduped by domain."""
    from .page_facts import decode_html

    soup = _soup(html)
    found = []
    seen = {own_domain}
    for anchor in soup.find_all("a", href=True, limit=800):
        href = (anchor.get("href") or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        domain = registrable_domain(absolute)
        if not domain or domain in seen:
            continue
        if same_site(own_domain and f"https://{own_domain}" or base_url, absolute):
            continue
        if _is_never_a_competitor(absolute):
            continue
        if _tokens_of(absolute, anchor.get_text(" ", strip=True)) & set(_SOCIAL_TOKENS):
            continue
        seen.add(domain)
        label = anchor.get_text(" ", strip=True)
        found.append(
            {
                "url": normalize_url(absolute),
                "domain": domain,
                "label": label,
                "partner": _is_partner_link(absolute, label),
            }
        )
        if len(found) >= 60:
            break
    return found


def _soup(html):
    from bs4 import BeautifulSoup

    return BeautifulSoup(html or "", "html.parser")


@transaction.atomic
def discover_candidates(user, submitted_url, content=None, content_type="", facts=None, workspace=None, timeout_seconds=15):
    """Propose competitors for a site the user owns.

    The flow is honest about what public pages can actually tell us:

    1. read the site the user submitted;
    2. find its own "alternatives" / "compare" page — a page where a
       business names who else does the same job;
    3. read the **external** links on that page: those are the candidates;
    4. optionally fetch each candidate to compute genuinely shared
       capability keywords.

    External links found directly on the submitted page (an integrations or
    partners page, typically) count too, classified as *adjacent* rather
    than *direct*.

    Returns ``(own_competitor, candidates)``. Nothing is monitored here.

    If the site publishes no comparison page and no outbound tool links, we
    return an empty list and the API says so. We never invent a candidate.
    """
    from ..models import Competitor, CompetitorCandidate

    from .analysis import AnalysisError, analyze_content, clean_submitted_url, fetch_for_analysis
    from .competitors import name_for_domain

    normalized = clean_submitted_url(submitted_url)
    own_domain = registrable_domain(normalized)

    if content is None:
        try:
            result = fetch_for_analysis(normalized, timeout_seconds=timeout_seconds)
        except AnalysisError:
            raise
        if result.status_code and result.status_code >= 400:
            raise AnalysisError(
                f"That page returned HTTP {result.status_code}.", "http_error"
            )
        content = result.content
        content_type = result.content_type

    payload = analyze_content(normalized, content, content_type)
    facts = payload.get("facts") or {}
    summary = payload.get("summary") or {}
    own_text = " ".join(
        str(value)
        for value in (
            summary.get("name"),
            summary.get("page_title"),
            summary.get("page_description"),
            summary.get("description"),
        )
        if value
    )

    from .page_facts import decode_html

    html = decode_html(bytes(content or b""), content_type or "")

    own = Competitor.objects.filter(user=user, domain=own_domain).first()
    if own is None:
        own = Competitor.objects.create(
            user=user,
            workspace=workspace,
            name=str(summary.get("name") or name_for_domain(own_domain))[:200],
            homepage_url=f"https://{own_domain}",
            domain=own_domain,
            relationship=Competitor.RELATIONSHIP_TRACKED,
            relationship_reasons=["This is the site you told Sitemyra to compare against."],
            first_seen_at=timezone.now(),
        )

    # --- step 2: find the site's own comparison page(s) -----------------
    hubs = [target for target in payload.get("targets", []) if _is_comparison_hub(target)]
    hubs = hubs[:MAX_HUBS]

    proposals = []
    seen_domains = {own_domain}
    hub_urls = {normalize_url(target["url"]) for target in hubs}

    # --- step 3: external links on the comparison page(s) ---------------
    for hub in hubs:
        try:
            page = fetch_for_analysis(hub["url"], timeout_seconds=min(timeout_seconds, 10))
        except AnalysisError:
            logger.info("intelligence comparison page unreadable [url=%s]", hub["url"])
            continue
        if page.status_code and page.status_code >= 400:
            continue
        hub_html = decode_html(bytes(page.content or b""), page.content_type or "")
        for link in _external_links(hub_html, hub["url"], own_domain):
            if link["domain"] in seen_domains:
                continue
            seen_domains.add(link["domain"])
            link["source_page"] = hub["url"]
            link["from_comparison_page"] = True
            proposals.append(link)
            if len(proposals) >= MAX_CANDIDATES:
                break
        if len(proposals) >= MAX_CANDIDATES:
            break

    # --- external links on the submitted page itself (partners/adjacent) -
    if len(proposals) < MAX_CANDIDATES:
        for link in _external_links(html, normalized, own_domain):
            if link["domain"] in seen_domains:
                continue
            seen_domains.add(link["domain"])
            link["source_page"] = normalized
            link["from_comparison_page"] = False
            proposals.append(link)
            if len(proposals) >= MAX_CANDIDATES:
                break

    if not proposals:
        return own, []

    existing_domains = set(
        Competitor.objects.filter(
            user=user, domain__in=[link["domain"] for link in proposals]
        ).values_list("domain", flat=True)
    )

    created = []
    for link in proposals:
        shared = []
        candidate_text = ""
        if link["domain"] not in existing_domains:
            try:
                page = fetch_for_analysis(link["url"], timeout_seconds=8)
                if not (page.status_code and page.status_code >= 400):
                    page_facts = extract_candidate_facts(page.content, page.content_type)
                    candidate_text = " ".join(
                        str(value)
                        for value in (
                            page_facts.get("name", {}).get("value"),
                            page_facts.get("page_title", {}).get("value"),
                            page_facts.get("page_description", {}).get("value"),
                        )
                        if value
                    )
            except Exception:
                # An unreadable candidate page means NO capability keywords,
                # never an invented one.
                logger.info("intelligence candidate page unreadable [domain=%s]", link["domain"])
        shared = _shared_keywords(own_text, candidate_text)

        if link["from_comparison_page"] and not link["partner"]:
            relationship = "direct"
            reasons = [
                f'{link["domain"]} is listed as a {link["label"] or "tool"} on the page '
                f"{link['source_page']}, which the site publishes as a comparison page."
            ]
        else:
            relationship = "adjacent"
            reasons = [
                f'{link["domain"]} is publicly linked from {link["source_page"]}, the page you '
                "submitted to Sitemyra."
            ]
        if shared:
            reasons.append(
                "Shared capability keywords: "
                + ", ".join(f"“{word}”" for word in shared[:6])
                + "."
            )

        confidence = "high" if shared else ("medium" if relationship == "direct" else "low")
        candidate, _made = CompetitorCandidate.objects.update_or_create(
            competitor=own,
            url=link["url"][:1000],
            defaults={
                "domain": link["domain"],
                "relationship": relationship,
                "reasons": reasons,
                "confidence": confidence,
            },
        )
        created.append(candidate)

    return own, created[:MAX_CANDIDATES]


def extract_candidate_facts(content, content_type=""):
    from .page_facts import extract_page_facts

    return extract_page_facts(content, content_type)
