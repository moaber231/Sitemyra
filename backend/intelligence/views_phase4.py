"""Phase 4 API — exports, reports and battlecards.

Every export and every report is filtered by exactly the same visibility
rules as the feed, so a download can never contain another workspace's
data. Every row carries its source URL and detection time.
"""

import json
import logging

from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from workspaces.models import Workspace
from workspaces.permissions import require_role

from .models import Competitor, Report
from .services import exporters
from .services import feed as feed_service
from .services import reports as report_service

logger = logging.getLogger(__name__)


def _visible_report(request, report_id):
    from .views_phase2 import _workspace_ids
    from django.db.models import Q

    queryset = Report.objects.all()
    if not request.user.is_superuser:
        visible = Q(user=request.user) | Q(organization__memberships__user=request.user)
        workspace_ids = _workspace_ids(request.user)
        if workspace_ids:
            visible |= Q(workspace_id__in=workspace_ids)
        queryset = queryset.filter(visible).distinct()
    return get_object_or_404(queryset, id=report_id)


def _filename(prefix, fmt, report=None):
    from .services.reports import _slugify

    stem = _slugify(report.title) if report is not None else prefix
    return f"{stem}.{fmt}"



# --------------------------------------------------------------------------
# Format parameter
#
# DRF's `URL_FORMAT_OVERRIDE` ("format") is a *renderer* selector, and DRF
# consumes it during content negotiation **before** the view runs. Asking for
# `?format=csv` therefore 404s with "Not found." because there is no `csv`
# renderer — the same trap the compliance export already documented with its
# `?type=` workaround.
#
# So the export format is read from `type` (consistent with the existing
# compliance export) with `fmt` accepted as an alias, and `format` is
# deliberately ignored.
# --------------------------------------------------------------------------

FORMAT_QUERY_PARAMS = ("type", "fmt")


