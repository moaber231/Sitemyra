"""Phase 6 API — browser extension sessions.

This is the highest-risk surface in the product, because a token lives in a
browser. The design keeps the blast radius as small as possible:

* the raw token is returned **once**, at mint time, and never again;
* only a SHA-256 hash is stored, exactly like the existing developer API
  keys;
* the scope is `monitors:read monitors:write` and nothing else — an
  extension token cannot reach billing, alert channels, exports, reports,
  workspaces or organization membership;
* it expires (max 90 days) and revoking it takes effect on the next
  request;
* the extension calls `POST /api/intelligence/quick-monitor/`, which is
  the same idempotent endpoint the dashboard uses — so the extension adds
  no privileged code path, only a convenience one.

What the extension must never hold: Stripe keys, SMTP credentials, the
Django secret, or a long-lived JWT.
"""

import logging

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import BrowserSession

logger = logging.getLogger(__name__)

MAX_ACTIVE_SESSIONS = 10
DEFAULT_TTL_DAYS = 30


@api_view(["GET", "POST"])
@permission_classes([permissions.IsAuthenticated])
def extension_sessions(request):
    """List the caller's extension sessions, or mint a new one."""
    if request.method == "GET":
        rows = BrowserSession.objects.filter(user=request.user).order_by("-created_at")
        return Response(
            {
                "sessions": [
                    {
                        "id": str(row.id),
                        "label": row.label,
                        "prefix": row.prefix,
                        "scopes": row.scopes,
                        "is_active": row.is_active,
                        "created_at": row.created_at,
                        "expires_at": row.expires_at,
                        "last_used_at": row.last_used_at,
                        "revoked_at": row.revoked_at,
                    }
                    for row in rows
                ],
                "allowed_scopes": BrowserSession.SCOPES,
            }
        )

    from workspaces.models import Workspace
    from workspaces.permissions import require_role

    workspace = None
    if request.data.get("workspace"):
        workspace = get_object_or_404(Workspace, id=request.data["workspace"])
        if not require_role(request.user, workspace, minimum="admin"):
            return Response(
                {"detail": "You need an admin or owner role in that workspace."},
                status=status.HTTP_403_FORBIDDEN,
            )

    active = BrowserSession.objects.filter(
        user=request.user, revoked_at__isnull=True, expires_at__gt=timezone.now()
    ).count()
    if active >= MAX_ACTIVE_SESSIONS:
        return Response(
            {
                "detail": f"You already have {active} active extension sessions "
                f"(the limit is {MAX_ACTIVE_SESSIONS}). Revoke one first."
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    try:
        ttl_days = int(request.data.get("ttl_days") or DEFAULT_TTL_DAYS)
    except (TypeError, ValueError):
        return Response(
            {"detail": "ttl_days must be a number."}, status=status.HTTP_400_BAD_REQUEST
        )

    label = (request.data.get("label") or "Browser extension").strip()[:120]
    session, raw = BrowserSession.generate(
        request.user, label=label, workspace=workspace, ttl_days=ttl_days
    )
    logger.info(
        "intelligence extension session minted [user_id=%s session_id=%s]",
        request.user.id, session.id,
    )
    return Response(
        {
            "id": str(session.id),
            # Shown exactly once. It is never stored and never returned again.
            "token": raw,
            "prefix": session.prefix,
            "scopes": session.scopes,
            "expires_at": session.expires_at,
            "warning": (
                "This token is shown once and cannot be retrieved again. Store it "
                "only in the extension's local storage. It can read and create "
                "monitors — and nothing else."
            ),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "DELETE"])
@permission_classes([permissions.IsAuthenticated])
def extension_session_detail(request, session_id):
    session = get_object_or_404(
        BrowserSession.objects.filter(user=request.user), id=session_id
    )
    if request.method == "DELETE":
        if session.revoked_at is None:
            session.revoked_at = timezone.now()
            session.save(update_fields=["revoked_at"])
        return Response(
            {"id": str(session.id), "is_active": False, "revoked_at": session.revoked_at}
        )
    return Response(
        {
            "id": str(session.id),
            "label": session.label,
            "prefix": session.prefix,
            "scopes": session.scopes,
            "is_active": session.is_active,
            "created_at": session.created_at,
            "expires_at": session.expires_at,
            "last_used_at": session.last_used_at,
        }
    )
