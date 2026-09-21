import json
import os

from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions, serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import (
    BUSINESS,
    FREE,
    PLAN_LIMITS,
    PLAN_MRR_CENTS,
    PRO,
    get_or_create_subscription,
    get_plan_for_user,
    plan_limits,
)
from .stripe_utils import (
    is_price_configured,
    is_stripe_configured,
    price_id_for_plan,
    stripe_client,
)


def _billing_not_configured():
    return Response(
        {
            "detail": (
                "Billing is not configured on this server. "
                "Set STRIPE_SECRET_KEY (and price IDs) to enable checkout."
            ),
            "code": "billing_not_configured",
        },
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _stripe_error():
    return Response(
        {
            "detail": (
                "The payment provider returned an error. "
                "Please try again or contact support."
            ),
            "code": "stripe_error",
        },
        status=status.HTTP_502_BAD_GATEWAY,
    )


def _price_not_configured(plan):
    return Response(
        {
            "detail": (
                f"No Stripe price is configured for plan '{plan}'. "
                "Set STRIPE_PRICE_PRO / STRIPE_PRICE_BUSINESS."
            ),
            "code": "price_not_configured",
        },
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _dev_stub_allowed() -> bool:
    """Explicit dev-only stub gate. Never true in production."""
    import os

    from django.conf import settings

    return bool(settings.DEBUG) and (
        os.getenv("STRIPE_DEV_STUB", "0") == "1"
    )


class CheckoutSerializer(serializers.Serializer):
    plan = serializers.ChoiceField(choices=[PRO, BUSINESS])


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def subscription_status(request):
    sub = get_or_create_subscription(request.user)
    plan = get_plan_for_user(request.user)
    return Response(
        {
            "plan": plan,
            "status": sub.status,
            "mrr_cents": sub.mrr_cents,
            "current_period_end": sub.current_period_end,
            "cancel_at_period_end": sub.cancel_at_period_end,
            "limits": plan_limits(plan),
            "stripe_customer_id": sub.stripe_customer_id,
            "billing_configured": is_stripe_configured(),
        }
    )


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def plans(request):
    current = get_plan_for_user(request.user)
    return Response(
        {
            "current_plan": current,
            "billing_configured": is_stripe_configured(),
            "plans": [
                {"id": FREE, "name": "Free", "mrr_cents": 0, **PLAN_LIMITS[FREE]},
                {
                    "id": PRO,
                    "name": "Pro",
                    "mrr_cents": PLAN_MRR_CENTS[PRO],
                    **PLAN_LIMITS[PRO],
                },
                {
                    "id": BUSINESS,
                    "name": "Business",
                    "mrr_cents": PLAN_MRR_CENTS[BUSINESS],
                    **PLAN_LIMITS[BUSINESS],
                },
            ],
        }
    )


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def create_checkout(request):
    serializer = CheckoutSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    plan = serializer.validated_data["plan"]
    stripe = stripe_client()
    frontend = os.getenv("FRONTEND_URL", "http://localhost:3000")

    if stripe is None:
        if _dev_stub_allowed():
            # Explicit local-dev stub only (STRIPE_DEV_STUB=1 + DEBUG).
            # Never exposed in production.
            return Response(
                {
                    "checkout_url": (
                        f"{frontend}/dashboard/billing?checkout=stub&plan={plan}"
                    ),
                    "stub": True,
                    "plan": plan,
                },
                status=201,
            )
        return _billing_not_configured()

    sub = get_or_create_subscription(request.user)
    if not is_price_configured(plan):
        return _price_not_configured(plan)

    import logging

    logger = logging.getLogger(__name__)
    try:
        if not sub.stripe_customer_id:
            customer = stripe.Customer.create(email=request.user.email)
            sub.stripe_customer_id = customer.id
            sub.save(update_fields=["stripe_customer_id"])

        session = stripe.checkout.Session.create(
            customer=sub.stripe_customer_id,
            mode="subscription",
            line_items=[{"price": price_id_for_plan(plan), "quantity": 1}],
            success_url=f"{frontend}/dashboard/billing?checkout=success",
            cancel_url=f"{frontend}/dashboard/billing?checkout=cancelled",
            metadata={"user_id": str(request.user.id), "plan": plan},
        )
    except Exception:
        logger.exception("Stripe checkout failed")
        return _stripe_error()
    return Response({"checkout_url": session.url, "stub": False}, status=201)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def create_portal_session(request):
    stripe = stripe_client()
    frontend = os.getenv("FRONTEND_URL", "http://localhost:3000")
    sub = get_or_create_subscription(request.user)
    if stripe is None or not sub.stripe_customer_id:
        if stripe is None and _dev_stub_allowed():
            return Response(
                {"portal_url": f"{frontend}/dashboard/billing", "stub": True}
            )
        if stripe is None:
            return _billing_not_configured()
        return Response(
            {
                "detail": (
                    "No Stripe customer exists for this account yet. "
                    "Complete checkout first."
                ),
                "code": "no_stripe_customer",
            },
            status=status.HTTP_409_CONFLICT,
        )
    import logging

    logger = logging.getLogger(__name__)
    try:
        session = stripe.billing_portal.Session.create(
            customer=sub.stripe_customer_id,
            return_url=f"{frontend}/dashboard/billing",
        )
    except Exception:
        logger.exception("Stripe portal failed")
        return _stripe_error()
    return Response({"portal_url": session.url, "stub": False})


@csrf_exempt
def stripe_webhook(request):
    """Handle Stripe lifecycle events with immediate PostgreSQL sync.

    Security: production requires STRIPE_WEBHOOK_SECRET signature
    verification. Events are deduplicated by Stripe event ID
    (StripeWebhookEvent) and tenant-guarded — an event for one customer
    can never modify another customer's subscription.

    Supported events:
      - checkout.session.completed -> activate plan (active). Requires
        our checkout metadata (plan); sessions without it are ignored.
      - customer.subscription.created / .updated -> sync status/plan/MRR/period
      - customer.subscription.deleted (.canceled alias) -> downgrade to Free
      - invoice.payment_failed -> past_due (dunning grace, features kept)
      - invoice.paid / invoice.payment_succeeded -> recover past_due to active

    Tier limits resolve dynamically via ``plan_limits(plan)``, and any
    downgrade immediately pauses monitors beyond the new plan's
    ``max_monitors`` instead of deleting data.
    """
    import logging

    from django.db import transaction

    from .models import Subscription

    logger = logging.getLogger(__name__)

    payload = request.body
    sig = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    stripe = stripe_client()

    if not webhook_secret:
        # Never trust unsigned payloads in production.
        logger.warning("Stripe webhook rejected: STRIPE_WEBHOOK_SECRET is not set")
        from django.conf import settings as _settings

        dev_bypass = bool(_settings.DEBUG) and (
            os.getenv("STRIPE_DEV_SKIP_WEBHOOK_VERIFY", "0") == "1"
        )
        if not dev_bypass:
            # 503 in production (misconfiguration), 400 in dev without
            # the explicit bypass flag.
            if not _settings.DEBUG:
                return HttpResponse(status=503)
            return HttpResponse(status=400)
        try:
            event = json.loads(payload.decode() or "{}")
        except Exception:
            return HttpResponse(status=400)
    else:
        if stripe is None:
            # Secret set but library/key missing: cannot verify.
            logger.warning("Stripe webhook rejected: client unavailable for verify")
            return HttpResponse(status=503)
        try:
            import stripe as stripe_mod

            event = stripe_mod.Webhook.construct_event(
                payload, sig, webhook_secret
            )
        except Exception:
            logger.warning("Stripe webhook rejected: invalid signature")
            return HttpResponse(status=400)

    event_type = event.get("type", "")
    data = (event.get("data") or {}).get("object", {}) or {}
    event_id = str(event.get("id", "") or "")

    # Idempotency: Stripe redelivers until 2xx. Record IDs and ack
    # redeliveries without re-applying transitions.
    if event_id:
        from .models import StripeWebhookEvent

        _, created = StripeWebhookEvent.objects.get_or_create(
            event_id=event_id,
            defaults={"event_type": event_type},
        )
        if not created:
            logger.info("Stripe webhook redelivery ignored: %s", event_type)
            return HttpResponse(status=200)

    def _customer_matches(sub, customer_id: str) -> bool:
        """Tenant guard: never apply one customer's event to another."""
        if not customer_id:
            return True
        if not sub.stripe_customer_id:
            return True
        if sub.stripe_customer_id != customer_id:
            logger.warning(
                "Stripe event customer mismatch for subscription %s: ignored",
                sub.pk,
            )
            return False
        return True

    def find_sub():
        customer_id = data.get("customer", "")
        # checkout.session.completed: `id` is a cs_* id, subscription in
        # `subscription`; subscription events: `id` is sub_*.
        sub_id = data.get("id") or data.get("subscription", "")
        qs = Subscription.objects.select_related("user")
        if sub_id and str(sub_id).startswith("sub_"):
            hit = qs.filter(stripe_subscription_id=sub_id).first()
            if hit:
                return hit
        # invoice events carry subscription id under `subscription`.
        inv_sub = data.get("subscription", "")
        if inv_sub and str(inv_sub).startswith("sub_"):
            hit = qs.filter(stripe_subscription_id=inv_sub).first()
            if hit:
                return hit
        if customer_id and str(customer_id).startswith("cus_"):
            hit = qs.filter(stripe_customer_id=customer_id).first()
            if hit:
                return hit
        # Last resort: checkout metadata. Only used when no stored
        # customer/subscription matched (verified signature required to
        # reach this code in production).
        metadata = data.get("metadata") or {}
        user_id = metadata.get("user_id")
        if user_id:
            return Subscription.objects.filter(user_id=user_id).first()
        return None

    def _plan_from_subscription_object(obj):
        """Map Stripe subscription -> free/pro/business via price IDs."""
        try:
            items = (obj.get("items") or {}).get("data") or []
            price_ids = {
                ((item or {}).get("price") or {}).get("id", "")
                for item in items
            }
        except Exception:
            price_ids = set()
        pro_price = os.getenv("STRIPE_PRICE_PRO", "")
        biz_price = os.getenv("STRIPE_PRICE_BUSINESS", "")
        if biz_price and biz_price in price_ids:
            return BUSINESS
        if pro_price and pro_price in price_ids:
            return PRO
        # Fallbacks: explicit metadata plan, or single-price id match.
        meta_plan = ((obj.get("metadata") or {}).get("plan", "") or "").lower()
        if meta_plan in (PRO, BUSINESS):
            return meta_plan
        if len(price_ids) == 1:
            only = next(iter(price_ids))
            if only == biz_price and biz_price:
                return BUSINESS
            if only == pro_price and pro_price:
                return PRO
        return None

    def _parse_period_end(obj):
        ts = obj.get("current_period_end")
        if not ts:
            return None
        try:
            from datetime import datetime, timezone as dt_timezone

            return datetime.fromtimestamp(
                int(ts), tz=dt_timezone.utc
            )
        except Exception:
            return None

    def _normalize_status(stripe_status, current):
        allowed = {"active", "trialing", "past_due", "canceled", "incomplete"}
        if stripe_status in allowed:
            return stripe_status
        if stripe_status in ("incomplete_expired",):
            return "canceled"
        if stripe_status in ("unpaid", "paused"):
            return "past_due"
        return current

    def _enforce_monitor_limits(sub):
        from monitors.models import Monitor

        allowed = PLAN_LIMITS[sub.plan]["max_monitors"]
        excess = list(
            Monitor.objects.filter(user=sub.user, active=True)
            .order_by("created_at")
            .values_list("id", flat=True)[allowed:]
        )
        if excess:
            Monitor.objects.filter(id__in=excess).update(active=False)
        return len(excess)

    if event_type == "checkout.session.completed":
        sub = find_sub()
        metadata = data.get("metadata") or {}
        plan = (metadata.get("plan", "") or "").lower()
        if plan not in (PRO, BUSINESS):
            # Never grant a plan without our own checkout metadata.
            logger.warning(
                "checkout.session.completed without valid plan metadata: ignored"
            )
            return HttpResponse(status=200)
        if sub:
            if not _customer_matches(sub, data.get("customer", "")):
                return HttpResponse(status=200)
            with transaction.atomic():
                customer_id = data.get("customer", "") or sub.stripe_customer_id
                subscription_id = (
                    data.get("subscription", "")
                    or sub.stripe_subscription_id
                )
                sub.plan = plan
                sub.status = "active"
                sub.stripe_customer_id = customer_id
                sub.stripe_subscription_id = subscription_id
                sub.mrr_cents = PLAN_MRR_CENTS.get(plan, 0)
                sub.cancel_at_period_end = False
                # Best-effort period sync when live keys exist.
                if stripe is not None and subscription_id:
                    try:
                        live = stripe.Subscription.retrieve(subscription_id)
                        period = _parse_period_end(dict(live))
                        if period:
                            sub.current_period_end = period
                    except Exception:
                        pass
                sub.save()
        return HttpResponse(status=200)
    elif event_type == "invoice.payment_failed":
        # Dunning: mark past_due, keep features during grace period.
        sub = find_sub()
        if sub and _customer_matches(sub, data.get("customer", "")):
            with transaction.atomic():
                sub.status = "past_due"
                sub.save(update_fields=["status", "updated_at"])
        return HttpResponse(status=200)
    elif event_type in ("invoice.paid", "invoice.payment_succeeded"):
        # Recovery: a successful payment clears dunning state.
        sub = find_sub()
        if (
            sub
            and _customer_matches(sub, data.get("customer", ""))
            and sub.status in ("past_due", "incomplete")
        ):
            with transaction.atomic():
                sub.status = "active"
                sub.save(update_fields=["status", "updated_at"])
        return HttpResponse(status=200)
    elif event_type in (
        "customer.subscription.created",
        "customer.subscription.updated",
    ):
        sub = find_sub()
        if sub:
            if not _customer_matches(sub, data.get("customer", "")):
                return HttpResponse(status=200)
            with transaction.atomic():
                stripe_status = data.get("status", "")
                sub.status = _normalize_status(stripe_status, sub.status)
                mapped_plan = _plan_from_subscription_object(data)
                if mapped_plan:
                    sub.plan = mapped_plan
                # Keep MRR consistent with effective plan; canceled => 0.
                if sub.status == "canceled":
                    sub.plan = FREE
                    sub.mrr_cents = 0
                else:
                    sub.mrr_cents = PLAN_MRR_CENTS.get(sub.plan, 0)
                sub.cancel_at_period_end = bool(
                    data.get("cancel_at_period_end", False)
                )
                period = _parse_period_end(data)
                if period:
                    sub.current_period_end = period
                # Tenant guard: only adopt IDs that are empty or match.
                event_customer = data.get("customer", "")
                if event_customer and (
                    not sub.stripe_customer_id
                    or sub.stripe_customer_id == event_customer
                ):
                    sub.stripe_customer_id = event_customer
                event_sub_id = str(data.get("id", ""))
                if event_sub_id.startswith("sub_") and (
                    not sub.stripe_subscription_id
                    or sub.stripe_subscription_id == event_sub_id
                ):
                    sub.stripe_subscription_id = event_sub_id
                sub.save()
                _enforce_monitor_limits(sub)
        else:
            logger.warning("Stripe subscription event without local match: %s", event_type)
        return HttpResponse(status=200)
    elif event_type in ("customer.subscription.deleted", "customer.subscription.canceled"):
        # Graceful downgrade: revert to Free, keep data, pause excess monitors.
        sub = find_sub()
        if sub and _customer_matches(sub, data.get("customer", "")):
            with transaction.atomic():
                sub.plan = FREE
                sub.status = "canceled"
                sub.mrr_cents = 0
                sub.stripe_subscription_id = ""
                sub.cancel_at_period_end = False
                sub.current_period_end = None
                sub.save()
                _enforce_monitor_limits(sub)
        return HttpResponse(status=200)

    return HttpResponse(status=200)
