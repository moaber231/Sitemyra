import csv
import io
from textwrap import wrap
from urllib.parse import urlsplit

from django.db.models import Avg, Count, Prefetch, Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from billing.models import get_plan_for_user, plan_limits
from workspaces.permissions import require_role, user_role_in_workspace

from .models import Monitor, MonitorCheck
from .serializers import MonitorCheckSerializer, MonitorSerializer
from .tasks import check_monitor


class MonitorViewSet(viewsets.ModelViewSet):
    serializer_class = MonitorSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        # API-key auth: scope to key's workspace when present.
        api_key = getattr(self.request, "api_key", None)
        qs = Monitor.objects.select_related("user", "workspace").prefetch_related(
            # Plan D9: the latest check arrives as ONE extra query for
            # the whole page — Monitor.status and last_response_time_ms
            # are both served from it (was 2 queries per monitor).
            Prefetch(
                "checks",
                queryset=MonitorCheck.objects.order_by("-checked_at")[:1],
                to_attr="latest_check_preview",
            )
        )
        if api_key is not None and api_key.workspace_id:
            return qs.filter(workspace_id=api_key.workspace_id)
        if user.is_superuser:
            return qs
        member_ws = list(
            user.workspace_memberships.values_list("workspace_id", flat=True)
        ) + list(user.owned_workspaces.values_list("id", flat=True))
        return qs.filter(Q(user=user) | Q(workspace_id__in=member_ws))

    def _assert_can_write(self, monitor=None):
        """Viewers are read-only; Admin/Owner can mutate."""
        user = self.request.user
        if user.is_superuser:
            return
        api_key = getattr(self.request, "api_key", None)
        if api_key is not None:
            if "monitors:write" not in (api_key.scopes or ""):
                from rest_framework.exceptions import PermissionDenied

                raise PermissionDenied("API key is read-only.")
            return
        workspace = None
        if monitor is not None:
            workspace = monitor.workspace
        elif self.request.data.get("workspace"):
            from workspaces.models import Workspace

            workspace = Workspace.objects.filter(
                pk=self.request.data["workspace"]
            ).first()
        if workspace is not None:
            if not require_role(user, workspace, minimum="admin"):
                from rest_framework.exceptions import PermissionDenied

                raise PermissionDenied(
                    "Viewers cannot create or modify workspace monitors."
                )

    def perform_create(self, serializer):
        self._assert_can_write()
        # Usage-based limit: max active URLs per plan.
        plan = get_plan_for_user(self.request.user)
        limit = plan_limits(plan)["max_monitors"]
        active_count = Monitor.objects.filter(
            user=self.request.user, active=True
        ).count()
        if active_count >= limit:
            from rest_framework.exceptions import Throttled

            raise Throttled(
                detail=(
                    f"Plan '{plan}' allows {limit} active URL(s). "
                    "Upgrade or pause a monitor."
                )
            )
        monitor = serializer.save(
            user=self.request.user,
            next_check_at=timezone.now(),
        )

        check_monitor.delay(str(monitor.id))

    def perform_update(self, serializer):
        self._assert_can_write(self.get_object())
        serializer.save()

    def perform_destroy(self, instance):
        self._assert_can_write(instance)
        instance.delete()

    @action(detail=True, methods=["post"])
    def pause(self, request, *args, **kwargs):
        monitor = self.get_object()

        monitor.active = False

        monitor.save(
            update_fields=[
                "active",
                "updated_at",
            ]
        )

        return Response(
            self.get_serializer(monitor).data
        )

    @action(detail=True, methods=["post"])
    def resume(self, request, *args, **kwargs):
        monitor = self.get_object()

        monitor.active = True
        monitor.next_check_at = timezone.now()

        monitor.save(
            update_fields=[
                "active",
                "next_check_at",
                "updated_at",
            ]
        )

        return Response(
            self.get_serializer(monitor).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def test(self, request, *args, **kwargs):
        monitor = self.get_object()

        if not monitor.active:
            return Response(
                {"detail": "Monitor is paused."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        check_monitor.delay(str(monitor.id))

        return Response(
            {"detail": "Monitor check queued."},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["get"])
    def checks(self, request, *args, **kwargs):
        monitor = self.get_object()

        checks = monitor.checks.all()[:100]

        serializer = MonitorCheckSerializer(
            checks,
            many=True,
        )

        return Response(serializer.data)

    # -- Phase 7: per-monitor notification routing -------------------------
    @action(detail=True, methods=["get", "post"], url_path="channels")
    def channels(self, request, *args, **kwargs):
        """List assigned channels (GET) or attach one (POST {channel_id})."""
        from notifications.models import AlertChannel, MonitorAlertChannel

        monitor = self.get_object()

        if request.method == "GET":
            routes = (
                MonitorAlertChannel.objects.filter(monitor=monitor)
                .select_related("channel")
                .order_by("created_at")
            )
            data = [
                {
                    "id": str(route.channel.id),
                    "channel_type": route.channel.channel_type,
                    "name": route.channel.name,
                    "config_preview": route.channel.masked_config,
                    "verified": route.channel.verified,
                    "created_at": route.channel.created_at,
                }
                for route in routes
                if route.channel.user_id == request.user.id
                or (
                    route.channel.workspace_id is not None
                    and monitor.workspace_id is not None
                    and route.channel.workspace_id == monitor.workspace_id
                )
            ]
            return Response(data)

        # POST attach — writers only.
        self._assert_can_write(monitor)
        channel_id = request.data.get("channel_id")
        if not channel_id:
            return Response(
                {"detail": "channel_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        channel = AlertChannel.objects.filter(
            id=channel_id, user=request.user
        ).first()
        if channel is None:
            # No cross-tenant oracle: unknown or another tenant's channel is 404.
            return Response(
                {"detail": "Channel not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if channel.channel_type not in AlertChannel.SUPPORTED_TYPES:
            return Response(
                {
                    "detail": (
                        f"Channel type '{channel.channel_type}' cannot "
                        "deliver notifications."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if (
            channel.workspace_id is not None
            and monitor.workspace_id != channel.workspace_id
        ):
            return Response(
                {"detail": "Workspace channel does not belong to this monitor."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        route, created = MonitorAlertChannel.objects.get_or_create(
            monitor=monitor, channel=channel
        )
        return Response(
            {
                "monitor_id": str(monitor.id),
                "channel_id": str(channel.id),
                "channel_type": channel.channel_type,
                "attached": True,
                "created": created,
            },
            status=(
                status.HTTP_201_CREATED if created else status.HTTP_200_OK
            ),
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"channels/(?P<channel_id>[^/.]+)",
    )
    def detach_channel(self, request, channel_id=None, *args, **kwargs):
        """Detach a channel from this monitor."""
        from notifications.models import MonitorAlertChannel

        monitor = self.get_object()
        self._assert_can_write(monitor)
        deleted, _ = MonitorAlertChannel.objects.filter(
            monitor=monitor, channel_id=channel_id
        ).delete()
        if not deleted:
            return Response(
                {"detail": "Channel is not attached to this monitor."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def changes(self, request, *args, **kwargs):
        monitor = self.get_object()

        checks = monitor.checks.filter(
            changed=True
        )[:100]

        serializer = MonitorCheckSerializer(
            checks,
            many=True,
        )

        return Response(serializer.data)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def compliance_export(request):
    """1-click Export Compliance Report (CSV/PDF): uptime, SLA, changes, outages."""
    from .models import MonitorCheck

    raw_fmt = (
        request.query_params.get("type")
        or request.query_params.get("file")
        or "csv"
    ).lower()
    if raw_fmt not in ("csv", "pdf"):
        return Response(
            {"detail": "Unsupported export type. Use ?type=csv|pdf."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    fmt = raw_fmt
    monitors = MonitorViewSet()
    monitors.request = request
    monitors.format_kwarg = None
    # get_queryset() already scopes to owned + workspace-member monitors
    # (and all monitors for superusers); do NOT re-filter by user here or
    # workspace monitors would silently disappear from the report.
    qs = monitors.get_queryset().order_by("name")
    # Include workspace monitors the user can see.
    rows = []
    for monitor in qs:
        checks = MonitorCheck.objects.filter(monitor=monitor)
        total = checks.count()
        errors = checks.exclude(error="").count()
        changed = checks.filter(changed=True).count()
        uptime = round((total - errors) / total * 100, 2) if total else None
        avg_latency = (
            checks.filter(response_time_ms__isnull=False).aggregate(
                avg=Avg("response_time_ms")
            )["avg"]
        )
        # Outage log: recent failed checks with timestamps + errors.
        outages = list(
            checks.exclude(error="")
            .order_by("-checked_at")
            .values("checked_at", "status_code", "error", "response_time_ms")[:50]
        )
        last_outage = outages[0] if outages else None
        rows.append(
            {
                "monitor": monitor.name,
                "url": _compliance_site_label(monitor.url),
                "status": monitor.status,
                "total_checks": total,
                "failures": errors,
                "changes": changed,
                "uptime_pct": uptime,
                "sla_met": (
                    "Met" if uptime >= 99.9 else "Not met"
                ) if total else "Not assessed",
                "avg_latency_ms": round(float(avg_latency), 1)
                if avg_latency is not None
                else None,
                "outage_count": errors,
                "last_outage_at": (
                    last_outage["checked_at"].isoformat()
                    if last_outage and last_outage["checked_at"]
                    else ""
                ),
                "last_error": (
                    "Request failed; review the monitor for details."
                    if last_outage
                    else ""
                ),
                "last_checked": monitor.last_checked_at or "",
                "last_changed": monitor.last_changed_at or "",
                "outages": [
                    {
                        "checked_at": (
                            o["checked_at"].isoformat() if o["checked_at"] else ""
                        ),
                        "status_code": o["status_code"] or "",
                        "response_time_ms": o["response_time_ms"] or "",
                        "error": "Request failed." if o["error"] else "",
                    }
                    for o in outages
                ],
            }
        )

    if fmt == "pdf":
        return _pdf_response(rows)
    return _csv_response(rows)


def _csv_response(rows):
    buf = io.StringIO()
    summary_fields = [
        "monitor",
        "url",
        "status",
        "total_checks",
        "failures",
        "changes",
        "uptime_pct",
        "sla_met",
        "avg_latency_ms",
        "outage_count",
        "last_outage_at",
        "last_error",
        "last_checked",
        "last_changed",
    ]
    writer = csv.DictWriter(buf, fieldnames=summary_fields, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow({k: r.get(k, "") for k in summary_fields})
    # Outage log section: valid CSV, separated by a blank + section header.
    buf.write("\n")
    outage_writer = csv.DictWriter(
        buf,
        fieldnames=["monitor", "outage_at", "status_code", "response_time_ms", "error"],
    )
    outage_writer.writeheader()
    for r in rows:
        for o in r.get("outages", []):
            outage_writer.writerow(
                {
                    "monitor": r["monitor"],
                    "outage_at": o["checked_at"],
                    "status_code": o["status_code"],
                    "response_time_ms": o["response_time_ms"],
                    "error": o["error"],
                }
            )
    resp = HttpResponse(buf.getvalue(), content_type="text/csv")
    resp["Content-Disposition"] = (
        'attachment; filename="sitemyra-compliance-report.csv"'
    )
    return resp


def _compliance_site_label(raw_url):
    """Return only the host so reports never expose URL credentials or tokens."""
    try:
        parsed = urlsplit(str(raw_url or ""))
        host = parsed.hostname or ""
        if not host:
            return "Website unavailable"
        if parsed.port:
            host = f"{host}:{parsed.port}"
        return host[:220]
    except (TypeError, ValueError):
        return "Website unavailable"


def _pdf_response(rows):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.pagesizes import landscape
        from reportlab.lib.utils import simpleSplit
        from reportlab.pdfgen import canvas

        buf = io.BytesIO()
        page_size = landscape(letter)
        c = canvas.Canvas(buf, pagesize=page_size)
        c.setTitle("Sitemyra Monitoring Compliance Report")
        c.setAuthor("Sitemyra")
        width, height = page_size
        margin = 42
        y = height - margin

        def _draw_lines(text, font="Helvetica", size=9, color=None, gap=3):
            nonlocal y
            if color is not None:
                c.setFillColorRGB(*color)
            c.setFont(font, size)
            for line in simpleSplit(str(text), font, size, width - margin * 2):
                if y < margin + size + gap:
                    c.showPage()
                    y = height - margin
                c.drawString(margin, y, line)
                y -= size + gap
            if color is not None:
                c.setFillColorRGB(0, 0, 0)

        def _date(value):
            if not value:
                return "Not checked yet"
            if isinstance(value, str):
                from django.utils.dateparse import parse_datetime

                value = parse_datetime(value)
            if value is None:
                return "Not available"
            try:
                return timezone.localtime(value).strftime("%b %d, %Y %H:%M %Z")
            except (TypeError, ValueError):
                return "Not available"

        def _site_label(raw_url):
            return str(raw_url or "Website unavailable")[:220]

        def _ensure_space(required=14):
            nonlocal y
            if y < margin + required:
                c.showPage()
                y = height - margin
                _draw_lines(
                    "Monitoring Compliance Report (continued)",
                    font="Helvetica-Bold",
                    size=10,
                )
                y -= 4

        _draw_lines(
            "Sitemyra Monitoring Compliance Report",
            font="Helvetica-Bold",
            size=18,
        )
        _draw_lines(
            f"Generated {_date(timezone.now())} · {len(rows)} monitored page(s)",
            size=9,
            color=(0.35, 0.40, 0.47),
        )
        total_checks = sum(int(row.get("total_checks") or 0) for row in rows)
        total_failures = sum(int(row.get("failures") or 0) for row in rows)
        total_changes = sum(int(row.get("changes") or 0) for row in rows)
        _draw_lines(
            f"Summary: {total_checks} checks · {total_failures} failed checks · "
            f"{total_changes} detected changes",
            font="Helvetica-Bold",
            size=10,
        )
        y -= 4

        if not rows:
            _draw_lines("No monitors are available for this report.", size=10)
        for index, row in enumerate(rows, start=1):
            _ensure_space(90)
            _draw_lines(
                f"{index}. {row.get('monitor') or 'Monitored page'}",
                font="Helvetica-Bold",
                size=12,
            )
            _draw_lines(f"Website: {_site_label(row.get('url'))}", size=8)
            status_labels = {
                "healthy": "Healthy",
                "changed": "Change detected",
                "failing": "Failing",
                "paused": "Paused",
                "never_checked": "Not checked yet",
            }
            _draw_lines(
                f"Monitor status: {status_labels.get(row.get('status'), 'Unknown')}",
                size=9,
            )
            checks = int(row.get("total_checks") or 0)
            if checks:
                _draw_lines(
                    f"Availability: {row['uptime_pct']}% across {checks} checks · "
                    f"SLA target (99.9%): {row['sla_met']}",
                    size=9,
                )
                average = row.get("avg_latency_ms")
                average_text = f"{average} ms" if average is not None else "not available"
                _draw_lines(
                    f"Failed checks: {row['failures']} · "
                    f"Changes detected: {row['changes']} · "
                    f"Average response: {average_text} · "
                    f"Outages: {row['outage_count']}",
                    size=9,
                )
                _draw_lines(f"Last checked: {_date(row.get('last_checked'))}", size=8)
                if row.get("last_changed"):
                    _draw_lines(f"Last change: {_date(row['last_changed'])}", size=8)
                outages = row.get("outages") or []
                if outages:
                    _draw_lines("Recent outages", font="Helvetica-Bold", size=9)
                    for outage in outages[:10]:
                        code = outage.get("status_code") or "No HTTP status"
                        response_time = outage.get("response_time_ms")
                        latency = f" · {response_time} ms" if response_time else ""
                        _draw_lines(f"{_date(outage.get('checked_at'))} · {code}{latency}", size=8)
                else:
                    _draw_lines("No outages recorded.", size=8, color=(0.30, 0.42, 0.35))
            else:
                _draw_lines(
                    "No checks have completed. Availability and SLA are not calculated yet.",
                    size=9,
                    color=(0.35, 0.40, 0.47),
                )
            y -= 8

        _ensure_space(24)
        _draw_lines(
            "Sitemyra reports checks against publicly accessible pages. "
            "Availability is calculated from recorded checks; it is not a guarantee "
            "of future uptime.",
            size=7,
            color=(0.35, 0.40, 0.47),
        )
        c.save()
        pdf = buf.getvalue()
    except ImportError:
        # Minimal fallback PDF so the endpoint works without reportlab.
        lines = [
            "Sitemyra Monitoring Compliance Report",
            f"Generated {timezone.now().strftime('%b %d, %Y %H:%M %Z')}",
            f"{len(rows)} monitored page(s)",
            "",
        ]
        status_labels = {
            "healthy": "Healthy",
            "changed": "Change detected",
            "failing": "Failing",
            "paused": "Paused",
            "never_checked": "Not checked yet",
        }
        for index, row in enumerate(rows[:30], start=1):
            lines.extend(
                [
                    f"{index}. {row.get('monitor') or 'Monitored page'}",
                    f"Website: {_compliance_site_label(row.get('url'))}",
                    f"Monitor status: {status_labels.get(row.get('status'), 'Unknown')}",
                ]
            )
            checks = int(row.get("total_checks") or 0)
            if checks:
                lines.extend(
                    [
                        f"Availability: {row.get('uptime_pct')}% across {checks} checks; "
                        f"SLA target 99.9%: {row.get('sla_met')}",
                        f"Failed checks: {row.get('failures', 0)}; "
                        f"Changes detected: {row.get('changes', 0)}; "
                        f"Average response: {row.get('avg_latency_ms') or 'not available'} ms; "
                        f"Outages: {row.get('outage_count', 0)}",
                    ]
                )
            else:
                lines.append("No checks completed; availability and SLA are not calculated.")
            lines.append("")
        if len(rows) > 30:
            lines.append("Additional monitors are omitted from this basic PDF renderer.")
        lines.append(
            "Availability is calculated from recorded checks; it is not a guarantee of future uptime."
        )
        lines = [line for item in lines for line in wrap(item, 105) or [""]][:55]
        escaped = [
            line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            for line in lines
        ]
        content = "BT /F1 9 Tf 12 TL 40 750 Td " + " Tj T* ".join(
            f"({line})" for line in escaped
        ) + " Tj ET"
        pdf = (
            "%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            "2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R>>endobj\n"
            f"4 0 obj<</Length {len(content)}>>stream\n{content}\nendstream\nendobj\n"
            "trailer<</Root 1 0 R>>\n%%EOF"
        ).encode()
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = (
        'attachment; filename="sitemyra-compliance-report.pdf"'
    )
    return resp
