"""Phase 5 API — agency mode.

An agency owns client workspaces. The shape mirrors the existing workspace
model on purpose, so the codebase has one tenancy concept to reason about
rather than two:

    Organization (agency)
      └── Workspace (client)  ← one Workspace.organization FK, nullable
            ├── Monitor / ProductWatch / Competitor / SignalEvent
            └── AlertChannel

Authorisation:

* membership is checked on every organization endpoint;
* a client workspace's rows are only visible to organization members, plus
  any personal workspace membership the user already has (a user in an
  agency and on their own account sees both, and never more);
* `analyst` may build watchlists and reports; only `admin`/`owner` may
  create client workspaces, manage seats, set branding, or change billing.
"""

import logging

import re

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from workspaces.models import Workspace, WorkspaceMembership

from .models import Organization, OrganizationMembership

logger = logging.getLogger(__name__)

# Branding is stored as plain text and never interpreted as markup.
_BRANDING_TEXT_FIELDS = ("agency_name", "tagline", "footer", "logo_text")
_BRANDING_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_MAX_BRANDING_FIELD = 120


def user_organizations(user):
    if not user or not user.is_authenticated:
        return Organization.objects.none()
    if user.is_superuser:
        return Organization.objects.all()
    return Organization.objects.filter(
        Q(memberships__user=user) | Q(owner=user)
    ).distinct()


def role_in_organization(user, organization):
    if user is None or organization is None:
        return None
    if user.is_superuser or organization.owner_id == user.id:
        return OrganizationMembership.OWNER
    membership = OrganizationMembership.objects.filter(
        organization=organization, user=user
    ).first()
    return membership.role if membership else None


def require_org_role(user, organization, minimum="viewer"):
    role = role_in_organization(user, organization)
    if role is None:
        return False
    rank = OrganizationMembership.ROLE_RANK
    return rank.get(role, 0) >= rank.get(minimum, 1)


def _visible_organization(request, organization_id):
    queryset = user_organizations(request.user)
    return get_object_or_404(queryset, id=organization_id)


def _slugify(value, fallback="agency"):
    cleaned = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return (cleaned or fallback)[:70]


def _unique_slug(base):
    slug = _slugify(base)
    candidate = slug
    suffix = 1
    while Organization.objects.filter(slug=candidate).exists():
        suffix += 1
        candidate = f"{slug}-{suffix}"
    return candidate


def sanitize_branding(payload):
    """Plain text only, length-capped, colour shape-checked.

    No HTML is accepted and nothing here is ever fetched by the server, so
    an agency cannot turn a report into a stored-XSS or SSRF vector.
    """
    branding = {}
    for field in _BRANDING_TEXT_FIELDS:
        value = payload.get(field)
        if value in (None, ""):
            continue
        text = str(value)
        if "<" in text or ">" in text:
            raise ValueError(f"{field} must not contain HTML.")
        branding[field] = text[:_MAX_BRANDING_FIELD]
    color = payload.get("primary_color")
    if color:
        if not _BRANDING_HEX_RE.match(str(color).strip()):
            raise ValueError("primary_color must be a hex value such as #0052ff.")
        branding["primary_color"] = str(color).strip()
    credit = payload.get("show_sitemyra_credit")
    if isinstance(credit, bool):
        branding["show_sitemyra_credit"] = credit
    return branding


def _serialize_organization(organization, user) -> dict:
    role = role_in_organization(user, organization)
    seats = organization.memberships.count()
    clients = organization.client_workspaces.count()
    from billing.models import PLAN_LIMITS, plan_limits

    limits = plan_limits(organization.plan)
    return {
        "id": str(organization.id),
        "name": organization.name,
        "slug": organization.slug,
        "role": role,
        "branding": organization.branding or {},
        "plan": organization.plan,
        "mrr_cents": organization.mrr_cents,
        "is_active": organization.is_active,
        "seats": seats,
        "clients": clients,
        "limits": {
            "max_seats": limits.get("max_seats", 1),
            "max_client_workspaces": limits.get("max_client_workspaces", 1),
            "max_monitors": limits.get("max_monitors", 3),
            "min_interval_seconds": limits.get("min_interval_seconds", 900),
            "white_label": limits.get("white_label", False),
            "history_days": limits.get("history_days", 7),
        },
        "available_plans": sorted(PLAN_LIMITS),
        "created_at": organization.created_at,
    }


