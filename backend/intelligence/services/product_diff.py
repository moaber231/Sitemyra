"""Product snapshot diffing, severity classification and explanation.

**Pure module.** Given two extracted product states it produces the
timeline rows Sitemyra alerts on, plus the structured "what changed /
why it may matter / what to check / basis / confidence" block.

Everything here is deterministic and rule-based on purpose. Competitive
intelligence that invents a competitor's price is worse than one that says
"not detected", so Phase 1 ships **no** model call on this path — see
Phase 3 of `docs/INTELLIGENCE-ROADMAP.md` for how optional AI narration
layers on top of exactly these records without ever replacing them.

Each change records the rule that produced it in ``basis`` so the user can
always audit why a change was rated the way it was.
"""

from decimal import Decimal, InvalidOperation

# --------------------------------------------------------------------------
# Severity ladder
# --------------------------------------------------------------------------

INFORMATIONAL = "informational"
MINOR = "minor"
IMPORTANT = "important"
CRITICAL = "critical"

SEVERITY_RANK = {INFORMATIONAL: 0, MINOR: 1, IMPORTANT: 2, CRITICAL: 3}
SEVERITY_LABELS = {
    INFORMATIONAL: "Informational",
    MINOR: "Minor",
    IMPORTANT: "Important",
    CRITICAL: "Critical",
}

# --------------------------------------------------------------------------
# Categories
# --------------------------------------------------------------------------

PRICING = "pricing"
PRODUCT = "product"
FEATURES = "features"
AVAILABILITY = "availability"
CONTENT = "content"
REVIEWS = "reviews"
MARKETING = "marketing"

# field -> (label, category, severity for a plain "some value changed")
TRACKED_FIELDS = {
    "price": ("Price", PRICING, IMPORTANT),
    "list_price": ("List price", PRICING, MINOR),
    "currency": ("Currency", PRICING, IMPORTANT),
    "availability": ("Availability", AVAILABILITY, IMPORTANT),
    "name": ("Product name", PRODUCT, MINOR),
    "description": ("Product description", CONTENT, MINOR),
    "brand": ("Brand", PRODUCT, MINOR),
    "sku": ("SKU", PRODUCT, INFORMATIONAL),
    "condition": ("Condition", PRODUCT, INFORMATIONAL),
    "rating": ("Rating", REVIEWS, MINOR),
    "review_count": ("Review count", REVIEWS, MINOR),
    "variants": ("Variants", PRODUCT, IMPORTANT),
    "badges": ("Badges & promotions", MARKETING, MINOR),
    "bundles": ("Bundles", PRODUCT, MINOR),
    "images": ("Images", CONTENT, INFORMATIONAL),
    "specs": ("Specifications", FEATURES, MINOR),
    "shipping": ("Shipping information", PRODUCT, MINOR),
    "price_valid_until": ("Offer validity", PRICING, INFORMATIONAL),
}

# Fields compared as ordered collections / mappings.
_SEQUENCE_FIELDS = ("variants", "badges", "bundles", "images")
_MAPPING_FIELDS = ("specs", "shipping")
_DECIMAL_FIELDS = ("price", "list_price", "rating")

MAX_EVIDENCE_RAW = 400


# --------------------------------------------------------------------------
# Normalisation helpers
# --------------------------------------------------------------------------


def _decimal(value):
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _text(value):
    if value is None:
        return ""
    return str(value)