def requested_format(request, default="csv"):
    for key in FORMAT_QUERY_PARAMS:
        value = (request.query_params.get(key) or "").strip().lower()
        if value:
            return value
    return default


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def export_intelligence(request):
    """Direct export of the feed. No report row is created."""
    fmt = requested_format(request)
    if fmt not in exporters.FORMATS:
        return Response(
            {
                "detail": (
                    f"Unsupported format '{fmt}'. Use ?type= with one of the "
                    "supported values — ?format= is reserved by the API for "
                    "renderer selection."
                ),
                "supported": sorted(set(exporters.FORMATS)),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    page = feed_service.get_feed(
        request.user,
        kind=request.query_params.get("kind"),
        competitor=request.query_params.get("competitor"),
        severity=request.query_params.get("severity"),
        monitor=request.query_params.get("monitor"),
        limit=request.query_params.get("limit") or 100,
    )
    # get_feed already returns the serialized projection, so re-serializing
    # here would be a double pass over the same rows.
    rows = page["results"]
    competitors = []
    competitor_id = request.query_params.get("competitor")
    if competitor_id:
        competitor = Competitor.objects.filter(
            id=competitor_id, user=request.user
        ).first()
        if competitor is not None:
            competitors.append(competitor)

    # Re-shape feed dicts into exporter rows.
    normalized = []
    for row in rows:
        detected = row.get("detected_at")
        normalized.append(
            {
                # Exporters treat every column as text; the feed projection
                # returns a real datetime, so stringify it here once.
                "detected_at": detected.isoformat() if hasattr(detected, "isoformat") else (detected or ""),
                "competitor": row["competitor_name"] or "",
                "kind": row["kind"],
                "severity": row["severity"],
                "headline": row["headline"],
                "before": row["before"],
                "after": row["after"],
                "rule": (row.get("evidence") or {}).get("rule", ""),
                "basis": row["summary"],
                "source_url": row["source_url"],
                "monitor_name": row["monitor_name"] or "",
                "monitor_url": "",
                "signal_event_id": row["id"],
                "evidence": json.dumps(row.get("evidence") or {}, sort_keys=True)[:500],
            }
        )
    normalized.extend(exporters.flatten_competitor(item) for item in competitors)
    normalized.sort(key=lambda item: item.get("detected_at") or "", reverse=True)

    branding = _branding_for(request)
    try:
        body = exporters.render(
            fmt,
            normalized,
            title="Sitemyra intelligence export",
            meta={"events": len(normalized), "filters": request.query_params.dict()},
            branding=branding,
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    content_type, extension = exporters.FORMATS[fmt]
    response = HttpResponse(body, content_type=content_type)
    response["Content-Disposition"] = (
        f'attachment; filename="{_filename("sitemyra-intelligence", extension)}"'
    )
    response["X-Sitemyra-Rows"] = str(len(normalized))
    return response


def _branding_for(request):
    """White-label branding when the request is scoped to an agency."""
    organization_id = request.query_params.get("organization")
    if not organization_id:
        return None
    from .models import Organization

    organization = Organization.objects.filter(
        id=organization_id, memberships__user=request.user
    ).first()
    return organization.branding if organization is not None else None


@api_view(["GET", "POST"])
@permission_classes([permissions.IsAuthenticated])
def reports(request):
    """List or generate reports."""
    if request.method == "GET":
        from .views_phase2 import _workspace_ids

        queryset = Report.objects.all()
        if not request.user.is_superuser:
            visible = Q(user=request.user) | Q(
                organization__memberships__user=request.user
            )
            workspace_ids = _workspace_ids(request.user)
            if workspace_ids:
                visible |= Q(workspace_id__in=workspace_ids)
            queryset = queryset.filter(visible).distinct()
        return Response(
            {
                "reports": [
                    _serialize_report(row)
                    for row in queryset.order_by("-created_at")[:100]
                ]
            }
        )

    payload = request.data or {}
    title = (payload.get("title") or "").strip() or "Competitive intelligence report"
    competitor_ids = payload.get("competitor_ids") or []
    monitor_ids = payload.get("monitor_ids") or []
    period_days = payload.get("period_days") or report_service.DEFAULT_PERIOD_DAYS
    formats = payload.get("formats") or ["html", "pdf"]
    workspace = None
    organization = None
    if payload.get("workspace"):
        workspace = get_object_or_404(Workspace, id=payload["workspace"])
        if not require_role(request.user, workspace, minimum="admin"):
            return Response(
                {"detail": "You need an admin or owner role in that workspace."},
                status=status.HTTP_403_FORBIDDEN,
            )
    if payload.get("organization"):
        from .models import Organization, OrganizationMembership

        organization = get_object_or_404(
            Organization.objects.filter(memberships__user=request.user),
            id=payload["organization"],
        )
        if not require_role(
            request.user, organization, minimum="admin"
        ):
            return Response(
                {"detail": "You need an admin or owner role in that agency."},
                status=status.HTTP_403_FORBIDDEN,
            )

    invalid = [fmt for fmt in formats if fmt not in exporters.FORMATS]
    if invalid:
        return Response(
            {
                "detail": f"Unsupported format(s): {', '.join(invalid)}.",
                "supported": sorted(set(exporters.FORMATS)),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        period_days = max(1, min(int(period_days), report_service.MAX_PERIOD_DAYS))
    except (TypeError, ValueError):
        return Response(
            {"detail": "period_days must be a number."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    report = report_service.create_report(
        request.user,
        title,
        competitor_ids=competitor_ids,
        monitor_ids=monitor_ids,
        period_days=period_days,
        formats=formats,
        branding=organization.branding if organization is not None else None,
        workspace=workspace,
        organization=organization,
    )
    return Response(_serialize_report(report), status=status.HTTP_201_CREATED)


def _serialize_report(row) -> dict:
    return {
        "id": str(row.id),
        "title": row.title,
        "slug": row.slug,
        "kind": row.kind,
        "status": row.status,
        "formats": row.formats,
        "period_start": row.period_start,
        "period_end": row.period_end,
        "rows": row.meta.get("rows", 0),
        "competitors": row.meta.get("competitors", 0),
        "sources": row.meta.get("sources", 0),
        "truncated": row.meta.get("truncated", False),
        "branding": row.branding,
        "generated_at": row.generated_at,
        "created_at": row.created_at,
        "executive_summary": (row.payload or {}).get("executive_summary", {}).get("text", ""),
        "downloads": {
            fmt: f"/api/intelligence/reports/{row.id}/download/?format={fmt}"
            for fmt in (row.formats or ["html"])
        },
    }


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def report_detail(request, report_id):
    report = _visible_report(request, report_id)
    payload = _serialize_report(report)
    payload["payload"] = report.payload
    return Response(payload)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def report_download(request, report_id):
    report = _visible_report(request, report_id)
    fmt = requested_format(request, (report.formats or ["html"])[0])
    if fmt not in exporters.FORMATS:
        return Response(
            {
                "detail": f"Unsupported format '{fmt}'.",
                "supported": sorted(set(exporters.FORMATS)),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    if report.status != report_service.STATUS_READY:
        return Response(
            {"detail": f"This report is {report.status}."},
            status=status.HTTP_409_CONFLICT,
        )
    try:
        body = report_service.render_report(report, fmt)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    content_type, extension = exporters.FORMATS[fmt]
    response = HttpResponse(body, content_type=content_type)
    response["Content-Disposition"] = (
        f'attachment; filename="{_filename("report", extension, report)}"'
    )
    return response


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def competitor_battlecard(request, competitor_id):
    """The living competitor profile, with an explicit staleness flag."""
    from .views_phase2 import _visible_competitor

    competitor = _visible_competitor(request, competitor_id)
    refresh = (request.query_params.get("refresh") or "").lower() in ("1", "true", "yes")
    card = report_service.upsert_battlecard(competitor)
    stale = report_service.is_battlecard_stale(card)
    payload = report_service.compose_battlecard(competitor)
    return Response(
        {
            "id": str(card.id),
            "refreshed": refresh,
            "is_stale": stale,
            "generated_at": card.generated_at,
            "stale_note": (
                "Newer changes exist for this competitor than the figures below. "
                "Regenerate the card before sharing it."
                if stale
                else "This card reflects every change Sitemyra has recorded for this "
                "competitor so far."
            ),
            **payload,
        }
    )
