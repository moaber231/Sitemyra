"""URL helpers for the intelligence layer.

Pure functions, no network, no database. Everything here is deliberately
conservative: registrable-domain extraction uses a small public-suffix
list rather than shipping `tldextract`, so same-origin / same-site checks
stay predictable and dependency-free.
"""

from urllib.parse import urljoin, urlparse, urlunparse

# Multi-part public suffixes we care about. This is NOT the full Public
# Suffix List — it is the small set of suffixes that make naive
# "last two labels" registrable-domain extraction wrong for the markets
# Sitemyra's customers actually monitor.
_MULTI_LABEL_SUFFIXES = frozenset(
    {
        "co.uk",
        "org.uk",
        "ac.uk",
        "gov.uk",
        "co.jp",
        "or.jp",
        "ne.jp",
        "com.au",
        "net.au",
        "org.au",
        "co.nz",
        "com.br",
        "com.mx",
        "com.ar",
        "co.za",
        "co.in",
        "com.tr",
        "com.sg",
        "com.hk",
        "co.kr",
    }
)

# Paths that are never worth monitoring: they are transactional, private,
# or legally/technically volatile for reasons unrelated to the market.
EXCLUDED_PATH_SEGMENTS = frozenset(
    {
        "account",
        "accounts",
        "auth",
        "basket",
        "cart",
        "checkout",
        "confirm",
        "cookie-consent",
        "cookies",
        "dashboard",
        "disclaimer",
        "download",
        "downloads",
        "forgot-password",
        "gdpr",
        "imprint",
        "legal",
        "login",
        "logout",
        "my-account",
        "order",
        "orders",
        "password",
        "privacy",
        "profile",
        "refund-policy",
        "register",
        "returns",
        "search",
        "session",
        "signin",
        "signout",
        "signup",
        "terms",
        "unsubscribe",
        "wishlist",
    }
)

DEFAULT_PORTS = {"http": 80, "https": 443}


def normalize_url(raw: str) -> str:
    """Canonical form used as the analysis cache key.

    Lowercases scheme/host, drops the fragment (it never reaches the
    server), strips a default port and a trailing empty query. Path case
    and query string are preserved because they change the response.
    """
    if not raw:
        return ""
    candidate = raw.strip()
    if not candidate:
        return ""
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    parsed = urlparse(candidate)
    scheme = (parsed.scheme or "https").lower()
    if scheme not in ("http", "https"):
        return ""
    host = (parsed.hostname or "").lower()
    if not host:
        return ""
    try:
        port = parsed.port
    except ValueError:
        # A non-numeric port ("javascript:alert(1)" parses as one) is a
        # malformed URL, not a server error. The fetcher's own validator
        # would reject it later; here we just refuse to normalize it.
        return ""
    netloc = host
    if port is not None and DEFAULT_PORTS.get(scheme) != port:
        netloc = f"{host}:{port}"
    path = parsed.path or "/"
    return urlunparse((scheme, netloc, path, parsed.params, parsed.query, ""))


def registrable_domain(host_or_url: str) -> str:
    """Best-effort eTLD+1. Empty string when the host is unusable."""
    if not host_or_url:
        return ""
    candidate = host_or_url.strip()
    if "://" in candidate:
        candidate = urlparse(candidate).hostname or ""
    else:
        candidate = urlparse(f"//{candidate}").hostname or ""
    candidate = candidate.lower().strip(".")
    if not candidate or candidate.replace(".", "").isdigit():
        return ""
    labels = candidate.split(".")
    if len(labels) <= 2:
        return candidate
    tail_two = ".".join(labels[-2:])
    if tail_two in _MULTI_LABEL_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return tail_two


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def same_site(left: str, right: str) -> bool:
    """True when both URLs share a registrable domain (subdomains count)."""
    left_domain = registrable_domain(left)
    right_domain = registrable_domain(right)
    return bool(left_domain) and left_domain == right_domain


def same_origin(left: str, right: str) -> bool:
    left_parsed = urlparse(left)
    right_parsed = urlparse(right)
    if not left_parsed.hostname or not right_parsed.hostname:
        return False
    left_scheme = (left_parsed.scheme or "").lower()
    right_scheme = (right_parsed.scheme or "").lower()
    if left_scheme != right_scheme:
        return False
    left_port = left_parsed.port or DEFAULT_PORTS.get(left_scheme)
    right_port = right_parsed.port or DEFAULT_PORTS.get(right_scheme)
    return (
        left_parsed.hostname.lower() == right_parsed.hostname.lower()
        and left_port == right_port
    )


def absolute(base: str, href: str) -> str:
    """Resolve a possibly-relative href against a base URL."""
    if not href:
        return ""
    return urljoin(base, href.strip())


def path_segments(url: str) -> list:
    path = urlparse(url).path or "/"
    return [segment for segment in path.split("/") if segment]


def is_excluded_path(url: str) -> bool:
    """Transactional / private / no-signal paths we never propose."""
    segments = [segment.lower() for segment in path_segments(url)]
    if not segments:
        return False
    for segment in segments:
        if segment in EXCLUDED_PATH_SEGMENTS:
            return True
    query = (urlparse(url).query or "").lower()
    return "cart" in query or "checkout" in query


def display_host(url: str) -> str:
    """Host without a leading ``www.`` — used in labels and UI copy."""
    host = host_of(url)
    if host.startswith("www."):
        return host[4:]
    return host
