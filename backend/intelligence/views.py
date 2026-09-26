"""Intelligence API — URL intake, activation and product intelligence.

Tenant rules mirror ``monitors.views`` exactly: a record the caller cannot
see returns **404**, never 403, so the API never confirms the existence of
another account's data. Workspace writes require admin, as everywhere else.
"""

import logging
from urllib.parse import quote

from django.conf import settings
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from billing.models import get_plan_for_user
from monitors.models import Monitor
from workspaces.models import Workspace

from .models import DiscoveredTarget, ProductChange, ProductSnapshot, ProductWatch, UrlAnalysis
from .serializers import (
    ActivationRequestSerializer,
    AnalyzeRequestSerializer,
    ProductChangeSerializer,
    ProductWatchSerializer,
    UrlAnalysisSerializer,
)
from .services import activation as activation_service
from .services import analysis as analysis_service
from .services import product_capture
from .services import recipes as recipe_registry

logger = logging.getLogger(__name__)


class PublicAnalyzeThrottle(AnonRateThrottle):
    """Rate limit for the unauthenticated marketing demo.

    Scoped to this view only — the rest of the API keeps its current
    (unthrottled) behaviour so nothing existing changes.
    """

    # Rate comes from REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] so an
    # operator can tune it with PUBLIC_ANALYZE_RATE without a code change.
    # Setting a class-level `rate` here would silently win over that.
    scope = "public_analyze"


def _member_workspace_ids(user):
    if not user or not user.is_authenticated:
        return []
    ids = list(
        user.workspace_memberships.values_list("workspace_id", flat=True)
    ) + list(user.owned_workspaces.values_list("id", flat=True))
    return [workspace_id for workspace_id in ids if workspace_id]


def _visible_monitor_ids(user):
    workspace_ids = _member_workspace_ids(user)
    queryset = Monitor.objects.filter(user=user)
    if workspace_ids:
        queryset = queryset | Monitor.objects.filter(workspace_id__in=workspace_ids)
    return queryset.values_list("id", flat=True)


def get_visible_analysis(request, analysis_id):
    """Fetch an analysis the caller owns, or raise 404."""
    queryset = UrlAnalysis.objects.all()
    if not request.user.is_superuser:
        queryset = queryset.filter(user=request.user)
    return get_object_or_404(queryset, id=analysis_id)


def get_visible_watch(request, watch_id):
    queryset = ProductWatch.objects.select_related("monitor")
    if not request.user.is_superuser:
        queryset = queryset.filter(monitor_id__in=_visible_monitor_ids(request.user))
    return get_object_or_404(queryset, id=watch_id)


def get_visible_monitor(request, monitor_id):
    queryset = Monitor.objects.all()
    if not request.user.is_superuser:
        queryset = queryset.filter(id__in=_visible_monitor_ids(request.user))
    return get_object_or_404(queryset, id=monitor_id)


def _with_target_counts(queryset):
    return queryset.prefetch_related(
        Prefetch(
                "targets",
                queryset=DiscoveredTarget.objects.order_by(
                    "-is_primary", "-relevance", "url"
                ),
            )
    )


