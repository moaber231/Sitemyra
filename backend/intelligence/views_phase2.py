"""Phase 2 API — market feed, competitor pulse, competitor discovery.

Tenant rules are identical to Phase 1: a record the caller cannot see is
**404**, never 403, and every competitor-scoped write requires the same
workspace admin role as a monitor write.
"""

import logging
from datetime import timedelta

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from monitors.models import Monitor
from workspaces.models import Workspace
from workspaces.permissions import require_role

from .models import Competitor, CompetitorCandidate
from .serializers import (
    ApproveCandidateSerializer,
    CompetitorCandidateSerializer,
    DiscoverRequestSerializer,
    FeedEventSerializer,
)
from .services import activation as activation_service
from .services import analysis as analysis_service
from .services import feed as feed_service
from .services import signals as signal_service

logger = logging.getLogger(__name__)


def _workspace_ids(user):
    """Every workspace the caller can reach.

    A workspace the user belongs to directly, one they own, or a **client
    workspace of an agency they are a member of** (Phase 5). The agency
    branch is what makes an analyst's client watchlists visible to them.
    """
    ids = list(user.workspace_memberships.values_list("workspace_id", flat=True)) + list(
        user.owned_workspaces.values_list("id", flat=True)
    )
    if not user.is_superuser:
        try:
            from .models import OrganizationMembership

            ids += list(
                Workspace.objects.filter(
                    organization__memberships__user=user
                ).values_list("id", flat=True)
            )
        except Exception:  # pragma: no cover
            pass
    return sorted({workspace_id for workspace_id in ids if workspace_id})


def _visible_competitor(request, competitor_id):
    """404 (never 403) for a competitor the caller cannot see."""
    queryset = Competitor.objects.all()
    if not request.user.is_superuser:
        workspace_ids = _workspace_ids(request.user)
        visible = Q(user=request.user)
        if workspace_ids:
            visible |= Q(workspace_id__in=workspace_ids)
        queryset = queryset.filter(visible)
    return get_object_or_404(queryset, id=competitor_id)


def _visible_candidate(request, candidate_id):
    """404 (never 403) for a candidate the caller cannot approve.

    Visibility follows the parent Competitor, which is what the
    organization/workspace visibility rules are expressed on.
    """
    if request.user.is_superuser:
        queryset = CompetitorCandidate.objects.all()
    else:
        workspace_ids = _workspace_ids(request.user)
        competitor_filter = Q(user=request.user)
        if workspace_ids:
            competitor_filter |= Q(workspace_id__in=workspace_ids)
        queryset = CompetitorCandidate.objects.filter(
            competitor__in=Competitor.objects.filter(competitor_filter)
        )
    return get_object_or_404(queryset, id=candidate_id)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def feed(request):
    """The chronological market feed, filterable and cursor-paginated."""
    window_days = _int_param(request.query_params.get("window_days"), 0)
    since = None
    if window_days:
        since = timezone.now() - timedelta(days=max(1, min(window_days, 365)))

    page = feed_service.get_feed(
        request.user,
        kind=request.query_params.get("kind"),
        competitor=request.query_params.get("competitor"),
        severity=request.query_params.get("severity"),
        monitor=request.query_params.get("monitor"),
        cursor=request.query_params.get("cursor"),
        limit=request.query_params.get("limit"),
        since=since,
    )
    payload = FeedEventSerializer(page["results"], many=True).data
    counts = _kind_counts(request.user, since=since)
    return Response(
        {
            "results": payload,
            "count": page["count"],
            "has_more": page["has_more"],
            "next_cursor": page["next_cursor"],
            "counts_by_kind": counts,
            "available_kinds": _available_kinds(),
        }
    )


