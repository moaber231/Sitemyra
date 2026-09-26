"""Phase 3 API — the alert deep link and market signals.

`signal_event_detail` is the screen an alert link must land on: what
changed, why it may matter, what to check, the source, the evidence, the
detection time, and a confidence that is traceable to a rule.
"""

import logging

from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MarketSignal, SignalEvent
from .services import narration as narration_service
from .serializers import FeedEventSerializer

logger = logging.getLogger(__name__)


def _visible_event(request, event_id):
    from django.db.models import Q

    from .views_phase2 import _workspace_ids

    queryset = SignalEvent.objects.all()
    if not request.user.is_superuser:
        visible = Q(user=request.user)
        workspace_ids = _workspace_ids(request.user)
        if workspace_ids:
            visible |= Q(workspace_id__in=workspace_ids)
        queryset = queryset.filter(visible)
    return get_object_or_404(queryset.select_related("competitor", "monitor"), id=event_id)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def signal_event_detail(request, event_id):
    """Everything needed to explain one change, with its evidence."""
    event = _visible_event(request, event_id)
    window_hours = narration_service._int(request.query_params.get("window_hours"), 24)
    detail = narration_service.build_event_detail(
        request.user, event, window_hours=max(1, min(window_hours, 720))
    )
    return Response(detail)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def signals_list(request):
    """Market signals — patterns across competitors, with evidence attached."""
    from django.db.models import Q

    from .views_phase2 import _workspace_ids

    queryset = MarketSignal.objects.all()
    if not request.user.is_superuser:
        visible = Q(user=request.user)
        workspace_ids = _workspace_ids(request.user)
        if workspace_ids:
            visible |= Q(workspace_id__in=workspace_ids)
        queryset = queryset.filter(visible)

    status_filter = (request.query_params.get("status") or "").strip()
    if status_filter and status_filter != "all":
        queryset = queryset.filter(status=status_filter)
    else:
        queryset = queryset.filter(status=MarketSignal.STATUS_NEW)

    rows = list(queryset.order_by("-created_at")[:100])
    return Response(
        {
            "count": len(rows),
            "minimum_competitors": narration_service.MIN_COMPETITORS_FOR_SIGNAL,
            "signals": [
                {
                    "id": str(row.id),
                    "kind": row.kind,
                    "headline": row.headline,
                    "statement": row.statement,
                    "interpretation": row.interpretation,
                    "window_days": row.window_days,
                    "evidence": row.evidence or [],
                    "evidence_count": len(row.evidence or []),
                    "confidence": row.confidence,
                    "status": row.status,
                    "created_at": row.created_at,
                }
                for row in rows
            ],
        }
    )


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def review_signal(request, signal_id):
    """Mark a market signal reviewed or dismissed (so it stops nagging)."""
    status_value = (request.data.get("status") or "").strip()
    signal = narration_service.review_signal(request.user, signal_id, status_value)
    if signal is None:
        return Response(
            {"detail": "Signal not found or an invalid status."},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response({"id": str(signal.id), "status": signal.status})


class NarrationPreferenceView(APIView):
    """GET/PATCH the user's AI-narration opt-in.

    Defaults to OFF. With no provider configured the flag has no effect and
    the product behaves exactly as it does today.
    """

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        return Response(self._payload(request))

    def patch(self, request):
        value = request.data.get("ai_narration_enabled")
        if not isinstance(value, bool):
            return Response(
                {"detail": "ai_narration_enabled must be true or false."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Update the instance as well as the row: request.user is cached for
        # the whole request, so a row-only update would make the response
        # disagree with what was just stored.
        request.user.ai_narration_enabled = value
        request.user.save(update_fields=["ai_narration_enabled"])
        return Response(self._payload(request))

    def _payload(self, request):
        from django.conf import settings

        return {
            "ai_narration_enabled": bool(
                getattr(request.user, "ai_narration_enabled", False)
            ),
            "provider_configured": narration_service.provider_configured(),
            "provider": getattr(settings, "AI_PROVIDER", "") or None,
            "explanation": (
                "Narration is optional. Every change already has a deterministic "
                "explanation built from the stored evidence, and that text is always "
                "kept. When narration is off — the default — Sitemyra makes no "
                "outbound AI request at all."
            ),
        }
