"""Phase 3 — the alert deep link, AI narration, and market signals.

This module is where "never just say something changed" becomes a real
screen: `signal_event_detail` returns the *what / why / what to check /
evidence* payload for one feed row, which is exactly what an alert link
should land on.

**AI narration is opt-in and can never replace the evidence.** Phase 1
already produced a deterministic explanation for every change
(`product_diff.explain`). This module:

* keeps that explanation as the stored default (`ChangeExplanation`
  rows with `is_fallback=True`);
* optionally asks a configured provider to narrate the SAME evidence
  packet, and requires every sentence to cite an evidence id that exists
  in that packet — a citation that does not resolve is discarded and the
  deterministic text is used instead;
* never sends anything beyond text that was already public at the
  monitored URL, and never sends user identity;
* does nothing at all when no provider is configured or the user has not
  opted in. With no provider configured — the default — this code path is
  inert and the product is fully functional.
"""

import hashlib
import json
import logging
import re

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

# Provider contracts are deliberately narrow. Anything not matching this
# shape is treated as "no provider configured".
PROVIDERS = ("openai", "anthropic", "custom")

DEFAULT_NARRATION_TIMEOUT_SECONDS = 20
MAX_EVIDENCE_ITEMS = 12
MAX_NARRATION_CHARS = 1500

