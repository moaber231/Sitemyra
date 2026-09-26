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
# Phase 5 adds three agency dimensions. Every default equals the
# pre-Phase-5 behaviour for an existing account: `max_seats` 1 and
# `max_client_workspaces` 1 mean a personal plan carries no agency
# features, and `white_label` False means nobody suddenly gains a branded
# report. No existing entitlement changes.
PLAN_LIMITS = {
    FREE: {
        "max_monitors": 3,
        "min_interval_seconds": 900,  # 15m
        "max_alert_channels": 1,
        "history_days": 7,
        "max_seats": 1,
        "max_client_workspaces": 1,
        "white_label": False,
    },
    PRO: {
        "max_monitors": 25,
        "min_interval_seconds": 300,  # 5m
        "max_alert_channels": 5,
        "history_days": 30,
        "max_seats": 3,
        "max_client_workspaces": 3,
        "white_label": True,
    },
    BUSINESS: {
        "max_monitors": 100,
        "min_interval_seconds": 60,  # 1m
        "max_alert_channels": 50,
        "history_days": 90,
        "max_seats": 25,
        "max_client_workspaces": 25,
        "white_label": True,
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
    # Phase 5: an agency bills once for all its seats and client workspaces.
    # NULLABLE, so a personal subscription is untouched. When set, the
    # organization plan is what the members actually get.
    organization = models.OneToOneField(
        "intelligence.Organization",
        on_delete=models.CASCADE,
        related_name="subscription",
        null=True,
        blank=True,
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

    class Meta:
        indexes = [
            # Phase E (plan D9): the Stripe webhook made up to four
            # sequential scans — status/updated_at sweeps plus point
            # lookups by subscription id and by customer id.
            models.Index(fields=["status", "updated_at"]),
            models.Index(fields=["stripe_subscription_id"]),
            models.Index(fields=["stripe_customer_id"]),
        ]

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
    """Resolve the plan a user actually gets.

    Order matters and is additive:

    1. superuser -> BUSINESS (unchanged);
    2. an **active, paid** organization membership -> the organization's
       plan, because in agency mode the agency pays once for all its seats;
    3. otherwise the user's own personal subscription (unchanged).

    The fall-through is what keeps this safe. A user whose agency
    membership was removed, or whose agency is not actually paid, keeps
    exactly the plan they had before this change — no existing account can
    lose an entitlement.
    """
    if user.is_superuser:
        return BUSINESS

    organization_plan = _organization_plan_for_user(user)
    if organization_plan:
        return organization_plan

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


def _organization_plan_for_user(user) -> str:
    """The agency plan for this user, or "" when there is none.

    Imported lazily: ``intelligence`` imports this module for plan limits,
    so a module-level import here would be circular.
    """
    try:
        from intelligence.models import OrganizationMembership
    except Exception:  # pragma: no cover - app not installed
        return ""
    membership = (
        OrganizationMembership.objects.filter(
            user=user, organization__is_active=True
        )
        .select_related("organization")
        .order_by("-created_at")
        .first()
    )
    if membership is None:
        return ""
    organization = membership.organization
    if organization.plan not in PLAN_LIMITS:
        return ""
    # A real paid subscription must back the agency's plan, otherwise the
    # default 'pro' on a brand-new Organization would hand out paid
    # entitlements for free. Unpaid agencies fall back to the personal plan.
    if not _organization_is_paid(organization):
        return ""
    return organization.plan


def _organization_is_paid(organization) -> bool:
    if organization.mrr_cents and organization.mrr_cents > 0:
        return True
    if organization.stripe_subscription_id:
        return True
    return False


def plan_limits(plan: str) -> dict:
    return PLAN_LIMITS.get(plan, PLAN_LIMITS[FREE])