def _int_param(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _available_kinds():
    return [
        {"value": "all", "label": "All"},
        {"value": "pricing", "label": "Pricing"},
        {"value": "products", "label": "Products"},
        {"value": "features", "label": "Features"},
        {"value": "marketing", "label": "Marketing"},
        {"value": "content", "label": "Content"},
        {"value": "hiring", "label": "Hiring"},
        {"value": "other", "label": "Other"},
    ]


def _kind_counts(user, since=None):
    queryset = feed_service.feed_queryset(user, since=since)
    counts = {row["kind"]: row["total"] for row in queryset.values("kind").annotate(total=Count("id"))}
    merged = {entry["value"]: 0 for entry in _available_kinds() if entry["value"] != "all"}
    merged.update(counts)
    return merged


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def pulse(request):
    """Competitor pulse board: descriptive states, never scores."""
    window_days = _int_param(request.query_params.get("window_days"), feed_service.ACTIVE_WINDOW_DAYS)
    window_days = max(1, min(window_days, 365))
    return Response(feed_service.get_pulse(request.user, window_days=window_days))


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def overview(request):
    """Compact counts for the dashboard home page."""
    return Response(feed_service.competitor_summary(request.user))


class CompetitorListView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        window_days = _int_param(request.query_params.get("window_days"), feed_service.ACTIVE_WINDOW_DAYS)
        window_days = max(1, min(window_days, 365))
        return Response(
            feed_service.get_pulse(request.user, window_days=window_days)
        )


class CompetitorDetailView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, competitor_id):
        competitor = _visible_competitor(request, competitor_id)
        window_days = _int_param(request.query_params.get("window_days"), feed_service.ACTIVE_WINDOW_DAYS)
        window_days = max(1, min(window_days, 365))
        data = feed_service.pulse_for_competitor(competitor, window_days=window_days)
        data["candidates"] = CompetitorCandidateSerializer(
            competitor.candidates.order_by("approved", "-confidence", "domain")[:50],
            many=True,
        ).data
        data["monitors"] = [
            {
                "id": str(monitor.id),
                "name": monitor.name,
                "url": monitor.url,
                "active": monitor.active,
            }
            for monitor in Monitor.objects.filter(
                user=request.user, url__icontains=competitor.domain
            )[:50]
        ]
        return Response(data)


