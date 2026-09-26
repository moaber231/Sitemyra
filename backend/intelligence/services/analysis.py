"""URL analysis orchestration — the only module in the intelligence app
that performs network access.

Flow: validate → fetch (reusing the monitoring fetcher, so SSRF rules and
redirect re-validation are identical to a normal check) → extract facts →
classify → discover same-site targets → persist.

Caching: an analysis younger than :data:`ANALYSIS_TTL` is returned as-is.
This is what makes "paste the same competitor URL again" free, and it keeps
the free tier from burning requests on a loop.
"""

import logging
from datetime import timedelta

from django.utils import timezone

from monitors.services.fetcher import FetchError, SecurityError, fetch_url

from .classify import build_targets, classify_page, discover_targets
from .page_facts import extract_page_facts, summarize_facts
from .urls import normalize_url

logger = logging.getLogger(__name__)

# How long an analysis stays fresh. Competitor pages change slowly
# relative to how often a user re-pastes the same URL during onboarding.
ANALYSIS_TTL_MINUTES = 360

DEFAULT_TIMEOUT_SECONDS = 15
MAX_ANALYSIS_TIMEOUT_SECONDS = 30


class AnalysisError(Exception):
    """User-facing analysis failure with a safe, plain message."""

    def __init__(self, message: str, code: str = "analysis_failed"):
        super().__init__(message)
        self.message = message
        self.code = code


def clean_submitted_url(raw: str) -> str:
    """Normalize user input, accepting bare hostnames."""
    if not raw or not str(raw).strip():
        raise AnalysisError("Enter a URL to analyse.", "url_required")
    normalized = normalize_url(str(raw).strip())
    if not normalized:
        raise AnalysisError(
            "That does not look like a valid http or https URL.",
            "url_invalid",
        )
    return normalized


def fetch_for_analysis(url: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS):
    """Fetch a page for analysis using the monitoring fetcher."""
    timeout = min(max(1, int(timeout_seconds or DEFAULT_TIMEOUT_SECONDS)), MAX_ANALYSIS_TIMEOUT_SECONDS)
    try:
        return fetch_url(url, timeout_seconds=timeout)
    except SecurityError as exc:
        raise AnalysisError(
            "Sitemyra only monitors publicly reachable web pages, so this "
            "address cannot be analysed.",
            "url_blocked",
        ) from exc
    except FetchError as exc:
        raise AnalysisError(
            f"Sitemyra could not load that page: {exc}",
            "fetch_failed",
        ) from exc
    except Exception as exc:  # never leak internals to the user
        logger.exception("intelligence analysis fetch error")
        raise AnalysisError(
            "Sitemyra could not load that page.",
            "fetch_failed",
        ) from exc


def analyze_content(url: str, content, content_type: str = ""):
    """Pure half of the analysis: bytes in, facts + targets out."""
    facts = extract_page_facts(content, content_type, url)
    kind, confidence, rationale = classify_page(url, facts)
    related = discover_targets(url, content, content_type, facts)
    targets = build_targets(url, kind, confidence, rationale, facts, related)
    return {
        "url": normalize_url(url),
        "page_kind": kind,
        "page_kind_label": _kind_label(kind),
        "classification_confidence": confidence,
        "classification_rationale": rationale,
        "facts": facts,
        "summary": summarize_facts(facts),
        "product_detected": bool(facts.get("product_detected")),
        "targets": targets,
    }


def _kind_label(kind: str) -> str:
    from .classify import KIND_LABELS

    return KIND_LABELS.get(kind, "Page")


def run_analysis(url: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> dict:
    """Fetch and analyse without touching the database (public demo path)."""
    normalized = clean_submitted_url(url)
    result = fetch_for_analysis(normalized, timeout_seconds)
    if result.status_code and result.status_code >= 400:
        raise AnalysisError(
            f"That page returned HTTP {result.status_code}. Sitemyra only "
            "monitors pages that are publicly available.",
            f"http_{result.status_code}",
        )
    analysis = analyze_content(normalized, result.content, result.content_type)
    analysis["status_code"] = result.status_code
    analysis["response_time_ms"] = result.response_time_ms
    return analysis


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------


def is_fresh(record, ttl_minutes: int = ANALYSIS_TTL_MINUTES) -> bool:
    if record is None or record.status != "ok":
        return False
    if record.fetched_at is None:
        return False
    age = timezone.now() - record.fetched_at
    return age.total_seconds() < ttl_minutes * 60


def store_analysis(user, analysis: dict, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS):
    """Persist an analysis and its discovered targets for later activation.

    Returns ``(UrlAnalysis, created)``. A fresh analysis for the same
    normalized URL is reused rather than re-fetched.
    """
    from ..models import DiscoveredTarget, UrlAnalysis

    normalized = analysis["url"]
    existing = (
        UrlAnalysis.objects.filter(user=user, normalized_url=normalized)
        .order_by("-fetched_at")
        .first()
    )
    if is_fresh(existing):
        return existing, False

    record = UrlAnalysis.objects.create(
        user=user,
        url=analysis.get("url", normalized),
        normalized_url=normalized,
        status="ok",
        page_kind=analysis.get("page_kind", "other"),
        classification_confidence=analysis.get("classification_confidence", "low"),
        classification_rationale=analysis.get("classification_rationale", ""),
        facts=analysis.get("facts", {}),
        summary=analysis.get("summary", {}),
        product_detected=bool(analysis.get("product_detected")),
        status_code=analysis.get("status_code"),
        response_time_ms=analysis.get("response_time_ms"),
        fetched_at=timezone.now(),
        expires_at=timezone.now() + timedelta(minutes=ANALYSIS_TTL_MINUTES),
        error="",
    )
    DiscoveredTarget.objects.bulk_create(
        [
            DiscoveredTarget(
                analysis=record,
                url=target["url"],
                kind=target["kind"],
                label=target["label"],
                why=target.get("why", ""),
                confidence=target.get("confidence", "medium"),
                relevance=int(target.get("relevance", 0)),
                is_product=bool(target.get("is_product")),
                is_primary=bool(target.get("is_primary")),
            )
            for target in analysis.get("targets", [])
        ]
    )
    return record, True


def public_view(analysis: dict, target_limit: int = 5) -> dict:
    """Redacted projection for the unauthenticated marketing demo.

    Contains only what is already public at the submitted URL. No user
    identity, no persisted record, no full link inventory.
    """
    facts = analysis.get("summary", {})
    headline = {}
    for key in ("name", "brand", "price", "list_price", "currency", "availability", "rating", "review_count"):
        if facts.get(key) not in (None, "", [], {}):
            headline[key] = facts[key]

    targets = analysis.get("targets", [])
    return {
        "url": analysis.get("url", ""),
        "page_kind": analysis.get("page_kind", "other"),
        "page_kind_label": analysis.get("page_kind_label", "Page"),
        "classification_confidence": analysis.get("classification_confidence", "low"),
        "classification_rationale": analysis.get("classification_rationale", ""),
        "product_detected": bool(analysis.get("product_detected")),
        "facts": headline,
        "found_count": len(targets),
        "targets": [
            {
                "kind": target["kind"],
                "label": target["label"],
                "url": target["url"],
                "relevance": target.get("relevance", 0),
            }
            for target in targets[:target_limit]
        ],
    }