@api_view(["GET", "POST"])
@permission_classes([permissions.IsAuthenticated])
def organizations(request):
    """List the agencies the caller belongs to, or create one."""
    if request.method == "GET":
        rows = list(user_organizations(request.user).annotate(seats=Count("memberships", distinct=True)))
        return Response(
            {"organizations": [_serialize_organization(row, request.user) for row in rows]}
        )

    name = (request.data.get("name") or "").strip()
    if not name:
        return Response(
            {"detail": "An agency name is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    organization = Organization.objects.create(
        owner=request.user,
        name=name[:200],
        slug=_unique_slug(name),
        plan="pro",
    )
    OrganizationMembership.objects.create(
        organization=organization, user=request.user, role=OrganizationMembership.OWNER
    )
    return Response(
        _serialize_organization(organization, request.user),
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([permissions.IsAuthenticated])
def organization_detail(request, organization_id):
    organization = _visible_organization(request, organization_id)

    if request.method == "GET":
        return Response(_serialize_organization(organization, request.user))

    if not require_org_role(request.user, organization, minimum="admin"):
        return Response(
            {"detail": "You need an admin or owner role in this agency."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "PATCH":
        name = (request.data.get("name") or "").strip()
        if name:
            organization.name = name[:200]
        if "branding" in request.data:
            try:
                organization.branding = sanitize_branding(request.data["branding"] or {})
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        organization.save(update_fields=["name", "branding", "updated_at"])
        return Response(_serialize_organization(organization, request.user))

    # DELETE is refused: destroying an agency would delete client
    # workspaces and their monitors. Deactivate instead, explicitly.
    organization.is_active = False
    organization.save(update_fields=["is_active", "updated_at"])
    return Response(
        {
            "id": str(organization.id),
            "is_active": False,
            "detail": (
                "The agency was deactivated rather than deleted, so client "
                "workspaces, monitors and reports are preserved."
            ),
        }
    )


@api_view(["GET", "POST"])
@permission_classes([permissions.IsAuthenticated])
def organization_members(request, organization_id):
    """List seats, or add one by email."""
    organization = _visible_organization(request, organization_id)
    if not require_org_role(request.user, organization, minimum="viewer"):
        return Response(
            {"detail": "You are not a member of this agency."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        rows = organization.memberships.select_related("user").order_by("-created_at")
        return Response(
            {
                "members": [
                    {
                        "id": str(row.id),
                        "user_id": str(row.user_id),
                        "email": row.user.email,
                        "role": row.role,
                        "created_at": row.created_at,
                    }
                    for row in rows
                ]
            }
        )

    if not require_org_role(request.user, organization, minimum="admin"):
        return Response(
            {"detail": "You need an admin or owner role to add seats."},
            status=status.HTTP_403_FORBIDDEN,
        )

    email = (request.data.get("email") or "").strip().lower()
    role = (request.data.get("role") or OrganizationMembership.VIEWER).strip()
    if role not in dict(OrganizationMembership.ROLE_CHOICES):
        return Response(
            {"detail": f"Unknown role '{role}'."}, status=status.HTTP_400_BAD_REQUEST
        )
    if not email or "@" not in email:
        return Response(
            {"detail": "A valid email address is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from accounts.models import User
    from billing.models import plan_limits

    user = User.objects.filter(email=email).first()
    if user is None:
        return Response(
            {
                "detail": "No Sitemyra account uses that email yet. Ask them to "
                "register first, then add them again."
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # Seat limit is checked before creation, not after.
    limit = plan_limits(organization.plan).get("max_seats", 1)
    if OrganizationMembership.objects.filter(organization=organization).count() >= limit:
        return Response(
            {
                "detail": f"The '{organization.plan}' plan includes {limit} seat(s). "
                "Upgrade the agency plan to add more people."
            },
            status=status.HTTP_402_PAYMENT_REQUIRED,
        )

    # Granting owner is restricted to an existing owner, mirroring the
    # workspace rule.
    if role == OrganizationMembership.OWNER and not require_org_role(
        request.user, organization, minimum=OrganizationMembership.OWNER
    ):
        return Response(
            {"detail": "Only an owner can grant the owner role."},
            status=status.HTTP_403_FORBIDDEN,
        )

    membership, created = OrganizationMembership.objects.get_or_create(
        organization=organization, user=user, defaults={"role": role}
    )
    if not created and membership.role != role:
        membership.role = role
        membership.save(update_fields=["role"])
    return Response(
        {
            "id": str(membership.id),
            "user_id": str(membership.user_id),
            "email": membership.user.email,
            "role": membership.role,
            "created": created,
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["GET", "POST"])
@permission_classes([permissions.IsAuthenticated])
def organization_workspaces(request, organization_id):
    """List the agency's client workspaces, or create a new client."""
    organization = _visible_organization(request, organization_id)

    if request.method == "GET":
        if not require_org_role(request.user, organization, minimum="viewer"):
            return Response(
                {"detail": "You are not a member of this agency."},
                status=status.HTTP_403_FORBIDDEN,
            )
        rows = organization.client_workspaces.annotate(
            member_count=Count("memberships", distinct=True)
        ).order_by("name")
        return Response({"workspaces": [_serialize_client(row) for row in rows]})

    if not require_org_role(request.user, organization, minimum="admin"):
        return Response(
            {"detail": "You need an admin or owner role to create client workspaces."},
            status=status.HTTP_403_FORBIDDEN,
        )

    from billing.models import plan_limits

    name = (request.data.get("name") or "").strip()
    if not name:
        return Response(
            {"detail": "A client name is required."}, status=status.HTTP_400_BAD_REQUEST
        )

    limit = plan_limits(organization.plan).get("max_client_workspaces", 1)
    if organization.client_workspaces.count() >= limit:
        return Response(
            {
                "detail": f"The '{organization.plan}' plan includes {limit} client "
                "workspace(s). Upgrade the agency plan to add more clients."
            },
            status=status.HTTP_402_PAYMENT_REQUIRED,
        )

    workspace = Workspace.objects.create(
        name=name[:200],
        slug=_unique_workspace_slug(name),
        owner=request.user,
        organization=organization,
    )
    WorkspaceMembership.objects.create(
        workspace=workspace, user=request.user, role=WorkspaceMembership.OWNER
    )
    return Response(_serialize_client(workspace), status=status.HTTP_201_CREATED)


def _unique_workspace_slug(base):
    candidate = _slugify(base, "client")
    suffix = 1
    while Workspace.objects.filter(slug=candidate).exists():
        suffix += 1
        candidate = f"{_slugify(base, 'client')}-{suffix}"
    return candidate


def _serialize_client(workspace) -> dict:
    from monitors.models import Monitor

    monitors = Monitor.objects.filter(workspace=workspace)
    return {
        "id": str(workspace.id),
        "name": workspace.name,
        "slug": workspace.slug,
        "organization_id": str(workspace.organization_id)
        if workspace.organization_id
        else None,
        "owner_id": str(workspace.owner_id),
        "members": getattr(workspace, "member_count", None)
        if hasattr(workspace, "member_count")
        else workspace.memberships.count(),
        "monitors": monitors.filter(active=True).count(),
        "monitors_total": monitors.count(),
        "competitors": workspace.competitors.count(),
        "created_at": workspace.created_at,
    }


@api_view(["GET", "PATCH"])
@permission_classes([permissions.IsAuthenticated])
def organization_branding(request, organization_id):
    """Read or update white-label branding for the agency's reports."""
    organization = _visible_organization(request, organization_id)
    minimum = "viewer" if request.method == "GET" else "admin"
    if not require_org_role(request.user, organization, minimum=minimum):
        return Response(
            {
                "detail": "You are not a member of this agency."
                if request.method == "GET"
                else "You need an admin or owner role to change branding."
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        from billing.models import plan_limits

        return Response(
            {
                "branding": organization.branding or {},
                "white_label_enabled": bool(
                    plan_limits(organization.plan).get("white_label", False)
                ),
                "fields": list(_BRANDING_TEXT_FIELDS) + ["primary_color", "show_sitemyra_credit"],
                "note": (
                    "Branding is plain text and a hex colour. Sitemyra never fetches "
                    "a logo URL and never renders your branding as HTML."
                ),
            }
        )

    # White-label needs a plan that includes it AND a paid, backing
    # subscription — the same reasoning as plan resolution. Without the
    # paid check, a brand-new Organization's default 'pro' plan would hand
    # out a paid entitlement for free.
    from billing.models import _organization_is_paid

    if not plan_limits_for(organization).get("white_label", False):
        return Response(
            {
                "detail": f"The '{organization.plan}' plan does not include "
                "white-label reports."
            },
            status=status.HTTP_402_PAYMENT_REQUIRED,
        )
    if not _organization_is_paid(organization):
        return Response(
            {
                "detail": "White-label reports unlock once this agency's "
                "subscription is active."
            },
            status=status.HTTP_402_PAYMENT_REQUIRED,
        )

    try:
        branding = sanitize_branding(request.data.get("branding") or request.data or {})
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    organization.branding = branding
    organization.save(update_fields=["branding", "updated_at"])
    return Response(
        {
            "branding": organization.branding,
            "updated_at": organization.updated_at,
        }
    )


def plan_limits_for(organization):
    from billing.models import plan_limits

    return plan_limits(organization.plan)