def _sequence(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return [str(value)]


def _mapping(value):
    if isinstance(value, dict):
        return {str(key): str(item) for key, item in value.items()}
    return {}


def _comparable(field_name, value):
    if field_name in _DECIMAL_FIELDS:
        return _decimal(value)
    if field_name in _SEQUENCE_FIELDS:
        return sorted(_sequence(value))
    if field_name in _MAPPING_FIELDS:
        return _mapping(value)
    if value is None:
        return ""
    if isinstance(value, (list, tuple, dict)):
        return sorted(str(item) for item in value)
    return str(value).strip()


def _render(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value[:8])
    if isinstance(value, dict):
        return ", ".join(f"{key}: {item}" for key, item in list(value.items())[:8])
    return str(value)


def _percent_change(before, after):
    """Signed percentage change, or ``None`` when it is not meaningful."""
    before_value = _decimal(before)
    after_value = _decimal(after)
    if before_value is None or after_value is None:
        return None
    if before_value == 0:
        return None
    return ((after_value - before_value) / before_value) * Decimal(100)


# --------------------------------------------------------------------------
# Severity rules
# --------------------------------------------------------------------------


def _severity_for_price(before, after, basis):
    change = _percent_change(before, after)
    if change is None:
        return (MINOR, f"Price changed from {_render(before)} to {_render(after)}.")
    magnitude = abs(change)
    direction = "increased" if change > 0 else "decreased"
    if magnitude >= Decimal(20):
        return (
            IMPORTANT,
            f"Price {direction} by {magnitude.quantize(Decimal('0.1'))}% "
            f"({_render(before)} → {_render(after)}).",
        )
    if magnitude >= Decimal(10):
        return (
            MINOR,
            f"Price {direction} by {magnitude.quantize(Decimal('0.1'))}% "
            f"({_render(before)} → {_render(after)}).",
        )
    return (INFORMATIONAL, f"Price {direction} by {magnitude.quantize(Decimal('0.01'))}%.")


def _severity_for_availability(before, after, basis):
    before_state = _text(before).strip()
    after_state = _text(after).strip()
    if before_state in ("in_stock", "low_stock") and after_state in ("out_of_stock", "discontinued"):
        return (
            CRITICAL,
            f"Availability moved from {before_state.replace('_', ' ')} to "
            f"{after_state.replace('_', ' ')}.",
        )
    if before_state in ("in_stock", "low_stock") and after_state == "backorder":
        return (IMPORTANT, "The product moved to backorder.")
    if before_state == "in_stock" and after_state == "low_stock":
        return (IMPORTANT, "Availability moved from in stock to low stock.")
    if before_state == "low_stock" and after_state == "in_stock":
        return (INFORMATIONAL, "Availability recovered from low stock to in stock.")
    if after_state in ("out_of_stock", "discontinued"):
        return (IMPORTANT, f"Availability is now {after_state.replace('_', ' ')}.")
    if after_state == "preorder" and before_state not in ("preorder",):
        return (INFORMATIONAL, "The product is now available for preorder.")
    return (MINOR, f"Availability changed from {before_state} to {after_state}.")


def _severity_for_review_count(before, after, basis):
    change = _percent_change(before, after)
    if change is None:
        return (MINOR, "Review count changed.")
    if change <= Decimal(-5):
        return (
            IMPORTANT,
            f"Published review count fell by {abs(change).quantize(Decimal('0.1'))}%.",
        )
    if change >= Decimal(10):
        return (INFORMATIONAL, f"Published review count rose by {change.quantize(Decimal('0.1'))}%.")
    return (INFORMATIONAL, "Published review count changed.")


def _severity_for_variants(before, after, basis):
    before_set = {item.strip().lower() for item in _sequence(before) if str(item).strip()}
    after_set = {item.strip().lower() for item in _sequence(after) if str(item).strip()}
    removed = before_set - after_set
    added = after_set - before_set
    if removed and not added:
        return (IMPORTANT, f"{len(removed)} published variant(s) are no longer listed.")
    if added and not removed:
        return (MINOR, f"{len(added)} new variant(s) were added.")
    if removed and added:
        return (MINOR, f"{len(removed)} variant(s) removed and {len(added)} added.")
    return (MINOR, "Variant list changed.")


def _severity_for_badges(before, after, basis):
    before_set = {item.strip().lower() for item in _sequence(before)}
    after_set = {item.strip().lower() for item in _sequence(after)}
    added = sorted(after_set - before_set)
    removed = sorted(before_set - after_set)
    parts = []
    if added:
        parts.append("added " + ", ".join(added[:4]))
    if removed:
        parts.append("removed " + ", ".join(removed[:4]))
    return (MINOR, "Promotional badges " + "; ".join(parts) + "." if parts else "Badges changed.")


def _severity_for_specs(before, after, basis):
    before_map = _mapping(before)
    after_map = _mapping(after)
    added = sorted(set(after_map) - set(before_map))
    removed = sorted(set(before_map) - set(after_map))
    changed = sorted(
        key
        for key in set(before_map) & set(after_map)
        if before_map[key] != after_map[key]
    )
    parts = []
    if added:
        parts.append(f"{len(added)} specification(s) added")
    if removed:
        parts.append(f"{len(removed)} specification(s) removed")
    if changed:
        parts.append(f"{len(changed)} specification value(s) changed")
    return (MINOR, "Specifications — " + "; ".join(parts) + "." if parts else "Specifications changed.")


_RULE_FOR_FIELD = {
    "price": _severity_for_price,
    "list_price": _severity_for_price,
    "availability": _severity_for_availability,
    "review_count": _severity_for_review_count,
    "variants": _severity_for_variants,
    "badges": _severity_for_badges,
    "specs": _severity_for_specs,
}


# --------------------------------------------------------------------------
# "Why it may matter" — phrased as an observation, never as advice
# --------------------------------------------------------------------------

_WHY_BY_CATEGORY = {
    PRICING: (
        "This is a change to a publicly advertised price. It shifts the price "
        "positioning customers see on the page."
    ),
    AVAILABILITY: (
        "This is a change to what the business currently offers for sale. It "
        "affects what a customer can buy right now."
    ),
    PRODUCT: (
        "This is a change to what the product is called or what it includes. "
        "It changes how the offering is presented."
    ),
    FEATURES: (
        "This is a change to the published capability or specification list."
    ),
    REVIEWS: (
        "This is a change to the published rating or review count shown to "
        "visitors."
    ),
    MARKETING: (
        "This is a change to the promotional presentation of the page."
    ),
    CONTENT: (
        "This is a change to the page copy that visitors read."
    ),
}

_CHECK_BY_CATEGORY = {
    PRICING: (
        "Compare the full price list, not just this product — page-level "
        "prices can move with promotions or regional pricing."
    ),
    AVAILABILITY: (
        "Open the source page and confirm the availability wording before "
        "acting on it."
    ),
    PRODUCT: (
        "Check whether the change is a rename, a repackaging, or a different "
        "product entirely."
    ),
    FEATURES: "Read the current feature list before comparing it with your own.",
    REVIEWS: (
        "Rating and review counts are frequently updated in bulk by review "
        "platforms; treat a single change as weak evidence."
    ),
    MARKETING: (
        "Promotional badges are often short-lived; check whether the "
        "underlying price also moved."
    ),
    CONTENT: "Read the current page copy to understand the context of the change.",
}


# --------------------------------------------------------------------------
# Diff
# --------------------------------------------------------------------------


def _change(
    field_name,
    before,
    after,
    severity,
    category,
    basis,
    detail,
    source_url="",
    detected_at=None,
    methods=None,
):
    return {
        "field": field_name,
        "label": TRACKED_FIELDS.get(field_name, (field_name.title(), CONTENT, MINOR))[0],
        "before": _render(before),
        "after": _render(after),
        "severity": severity,
        "category": category,
        "basis": detail,
        "rule": basis,
        "source_url": source_url,
        "detected_at": detected_at.isoformat() if hasattr(detected_at, "isoformat") else (detected_at or ""),
        "methods": methods or {},
    }


def diff_snapshots(previous, current, source_url="", detected_at=None):
    """Compare two extracted product states.

    ``previous`` may be ``None`` (first observation) — an empty diff is
    returned so a first capture never produces a false "changed" alert.

    Both arguments are the raw ``{field: {value, method, raw}}`` maps
    produced by :mod:`intelligence.services.page_facts`.
    """
    if not previous:
        return []

    changes = []
    for field_name in TRACKED_FIELDS:
        if field_name not in current and field_name not in previous:
            continue

        before_entry = previous.get(field_name) or {}
        after_entry = current.get(field_name) or {}
        before = before_entry.get("value")
        after = after_entry.get("value")

        # A field that appears or disappears entirely is reported only when
        # it had a real value before: extraction flakiness must not read as
        # "the competitor removed their rating".
        if field_name not in previous and before in (None, "", [], {}):
            continue

        before_comparable = _comparable(field_name, before)
        after_comparable = _comparable(field_name, after)

        if field_name in previous and field_name not in current:
            if before_comparable in ("", None, [], {}):
                continue
            if not _is_disappearance(field_name, after):
                continue

        if before_comparable == after_comparable:
            continue

        label, category, default_severity = TRACKED_FIELDS[field_name]
        rule = _RULE_FOR_FIELD.get(field_name)
        if rule is not None:
            severity, detail = rule(before_comparable, after_comparable, "")
        else:
            severity = default_severity
            detail = f"{label} changed."

        methods = {
            "before": before_entry.get("method", ""),
            "after": after_entry.get("method", ""),
        }
        # If the extraction path changed, the observation is weaker — say so
        # instead of presenting it as a competitor action.
        if methods["before"] and methods["after"] and methods["before"] != methods["after"]:
            severity = INFORMATIONAL if severity != CRITICAL else severity
            detail = (
                f"{detail} (read from {methods['before']} before and "
                f"{methods['after']} now — confirm on the page)"
            )

        changes.append(
            _change(
                field_name,
                before,
                after,
                severity,
                category,
                f"rule:{field_name}",
                detail,
                source_url=source_url,
                detected_at=detected_at,
                methods=methods,
            )
        )

    changes.sort(key=lambda item: (-SEVERITY_RANK.get(item["severity"], 0), item["field"]))
    return changes


def _is_disappearance(field_name, after) -> bool:
    """A missing field counts as removed only for these fields."""
    return field_name in ("price", "availability", "variants", "badges", "bundles", "specs")


# --------------------------------------------------------------------------
# Explanation block
# --------------------------------------------------------------------------

_CONFIDENCE_BY_METHOD = {
    "jsonld": "high",
    "microdata": "high",
    "opengraph": "medium",
    "attribute": "medium",
    "heuristic": "low",
    "html": "medium",
    "": "medium",
}


def confidence_for(changes) -> str:
    """Overall confidence, derived from how the values were read."""
    if not changes:
        return "low"
    methods = set()
    for change in changes:
        methods.add(change.get("methods", {}).get("after", ""))
    methods.discard("")
    if not methods:
        return "medium"
    levels = {_CONFIDENCE_BY_METHOD.get(method, "medium") for method in methods}
    if "low" in levels:
        return "low"
    if levels == {"high"}:
        return "high"
    return "medium"


def explain(changes, product_name="", source_url="", detected_at=None):
    """Build the structured explanation shown in the UI and the alert.

    Returns a dict with ``what_changed``, ``why_it_may_matter``,
    ``what_to_check``, ``confidence``, ``basis`` and ``evidence``.
    The text deliberately stops at describing the public change and
    pointing the user at the source; it never prescribes a business
    decision.
    """
    if not changes:
        return {
            "what_changed": "No product fields changed on this check.",
            "why_it_may_matter": "",
            "what_to_check": "",
            "confidence": "medium",
            "basis": [],
            "evidence": [],
        }

    top = changes[0]
    label = product_name or top.get("label") or "This product"

    if len(changes) == 1:
        headline = f"{label}: {top['basis']}"
    else:
        # Lead with the count, then quote the rules that fired. The rule
        # text already carries the before/after numbers, so the headline
        # stays readable without repeating any field label.
        headline = f"{label}: {len(changes)} published fields changed. " + " ".join(
            change["basis"] for change in changes[:3] if change.get("basis")
        )

    categories = []
    for change in changes:
        if change["category"] not in categories:
            categories.append(change["category"])

    why_parts = []
    for category in categories[:2]:
        text = _WHY_BY_CATEGORY.get(category)
        if text and text not in why_parts:
            why_parts.append(text)
    if not why_parts:
        why_parts.append("This is a change to a publicly published page field.")

    check_parts = []
    for category in categories[:2]:
        text = _CHECK_BY_CATEGORY.get(category)
        if text and text not in check_parts:
            check_parts.append(text)

    evidence = []
    for change in changes[:8]:
        entry = {
            "field": change["field"],
            "label": change["label"],
            "before": change["before"],
            "after": change["after"],
            "severity": change["severity"],
            "category": change["category"],
            "rule": change["rule"],
            "basis": change["basis"],
        }
        if change.get("source_url"):
            entry["source_url"] = change["source_url"]
        if change.get("detected_at"):
            entry["detected_at"] = change["detected_at"]
        evidence.append(entry)

    return {
        "what_changed": headline,
        "why_it_may_matter": " ".join(why_parts),
        "what_to_check": " ".join(check_parts),
        "confidence": confidence_for(changes),
        "basis": [change["rule"] for change in changes[:8]],
        "evidence": evidence,
    }


# --------------------------------------------------------------------------
# Summary lines (alerts, feed, digests)
# --------------------------------------------------------------------------


def format_change_line(change, currency="") -> str:
    """One human line for an alert or feed row."""
    label = change.get("label", "Field")
    before = change.get("before", "")
    after = change.get("after", "")
    prefix = ""
    if change.get("field") in ("price", "list_price") and currency:
        prefix = f"{currency} "
    if change["field"] == "availability":
        return f"Availability: {before.replace('_', ' ')} → {after.replace('_', ' ')}"
    if not before and after:
        return f"{label} added: {prefix}{after}"
    if before and not after:
        return f"{label} no longer published (was {prefix}{before})"
    return f"{label}: {prefix}{before} → {prefix}{after}"


def summarize(changes, currency="", limit: int = 3):
    """Short multi-line summary used in alert subjects and the feed."""
    lines = [format_change_line(change, currency) for change in changes[:limit]]
    remaining = len(changes) - len(lines)
    if remaining > 0:
        lines.append(f"+{remaining} more field(s) changed")
    return "\n".join(lines)


def discount_percent(list_price, price):
    """Discount percentage, or ``None`` when it cannot be computed."""
    list_value = _decimal(list_price)
    price_value = _decimal(price)
    if list_value is None or price_value is None:
        return None
    if list_value <= 0 or price_value >= list_value:
        return None
    return ((list_value - price_value) / list_value) * Decimal(100)


def severity_of(changes) -> str:
    if not changes:
        return INFORMATIONAL
    return max((change["severity"] for change in changes), key=lambda item: SEVERITY_RANK.get(item, 0))


def category_of(changes) -> str:
    if not changes:
        return CONTENT
    return changes[0].get("category", CONTENT)