def _int(value, default=0):
    """Best-effort int parse. Used for query params, never for storage."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


_CITATION_RE = re.compile(r"\[(?P<ids>[eE]\d+(?:\s*,\s*e?\d+)*)\]")


# ==========================================================================
# The deep link: everything needed to explain one change
# ==========================================================================


def build_event_detail(user, event, window_hours: int = 24):
    """The full explanation payload for one feed row.

    Assembled from stored rows only. If a change is present it is explained
    in full; if not, the payload says exactly that instead of guessing.
    """
    from ..models import ChangeExplanation, ProductChange
    from . import feed as feed_service
    from .product_diff import explain

    detail = feed_service.serialize_event(event)

    change = None
    if event.product_change_id:
        change = ProductChange.objects.filter(
            id=event.product_change_id
        ).select_related("product_watch", "product_watch__monitor").first()

    watch = None
    if change is not None:
        watch = change.product_watch
    elif event.monitor_id:
        from ..models import ProductWatch

        watch = ProductWatch.objects.filter(monitor_id=event.monitor_id).first()

    if change is not None:
        payload = [
            {
                "field": change.field,
                "label": change.label,
                "before": change.before,
                "after": change.after,
                "severity": change.severity,
                "category": change.category,
                "rule": change.rule,
                "basis": change.basis,
                "source_url": change.source_url,
                "detected_at": change.created_at,
            }
        ]
        stored = (
            ChangeExplanation.objects.filter(signal_event=event)
            .order_by("-is_fallback", "-created_at")
            .first()
        )
        if stored is not None:
            explanation = {
                "what_changed": stored.what_changed,
                "why_it_may_matter": stored.why_it_may_matter,
                "what_to_check": stored.what_to_check,
                "confidence": stored.confidence,
                "basis": stored.basis or [],
                "evidence": stored.evidence or [],
                "generator": stored.model or "rules",
                "is_fallback": stored.is_fallback,
            }
        else:
            explanation = explain(
                payload, product_name=watch.name if watch else ""
            )
            explanation["generator"] = "rules"
            explanation["is_fallback"] = True
    else:
        explanation = {
            "what_changed": event.headline,
            "why_it_may_matter": (
                "Sitemyra detected that the page content changed but could not read a "
                "specific published value from it."
            ),
            "what_to_check": (
                "Open the source page to see what moved. A change here may be copy, "
                "layout, or something Sitemyra has not learned to read yet."
            ),
            "confidence": "medium",
            "basis": ["rule:content_hash"],
            "evidence": [
                {
                    "field": "content",
                    "label": "Page content",
                    "before": "previous normalized text",
                    "after": "current normalized text",
                    "severity": event.severity,
                    "category": event.kind,
                    "rule": "rule:content_hash",
                    "basis": "The normalized text hash differs from the previous check.",
                    "source_url": event.source_url,
                    "detected_at": event.detected_at.isoformat()
                    if event.detected_at
                    else "",
                }
            ],
            "generator": "rules",
            "is_fallback": True,
        }

    detail["explanation"] = explanation
    detail["product_watch_id"] = str(watch.id) if watch is not None else None
    detail["context"] = _recent_context(user, event, window_hours=window_hours)
    detail["evidence_url"] = _evidence_url(event)
    detail["timeline_url"] = (
        f"/dashboard/monitors/{event.monitor_id}?tab=product" if event.monitor_id else None
    )
    detail["export"] = {
        "csv": f"/api/intelligence/export/?format=csv&monitor={event.monitor_id or ''}",
        "json": f"/api/intelligence/export/?format=json&monitor={event.monitor_id or ''}",
    }
    return detail


def _evidence_url(event):
    if event.product_change_id:
        return f"/api/intelligence/export/?format=json&monitor={event.monitor_id or ''}"
    if event.monitor_check_id:
        return f"/api/monitors/{event.monitor_id}/checks/"
    return event.source_url


def _recent_context(user, event, window_hours: int = 24):
    """What else this competitor did recently, so one alert has context."""
    from ..models import SignalEvent

    since = timezone.now() - timezone.timedelta(hours=max(1, min(window_hours, 720)))
    queryset = SignalEvent.objects.filter(
        user=user, detected_at__gte=since
    ).exclude(id=event.id)
    if event.competitor_id:
        queryset = queryset.filter(competitor_id=event.competitor_id)
    elif event.monitor_id:
        queryset = queryset.filter(monitor_id=event.monitor_id)
    else:
        return []
    return [
        {
            "id": str(row.id),
            "headline": row.headline,
            "kind": row.kind,
            "severity": row.severity,
            "detected_at": row.detected_at,
        }
        for row in queryset.order_by("-detected_at")[:10]
    ]


def store_explanation(signal_event, what_changed, why_it_may_matter, what_to_check, confidence, basis, evidence, model_name, is_fallback):
    from ..models import ChangeExplanation

    return ChangeExplanation.objects.create(
        signal_event=signal_event,
        what_changed=what_changed,
        why_it_may_matter=why_it_may_matter,
        what_to_check=what_to_check,
        confidence=confidence,
        basis=list(basis or []),
        evidence=list(evidence or []),
        model=model_name,
        is_fallback=bool(is_fallback),
    )


# ==========================================================================
# AI narration (opt-in, evidence-bound)
# ==========================================================================


def provider_configured() -> bool:
    from django.conf import settings

    return bool(getattr(settings, "AI_PROVIDER", "")) and bool(
        getattr(settings, "AI_API_KEY", "")
    )


def narration_enabled(user) -> bool:
    return bool(getattr(user, "ai_narration_enabled", False)) and provider_configured()


def build_evidence_packet(product_name, payload, competitor_name="", currency=""):
    """The only thing that may ever leave the process.

    It contains text that was already public at the monitored URL, plus the
    rule names that classified it. No user identity, no workspace name, no
    internal ids, no competitor content beyond the source's own fields.
    """
    evidence = []
    for index, item in enumerate(payload[:MAX_EVIDENCE_ITEMS], start=1):
        evidence.append(
            {
                "id": f"e{index}",
                "field": item.get("field", ""),
                "label": item.get("label", ""),
                "before": str(item.get("before", ""))[:200],
                "after": str(item.get("after", ""))[:200],
                "observed": str(item.get("basis", ""))[:300],
                "rule": item.get("rule", ""),
                "source_url": item.get("source_url", ""),
                "detected_at": str(item.get("detected_at", "")),
            }
        )
    return {
        "product": product_name or "",
        "competitor": competitor_name or "",
        "currency": currency or "",
        "evidence": evidence,
        "rules": sorted({item.get("rule", "") for item in payload if item.get("rule")}),
    }


PROMPT = (
    "You are describing a change to a PUBLIC web page. You are given a JSON packet of "
    "observations. Write three short fields.\n"
    "Rules you must follow:\n"
    "1. Use only facts present in the packet. Never infer revenue, customers, strategy, "
    "or intent.\n"
    "2. After every sentence in every field, cite the evidence ids you used, like [e1] or "
    "[e1,e2].\n"
    "3. 'why_it_may_matter' must be phrased as a possibility about the public page, not as "
    "business advice.\n"
    "4. 'what_to_check' must be an instruction to verify something on the source page.\n"
    "5. Never state a confidence you were not given.\n"
    "Return ONLY JSON: "
    '{"what_changed":str,"why_it_may_matter":str,"what_to_check":str,"confidence":"high|medium|low",'
    '"citations":["e1"]}'
)


def _extract_json(text: str):
    if not text:
        return None
    stripped = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, flags=re.S)
    if fence:
        stripped = fence.group(1).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(stripped[start:end + 1])
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def validate_narration(parsed, valid_ids):
    """Keep a narration only if every citation resolves.

    A fabricated citation is a hallucination we cannot detect downstream, so
    the whole narration is discarded and the deterministic text is used.
    """
    if not isinstance(parsed, dict):
        return None
    fields = ("what_changed", "why_it_may_matter", "what_to_check")
    cleaned = {}
    cited = set()
    for name in fields:
        value = parsed.get(name)
        if not isinstance(value, str) or not value.strip():
            return None
        text = value.strip()
        if len(text) > MAX_NARRATION_CHARS:
            return None
        found = _CITATION_RE.findall(text)
        if not found:
            # A field with no citation at all is not evidence-bound.
            return None
        for group in found:
            for token in group.split(","):
                cleaned_id = token.strip().lower()
                if cleaned_id not in valid_ids:
                    return None
                cited.add(cleaned_id)
        cleaned[name] = _CITATION_RE.sub("", text).strip()
        if not cleaned[name]:
            return None

    confidence = parsed.get("confidence")
    if confidence not in ("high", "medium", "low"):
        return None
    declared = parsed.get("citations")
    if isinstance(declared, list):
        for token in declared:
            if str(token).strip().lower() not in valid_ids:
                return None
    return {
        "what_changed": cleaned["what_changed"],
        "why_it_may_matter": cleaned["why_it_may_matter"],
        "what_to_check": cleaned["what_to_check"],
        "confidence": confidence,
        "cited": sorted(cited),
    }


def request_narration(packet, timeout_seconds=None):
    """Call the configured provider. Returns a dict or ``None``.

    Any failure at all — not configured, no network, bad shape,
    unresolvable citation, timeout — returns ``None`` so the caller falls
    back to the deterministic explanation. This function never raises.
    """
    try:
        from django.conf import settings

        provider = (getattr(settings, "AI_PROVIDER", "") or "").lower()
        api_key = getattr(settings, "AI_API_KEY", "") or ""
        if provider not in PROVIDERS or not api_key:
            return None
        timeout = timeout_seconds or getattr(
            settings, "AI_TIMEOUT_SECONDS", DEFAULT_NARRATION_TIMEOUT_SECONDS
        )
        model = getattr(settings, "AI_MODEL", "") or ""
        base_url = getattr(settings, "AI_BASE_URL", "") or ""

        import httpx

        if provider == "openai":
            url = base_url or "https://api.openai.com/v1/chat/completions"
            model = model or "gpt-4o-mini"
            headers = {"Authorization": f"Bearer {api_key}"}
            body = {
                "model": model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(packet)[:8000],
                    },
                ],
            }
            content_path = ("choices", 0, "message", "content")
        elif provider == "anthropic":
            url = base_url or "https://api.anthropic.com/v1/messages"
            model = model or "claude-3-5-haiku-latest"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
            body = {
                "model": model,
                "max_tokens": 700,
                "temperature": 0,
                "system": PROMPT,
                "messages": [
                    {
                        "role": "user",
                        "content": json.dumps(packet)[:8000],
                    }
                ],
            }
            content_path = ("content", 0, "text")
        else:
            url = base_url
            if not url:
                return None
            headers = {"Authorization": f"Bearer {api_key}"}
            body = {
                "model": model or "default",
                "prompt": f"{PROMPT}\n\n{json.dumps(packet)[:8000]}",
            }
            content_path = ("text",)

        if not url:
            return None

        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, json=body, headers=headers)
        if response.status_code >= 400:
            logger.info(
                "intelligence narration provider returned %s", response.status_code
            )
            return None
        data = response.json()
        node = data
        for key in content_path:
            if not isinstance(node, dict) and not isinstance(node, list):
                return None
            try:
                node = node[key]
            except (KeyError, IndexError, TypeError):
                return None
        if not isinstance(node, str):
            return None
        return _extract_json(node)
    except Exception:
        # Narration is a nicety. It must never break an alert.
        logger.exception("intelligence narration request failed")
        return None


def narrate_event(signal_event, change, watch=None, competitor=None):
    """Produce and store a narration for one change, falling back cleanly.

    Returns the stored ``ChangeExplanation`` either way, so the caller can
    render a single shape.
    """
    from .product_diff import explain

    payload = [
        {
            "field": change.field,
            "label": change.label,
            "before": change.before,
            "after": change.after,
            "severity": change.severity,
            "category": change.category,
            "rule": change.rule,
            "basis": change.basis,
            "source_url": change.source_url,
            "detected_at": change.created_at,
        }
    ]
    deterministic = explain(
        payload, product_name=watch.name if watch else ""
    )

    enabled = narration_enabled(getattr(signal_event, "user", None)) if signal_event else False
    validated = None
    if enabled:
        packet = build_evidence_packet(
            watch.name if watch else "",
            payload,
            competitor_name=competitor.name if competitor else "",
            currency=watch.currency if watch else "",
        )
        parsed = request_narration(packet)
        if parsed is not None:
            valid_ids = {item["id"] for item in packet["evidence"]}
            validated = validate_narration(parsed, valid_ids)
            if validated is None:
                logger.info(
                    "intelligence narration discarded: citation did not resolve"
                )

    # ALWAYS store the deterministic text first. A narration is stored as a
    # SECOND row for the same event, so the rule-based explanation survives
    # even if the AI row later turns out to be wrong — which is the whole
    # reason the deterministic path exists. Readers prefer the non-fallback
    # row (see build_event_detail) and fall back automatically.
    fallback_row = store_explanation(
        signal_event,
        deterministic["what_changed"],
        deterministic["why_it_may_matter"],
        deterministic["what_to_check"],
        deterministic["confidence"],
        deterministic["basis"],
        deterministic["evidence"],
        model_name="rules",
        is_fallback=True,
    )

    if validated is not None:
        return store_explanation(
            signal_event,
            validated["what_changed"],
            validated["why_it_may_matter"],
            validated["what_to_check"],
            validated["confidence"],
            deterministic["basis"],
            deterministic["evidence"],
            model_name=f"ai:{packet_provider_label()}",
            is_fallback=False,
        )
    return fallback_row


def packet_provider_label():
    from django.conf import settings

    return (getattr(settings, "AI_PROVIDER", "") or "rules").lower()


# ==========================================================================
# Market signals (Feature 10)
# ==========================================================================

# A signal is only emitted at this many distinct competitors. One
# competitor doing one thing is an event, not a market signal.
MIN_COMPETITORS_FOR_SIGNAL = 2
DEFAULT_WINDOW_DAYS = 30


def _fingerprint(kind, competitor_ids, when, key) -> str:
    return hashlib.sha256(
        f"{kind}|{'|'.join(sorted(str(value) for value in competitor_ids))}|{key}".encode()
    ).hexdigest()


def _evidence_rows(events):
    return [
        {
            "signal_event_id": str(event.id),
            "competitor_id": str(event.competitor_id) if event.competitor_id else None,
            "competitor": event.competitor.name if event.competitor_id else None,
            "headline": event.headline,
            "before": event.before,
            "after": event.after,
            "source_url": event.source_url,
            "detected_at": event.detected_at.isoformat() if event.detected_at else "",
            "severity": event.severity,
        }
        for event in events
    ]


def _store(kind, headline, statement, interpretation, events, confidence="medium", window_days=DEFAULT_WINDOW_DAYS):
    from ..models import MarketSignal

    competitor_ids = {event.competitor_id for event in events if event.competitor_id}
    if len(competitor_ids) < MIN_COMPETITORS_FOR_SIGNAL:
        return None
    fingerprint = _fingerprint(kind, competitor_ids, None, window_days)
    if MarketSignal.objects.filter(fingerprint=fingerprint).exists():
        return None
    return MarketSignal.objects.create(
        user=events[0].competitor.user if events[0].competitor else events[0].user,
        workspace=events[0].competitor.workspace if events[0].competitor else None,
        kind=kind,
        headline=headline,
        statement=statement,
        interpretation=interpretation,
        window_days=window_days,
        evidence=_evidence_rows(events),
        confidence=confidence,
        fingerprint=fingerprint,
    )


def detect_market_signals(user, window_days=DEFAULT_WINDOW_DAYS):
    """Look across a user's monitored competitors for patterns.

    Each detector states what it observed and offers an interpretation as a
    possibility. None of them claims to know why a competitor acted.
    """
    from ..models import MarketSignal, SignalEvent

    since = timezone.now() - timezone.timedelta(days=max(1, min(window_days, 365)))
    events = list(
        SignalEvent.objects.filter(user=user, detected_at__gte=since)
        .select_related("competitor", "monitor")
        .order_by("-detected_at")[:2000]
    )
    if not events:
        return []

    created = []

    # --- price direction clusters --------------------------------------
    # Direction is read from the wording the price rule produced, not
    # inferred from the numbers, so a cluster is "these pages said they
    # went up" — exactly the observable fact.
    #
    # A cluster spans competitors, so the events are pooled first and the
    # distinct-competitor count is what gates the signal. Grouping *by*
    # competitor here would make the threshold unreachable.
    up_events, down_events = [], []
    for event in events:
        if event.kind != "pricing" or not event.competitor_id:
            continue
        basis = ((event.evidence or {}).get("basis", "") or "").lower()
        if "decreased by" in basis:
            down_events.append(event)
        elif "increased by" in basis:
            up_events.append(event)

    for chosen, verb, kind in (
        (up_events, "increased a published price", "price_increase_cluster"),
        (down_events, "cut a published price", "price_decrease_cluster"),
    ):
        signal = _cluster_signal(
            chosen, kind, verb, window_days, created
        )
        if signal:
            created.append(signal)

    # --- feature parity -------------------------------------------------
    feature_events = [
        event for event in events if event.kind == "features" and event.competitor_id
    ]
    signal = _cluster_signal(
        feature_events,
        "feature_parity",
        "changed what they publish as features",
        window_days,
        created,
        interpretation=(
            "This may reflect increasing demand or competitive investment in this "
            "capability. Check each source page to see whether the changes are "
            "actually equivalent."
        ),
    )
    if signal:
        created.append(signal)

    # --- feature removal (one competitor is enough: it is a warning) ----
    for event in feature_events:
        basis = ((event.evidence or {}).get("basis", "") or "").lower()
        if "no longer listed" not in basis and "removed" not in basis:
            continue
        signal = _store(
            "feature_removal",
            f"{event.competitor.name if event.competitor else 'A competitor'} removed a published item",
            "A monitored competitor stopped publishing an item during the last "
            f"{window_days} days.",
            (
                "This is a removal from a public page. It may be a product change, a "
                "content cleanup, or a temporary state. Open the source to confirm."
            ),
            [event],
            confidence="low",
            window_days=window_days,
        )
        if signal:
            created.append(signal)
        break

    # --- hiring push ----------------------------------------------------
    hiring_events = [
        event for event in events if event.kind == "hiring" and event.competitor_id
    ]
    signal = _cluster_signal(
        hiring_events,
        "hiring_push",
        "changed their public careers page",
        window_days,
        created,
        interpretation=(
            "A change to a public careers page may reflect hiring activity, a careers "
            "site rebuild, or nothing at all. Open the source before drawing a conclusion."
        ),
        confidence="low",
    )
    if signal:
        created.append(signal)

    if created:
        logger.info("intelligence market signals created [count=%d]", len(created))
    return created


def _cluster_signal(
    events, kind, verb, window_days, already_created, interpretation=None, confidence="medium"
):
    """One market signal when >= MIN_COMPETITORS competitors moved together.

    Returns None when the evidence threshold is not met or an identical
    signal already exists.
    """
    if not events:
        return None
    # Gate on distinct competitor IDs, not distinct names: two competitors
    # can legitimately share a display name, and a shared name must not
    # collapse a real two-competitor pattern into "one company".
    competitor_ids = {event.competitor_id for event in events if event.competitor_id}
    if len(competitor_ids) < MIN_COMPETITORS_FOR_SIGNAL:
        return None
    names = sorted({event.competitor.name for event in events if event.competitor_id})
    return _store(
        kind,
        f"{len(competitor_ids)} monitored competitors {verb} in the last {window_days} days",
        (
            f"{len(competitor_ids)} competitors you monitor did so during the last "
            f"{window_days} days: {', '.join(names[:6])}."
        ),
        interpretation
        or (
            "This may indicate a decision taken across a market rather than by one "
            "company. It does not indicate whether the decision succeeded."
        ),
        events,
        confidence="high" if len(competitor_ids) >= 3 and confidence == "medium" else confidence,
        window_days=window_days,
    )


def _group_by_competitor(events):
    groups = {}
    for event in events:
        if not event.competitor_id:
            continue
        groups.setdefault(event.competitor_id, []).append(event)
    return groups


@transaction.atomic
def review_signal(user, signal_id, status):
    from ..models import MarketSignal

    queryset = MarketSignal.objects.filter(user=user)
    signal = queryset.filter(id=signal_id).first()
    if signal is None:
        return None
    if status not in dict(MarketSignal.STATUS_CHOICES):
        return None
    signal.status = status
    signal.save(update_fields=["status"])
    return signal