def _analyze_and_store(request):
    """Return a cached analysis when possible, otherwise fetch a new one.

    The cache is checked *before* the fetch — that is the entire point of
    it, and it is what keeps re-pasting the same competitor URL free on
    the Free plan.
    """
    serializer = AnalyzeRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    url = serializer.validated_data["url"]
    timeout = serializer.validated_data.get("timeout") or analysis_service.DEFAULT_TIMEOUT_SECONDS

    try:
        normalized = analysis_service.clean_submitted_url(url)
    except analysis_service.AnalysisError as exc:
        return None, Response(
            {"detail": exc.message, "code": exc.code},
            status=status.HTTP_400_BAD_REQUEST,
        )

    cached = (
        UrlAnalysis.objects.filter(user=request.user, normalized_url=normalized)
        .order_by("-fetched_at")
        .first()
    )
    if analysis_service.is_fresh(cached):
        record = _with_target_counts(
            UrlAnalysis.objects.filter(id=cached.id)
        ).first()
        data = UrlAnalysisSerializer(record).data
        data["cached"] = True
        return data, None

    try:
        payload = analysis_service.run_analysis(normalized, timeout_seconds=timeout)
    except analysis_service.AnalysisError as exc:
        return None, Response(
            {"detail": exc.message, "code": exc.code},
            status=status.HTTP_400_BAD_REQUEST,
        )

    record, _created = analysis_service.store_analysis(request.user, payload)
    data = UrlAnalysisSerializer(
        _with_target_counts(UrlAnalysis.objects.filter(id=record.id)).first()
    ).data
    data["cached"] = False
    return data, None


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def analyze(request):
    """Analyse a URL the user submitted and return what is worth watching."""
    data, error = _analyze_and_store(request)
    if error is not None:
        return error
    return Response(data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
@throttle_classes([PublicAnalyzeThrottle])
def public_analyze(request):
    """Unauthenticated demo used by the marketing homepage.

    Returns a redacted projection of facts that are already public at the
    submitted URL. Nothing is persisted, no user is referenced, and no
    monitoring starts.
    """
    serializer = AnalyzeRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    url = serializer.validated_data["url"]
    timeout = serializer.validated_data.get("timeout") or analysis_service.DEFAULT_TIMEOUT_SECONDS
    try:
        payload = analysis_service.run_analysis(url, timeout_seconds=timeout)
    except analysis_service.AnalysisError as exc:
        return Response(
            {"detail": exc.message, "code": exc.code},
            status=status.HTTP_400_BAD_REQUEST,
        )
    view = analysis_service.public_view(payload)
    frontend = (settings.FRONTEND_URL or "").rstrip("/")
    view["sign_in_url"] = f"{frontend}/register?url={quote(url, safe='')}"
    return Response(view, status=status.HTTP_200_OK)


def _resolve_targets(analysis, target_ids):
    queryset = DiscoveredTarget.objects.filter(analysis=analysis)
    if target_ids:
        queryset = queryset.filter(id__in=list(target_ids))
    return list(queryset.order_by("-is_primary", "-relevance", "url"))


def _serialize_targets(targets):
    return [
        {
            "id": str(target.id),
            "url": target.url,
            "kind": target.kind,
            "label": target.label,
            "why": target.why,
            "confidence": target.confidence,
            "relevance": target.relevance,
            "is_product": target.is_product,
            "is_primary": target.is_primary,
        }
        for target in targets
    ]


def _workspace_for(request, workspace_id):
    if not workspace_id:
        return None
    return get_object_or_404(Workspace, id=workspace_id)


def _activation_response(result, request):
    from monitors.serializers import MonitorSerializer

    if result.get("error") == "workspace_forbidden":
        return Response(
            {"detail": "You need an admin or owner role in that workspace."},
            status=status.HTTP_403_FORBIDDEN,
        )
    if result.get("error") == "no_targets":
        return Response(
            {"detail": "That analysis has no monitoring targets."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    payload = {
        "monitors": MonitorSerializer(result["monitors"], many=True).data,
        "product_watches": ProductWatchSerializer(result["product_watches"], many=True).data,
        "created": result["created"],
        "skipped": result["skipped"],
        "limit_reached": result.get("limit_reached", False),
        "plan": result.get("plan", ""),
        "plan_limit": result.get("plan_limit"),
        "check_interval": result.get("check_interval"),
        "recipe": result.get("recipe", ""),
        "published_first_checks": result.get("published_first_checks", 0),
    }
    if result.get("limit_reached"):
        payload["detail"] = (
            f"Your '{result.get('plan')}' plan allows {result.get('plan_limit')} "
            "active URLs. The rest were not created."
        )
    elif result.get("skipped"):
        payload["detail"] = "Some pages were skipped."
    return Response(payload, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def activate(request):
    """Create monitors from a stored analysis (the "Monitor everything" step)."""
    serializer = ActivationRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    analysis = get_visible_analysis(request, data["analysis_id"])
    workspace = _workspace_for(request, data.get("workspace"))
    targets = _resolve_targets(analysis, data.get("target_ids"))

    result = activation_service.activate(
        request.user,
        analysis,
        targets=targets,
        recipe=data.get("recipe") or None,
        workspace=workspace,
        check_interval=data.get("check_interval"),
    )
    response = _activation_response(result, request)
    if response.status_code == status.HTTP_201_CREATED:
        response.data["selected_targets"] = _serialize_targets(targets)
    return response


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def quick_monitor(request):
    """Feature 7 — "Monitor this page" in a single call.

    Used by the bookmarklet and the browser extension. Idempotent: if the
    URL is already monitored, the existing monitor is returned.
    """
    serializer = ActivationRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    workspace = _workspace_for(request, data.get("workspace"))

    if data.get("analysis_id"):
        analysis = get_visible_analysis(request, data["analysis_id"])
    else:
        try:
            payload = analysis_service.run_analysis(
                data["url"], timeout_seconds=analysis_service.DEFAULT_TIMEOUT_SECONDS
            )
        except analysis_service.AnalysisError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        analysis, _created = analysis_service.store_analysis(request.user, payload)

    targets = _resolve_targets(analysis, data.get("target_ids"))
    if not targets:
        targets = list(
            DiscoveredTarget.objects.filter(analysis=analysis).order_by(
                "-is_primary", "-relevance"
            )[:1]
        )

    result = activation_service.activate(
        request.user,
        analysis,
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
    if result.get("error") == "no_targets":
        return Response(
            {"detail": "Sitemyra could not find a page on that URL worth monitoring."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from monitors.serializers import MonitorSerializer

    payload = {
        "analysis_id": str(analysis.id),
        "monitors": MonitorSerializer(result["monitors"], many=True).data,
        "product_watches": ProductWatchSerializer(result["product_watches"], many=True).data,
        "created": result["created"],
        "skipped": result["skipped"],
        "plan": result.get("plan", ""),
        "plan_limit": result.get("plan_limit"),
        "product_detected": analysis.product_detected,
        "page_kind": analysis.page_kind,
    }
    if result["monitors"]:
        payload["monitor_id"] = str(result["monitors"][0].id)
        payload["detail"] = (
            f"Monitoring {result['monitors'][0].name}."
            if result["created"] == 1
            else f"Monitoring {result['created']} pages."
        )
    elif result["skipped"]:
        payload["detail"] = "That page is already monitored."
        existing = result["skipped"][0].get("monitor_id")
        if existing:
            payload["monitor_id"] = existing
    return Response(payload, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def recipes(request):
    return Response(
        {
            "recipes": recipe_registry.list_recipes(),
            "plan": get_plan_for_user(request.user),
        }
    )


class ProductWatchListView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        queryset = ProductWatch.objects.select_related("monitor")
        if not request.user.is_superuser:
            queryset = queryset.filter(
                monitor_id__in=_visible_monitor_ids(request.user)
            )
        watches = list(
            queryset.prefetch_related(
                Prefetch(
                    "snapshots",
                    queryset=ProductSnapshot.objects.order_by("-captured_at")[:1],
                    to_attr="latest_snapshot_preview",
                )
            )
        )
        # One grouped query for every change count, instead of one per watch.
        change_counts = {
            row["product_watch"]: row["total"]
            for row in ProductChange.objects.filter(product_watch__in=queryset)
            .values("product_watch")
            .annotate(total=Count("id"))
        }
        for watch in watches:
            watch.change_count_cache = change_counts.get(watch.id, 0)
        return Response(
            {"product_watches": ProductWatchSerializer(watches, many=True).data}
        )


class ProductWatchDetailView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, watch_id):
        watch = get_visible_watch(request, watch_id)
        snapshot = watch.latest_snapshot
        changes = watch.changes.order_by("-created_at")[:50]
        explanation = product_capture.build_explanation(watch, list(changes))
        from .serializers import ProductSnapshotSerializer

        return Response(
            {
                "product_watch": ProductWatchSerializer(watch).data,
                "current_snapshot": (
                    ProductSnapshotSerializer(snapshot).data if snapshot else None
                ),
                "changes": ProductChangeSerializer(changes, many=True).data,
                "explanation": explanation,
                "source_url": snapshot.source_url if snapshot else watch.monitor.url,
            }
        )


class ProductWatchTimelineView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, watch_id):
        watch = get_visible_watch(request, watch_id)
        queryset = watch.changes.order_by("-created_at")
        severity = (request.query_params.get("severity") or "").strip()
        if severity:
            queryset = queryset.filter(severity=severity)
        category = (request.query_params.get("category") or "").strip()
        if category:
            queryset = queryset.filter(category=category)
        try:
            limit = max(1, min(200, int(request.query_params.get("limit") or 50)))
        except (TypeError, ValueError):
            limit = 50
        rows = list(queryset[:limit])
        return Response(
            {
                "product_watch_id": str(watch.id),
                "count": len(rows),
                "changes": ProductChangeSerializer(rows, many=True).data,
                "explanation": product_capture.build_explanation(watch, rows),
            }
        )


class MonitorProductView(APIView):
    """Product state for one monitor, or 404 when it has no product watch."""

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, monitor_id):
        monitor = get_visible_monitor(request, monitor_id)
        watch = getattr(monitor, "product_watch", None)
        if watch is None:
            return Response(
                {"detail": "This monitor is not tracking a product."},
                status=status.HTTP_404_NOT_FOUND,
            )
        snapshot = watch.latest_snapshot
        changes = list(watch.changes.order_by("-created_at")[:25])
        from .serializers import ProductSnapshotSerializer

        return Response(
            {
                "monitor_id": str(monitor.id),
                "product_watch": ProductWatchSerializer(watch).data,
                "current_snapshot": (
                    ProductSnapshotSerializer(snapshot).data if snapshot else None
                ),
                "changes": ProductChangeSerializer(changes, many=True).data,
                "explanation": product_capture.build_explanation(watch, changes),
            }
        )
