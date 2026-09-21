import uuid

from django.conf import settings
from django.db import models


FREE = "free"
PRO = "pro"
BUSINESS = "business"
PLAN_CHOICES = ((FREE, "Free"), (PRO, "Pro"), (BUSINESS, "Business"))

# MRR in cents per plan (used for metrics + graceful downgrade math).
PLAN_MRR_CENTS = {FREE: 0, PRO: 1900, BUSINESS: 4900}

# Usage-based limits enforced per active subscription tier.
# Marketed tiers (frontend reads these directly via /api/billing/plans/):
# Free 3 URLs / 15m / 7d — Pro $19 25 URLs / 5m / 30d — Business $49 100 URLs / 1m / 90d.
PLAN_LIMITS = {
    FREE: {
        "max_monitors": 3,
        "min_interval_seconds": 900,  # 15m
        "max_alert_channels": 1,
        "history_days": 7,
    },
    PRO: {
        "max_monitors": 25,
        "min_interval_seconds": 300,  # 5m
        "max_alert_channels": 5,
        "history_days": 30,
    },
    BUSINESS: {
        "max_monitors": 100,
        "min_interval_seconds": 60,  # 1m
        "max_alert_channels": 50,
        "history_days": 90,
    },
}


class Subscription(models.Model):
    STATUS_CHOICES = (
        ("active", "Active"),
        ("trialing", "Trialing"),
        ("past_due", "Past due"),
        ("canceled", "Canceled"),
        ("incomplete", "Incomplete"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default=FREE)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="active"
    )
    stripe_customer_id = models.CharField(max_length=120, blank=True, default="")
    stripe_subscription_id = models.CharField(
        max_length=120, blank=True, default=""
    )
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    mrr_cents = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} -> {self.plan} ({self.status})"


class StripeWebhookEvent(models.Model):
    """Processed Stripe event IDs for idempotent webhook handling.

    Stripe redelivers events until a 2xx is returned. Recording IDs lets
    us acknowledge redeliveries without re-applying state transitions.
    """

    event_id = models.CharField(max_length=120, unique=True)
    event_type = models.CharField(max_length=80, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.event_type} ({self.event_id})"


def get_or_create_subscription(user) -> Subscription:
    sub, _ = Subscription.objects.get_or_create(
        user=user, defaults={"plan": FREE, "status": "active", "mrr_cents": 0}
    )
    return sub


def get_plan_for_user(user) -> str:
    if user.is_superuser:
        return BUSINESS
    try:
        sub = user.subscription
    except Subscription.DoesNotExist:
        return FREE
    # Only paid-in-good-standing states unlock paid entitlements.
    # `incomplete` (initial payment never completed) and `canceled`
    # resolve to Free; `past_due` keeps Pro features for the dunning
    # grace period, enforced at the view layer via downgrade task after
    # grace expiry.
    if sub.status not in ("active", "trialing", "past_due"):
        return FREE
    return sub.plan


def plan_limits(plan: str) -> dict:
    return PLAN_LIMITS.get(plan, PLAN_LIMITS[FREE])
