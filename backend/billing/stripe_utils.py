import os

from django.conf import settings


def stripe_client():
    """Return a configured stripe module or None when not installed/keyless."""
    api_key = os.getenv("STRIPE_SECRET_KEY", "")
    if not api_key:
        return None
    try:
        import stripe
    except ImportError:
        return None
    stripe.api_key = api_key
    return stripe


def is_stripe_configured() -> bool:
    """True only when live Stripe calls are actually possible."""
    return stripe_client() is not None


def price_id_for_plan(plan: str) -> str:
    mapping = {
        "pro": os.getenv("STRIPE_PRICE_PRO", ""),
        "business": os.getenv("STRIPE_PRICE_BUSINESS", ""),
    }
    price_id = (mapping.get(plan, "") or "").strip()
    # Never fabricate a placeholder: missing price config must surface as
    # an explicit 503, not a doomed Stripe API call.
    if not price_id or "placeholder" in price_id:
        return ""
    return price_id


def is_price_configured(plan: str) -> bool:
    return bool(price_id_for_plan(plan))