class CompetitorActivityView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, competitor_id):
        competitor = _visible_competitor(request, competitor_id)
        page = feed_service.get_feed(
            request.user, competitor=str(competitor.id), cursor=request.query_params.get("cursor"),
            limit=request.query_params.get("limit"),
        )
        return Response(
            {
                "competitor_id": str(competitor.id),
                "results": FeedEventSerializer(page["results"], many=True).data,
                "has_more": page["has_more"],
                "next_cursor": page["next_cursor"],
            }
        )


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def discover(request):
    """Feature 2 — propose competitors for a site the user owns."""
    serializer = DiscoverRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    workspace = None
    if data.get("workspace"):
        workspace = get_object_or_404(Workspace, id=data["workspace"])
        if not require_role(request.user, workspace, minimum="admin"):
            return Response(
                {"detail": "You need an admin or owner role in that workspace."},
                status=status.HTTP_403_FORBIDDEN,
            )

    from .services.discovery import discover_candidates

    try:
        own, candidates = discover_candidates(
            request.user,
            data["url"],
            workspace=workspace,
            timeout_seconds=analysis_service.DEFAULT_TIMEOUT_SECONDS,
        )
    except analysis_service.AnalysisError as exc:
        return Response(
            {"detail": exc.message, "code": exc.code},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {
            "competitor": {
                "id": str(own.id),
                "name": own.name,
                "domain": own.domain,
                "homepage_url": own.homepage_url,
            },
            "candidate_count": len(candidates),
            "candidates": CompetitorCandidateSerializer(candidates, many=True).data,
            "detail": (
                "Candidates are proposals only. Approve one to start monitoring it."
                if candidates
                else "Sitemyra could not find public competitor signals on that site. "
                "You can still add competitors as plain monitors."
            ),
        }
    )


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def approve_candidate(request):
    """Approve a candidate: create a Competitor and start monitoring it.

    Approval is the gate. Nothing is monitored before this call.
    """
    from monitors.serializers import MonitorSerializer

    from .services.competitors import name_for_domain

    serializer = ApproveCandidateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    candidate = _visible_candidate(request, data["candidate_id"])
    if candidate.approved:
        return Response(
            {"detail": "That candidate was already approved.", "competitor_id": str(candidate.competitor_id)},
            status=status.HTTP_200_OK,
        )

    workspace = None
    if data.get("workspace"):
        workspace = get_object_or_404(Workspace, id=data["workspace"])
        if not require_role(request.user, workspace, minimum="admin"):
            return Response(
                {"detail": "You need an admin or owner role in that workspace."},
                status=status.HTTP_403_FORBIDDEN,
            )

    # The candidate URL is the target to monitor.
    analysis_record, _created = analysis_service.store_analysis(
        request.user,
        _analysis_for_url(request.user, candidate.url),
    )
    from .models import DiscoveredTarget

    target = DiscoveredTarget.objects.filter(analysis=analysis_record, url=candidate.url).first()
    targets = [target] if target is not None else []

    result = activation_service.activate(
        request.user,
        analysis_record,
        targets=targets,
        recipe=data.get("recipe") or None,
        workspace=workspace,
        check_interval=data.get("check_interval"),
    )
    if result.get("error") == "workspace_forbidden":
        return Response(
            {"detail": "You need an admin or owner role in that workspace."},
            status=status.HTTP_403_FORBIDDEN,
        )

    now = timezone.now()
    competitor, _made = Competitor.objects.get_or_create(
        user=request.user,
        domain=candidate.domain,
        defaults={
            "name": name_for_domain(candidate.domain, fallback=candidate.domain),
            "homepage_url": f"https://{candidate.domain}",
            "workspace": workspace,
            "relationship": candidate.relationship,
            "relationship_reasons": candidate.reasons,
            "first_seen_at": now,
        },
    )
    from .services.competitors import merge_target_signals

    merge_target_signals(competitor, [f"Approved from a discovery candidate on {candidate.competitor.domain}."])

    candidate.approved = True
    candidate.approved_at = now
    candidate.save(update_fields=["approved", "approved_at"])

    payload = {
        "competitor": {
            "id": str(competitor.id),
            "name": competitor.name,
            "domain": competitor.domain,
            "relationship": competitor.relationship,
        },
        "monitors": MonitorSerializer(result["monitors"], many=True).data,
        "created": result["created"],
        "skipped": result["skipped"],
        "limit_reached": result.get("limit_reached", False),
        "plan": result.get("plan", ""),
    }
    if result.get("limit_reached"):
        payload["detail"] = (
            f"Your '{result.get('plan')}' plan allows {result.get('plan_limit')} "
            "active URLs, so this competitor was not added."
        )
    return Response(payload, status=status.HTTP_201_CREATED)


def _analysis_for_url(user, url):
    """Analyse a URL for approval without failing the approval on failure."""
    try:
        return analysis_service.run_analysis(url)
    except analysis_service.AnalysisError:
        # Fall back to a minimal analysis so approval still creates the
        # monitor; the check will read the real page on its first run.
        normalized = analysis_service.clean_submitted_url(url)
        return {
            "url": normalized,
            "page_kind": "other",
            "page_kind_label": "Page",
            "classification_confidence": "low",
            "classification_rationale": "Sitemyra could not read this page during approval.",
            "facts": {},
            "summary": {},
            "product_detected": False,
            "targets": [
                {
                    "url": normalized,
                    "kind": "other",
                    "label": "Page",
                    "why": "Approved by you as a competitor.",
                    "confidence": "low",
                    "relevance": 100,
                    "is_product": False,
                    "is_primary": True,
                }
            ],
        }


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def derive_now(request):
    """Staff-friendly manual trigger for the feed derivation.

    Runs the same idempotent code path as the 15-minute beat tick, so it is
    safe to call repeatedly.
    """
    if not request.user.is_staff:
        return Response(
            {"detail": "Staff only."}, status=status.HTTP_403_FORBIDDEN
        )
    summary = signal_service.derive_signals()
    return Response(summary)
