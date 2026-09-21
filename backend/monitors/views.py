import csv
import io

from django.db.models import Avg, Count, Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from billing.models import get_plan_for_user, plan_limits
from workspaces.permissions import require_role, user_role_in_workspace

from .models import Monitor
from .serializers import MonitorCheckSerializer, MonitorSerializer
from .tasks import check_monitor


class MonitorViewSet(viewsets.ModelViewSet):
    serializer_class = MonitorSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        # API-key auth: scope to key's workspace when present.
        api_key = getattr(self.request, "api_key", None)
        qs = Monitor.objects.select_related("user", "workspace")
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
        uptime = round((total - errors) / total * 100, 2) if total else 100.0
        avg_latency = (
            checks.filter(response_time_ms__isnull=False).aggregate(
                avg=Avg("response_time_ms")
            )["avg"]
            or 0
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
                "url": monitor.url,
                "status": monitor.status,
                "total_checks": total,
                "failures": errors,
                "changes": changed,
                "uptime_pct": uptime,
                "sla_met": "yes" if uptime >= 99.9 else "no",
                "avg_latency_ms": round(float(avg_latency), 1),
                "outage_count": len(outages) if total else errors,
                "last_outage_at": (
                    last_outage["checked_at"].isoformat()
                    if last_outage and last_outage["checked_at"]
                    else ""
                ),
                "last_error": (last_outage["error"][:200] if last_outage else ""),
                "last_checked": monitor.last_checked_at or "",
                "last_changed": monitor.last_changed_at or "",
                "outages": [
                    {
                        "checked_at": (
                            o["checked_at"].isoformat() if o["checked_at"] else ""
                        ),
                        "status_code": o["status_code"] or "",
                        "response_time_ms": o["response_time_ms"] or "",
                        "error": (o["error"] or "")[:500],
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
        'attachment; filename="apeiro-compliance-report.csv"'
    )
    return resp


def _pdf_response(rows):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        width, height = letter
        y = height - 50
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, y, "Apeiro Monitor - Compliance Report")
        y -= 20
        c.setFont("Helvetica", 9)
        c.drawString(
            40, y, f"Generated {timezone.now().isoformat()}  |  Monitors: {len(rows)}"
        )
        y -= 20

        def _ensure_space(lines=1):
            nonlocal y
            if y < 60 + lines * 12:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 9)

        for r in rows:
            _ensure_space(2)
            c.setFont("Helvetica-Bold", 9)
            c.drawString(
                40,
                y,
                f"{r['monitor'][:40]} | uptime {r['uptime_pct']}% "
                f"| SLA {r['sla_met']} | checks {r['total_checks']} "
                f"| fail {r['failures']} | chg {r['changes']} "
                f"| {r['avg_latency_ms']}ms",
            )
            y -= 14
            c.setFont("Helvetica", 8)
            _ensure_space(1)
            c.drawString(
                48, y,
                f"outages: {r.get('outage_count', 0)} | last: "
                f"{r.get('last_outage_at', '') or 'none'} | "
                f"{(r.get('last_error', '') or '')[:80]}",
            )
            y -= 13
            for o in (r.get("outages", []) or [])[:10]:
                _ensure_space(1)
                c.drawString(
                    56, y,
                    f"- {o['checked_at']} | {o['status_code']} | "
                    f"{o['response_time_ms']}ms | {(o['error'] or '')[:90]}",
                )
                y -= 12
            y -= 4
        c.save()
        pdf = buf.getvalue()
    except ImportError:
        # Minimal fallback PDF so the endpoint works without reportlab.
        lines = ["Apeiro Monitor - Compliance Report", ""]
        for r in rows:
            lines.append(
                f"{r['monitor']} | uptime {r['uptime_pct']}% | "
                f"SLA {r['sla_met']} | checks {r['total_checks']} | "
                f"avg {r['avg_latency_ms']}ms | outages {r.get('outage_count', 0)}"
            )
            for o in (r.get("outages", []) or [])[:10]:
                lines.append(f"  outage {o['checked_at']} | {o['error'][:100]}")
        text = "\n".join(lines)
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content = f"BT /F1 10 Tf 40 750 Td ({escaped}) Tj ET"
        pdf = (
            "%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            "2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R>>endobj\n"
            f"4 0 obj<</Length {len(content)}>>stream\n{content}\nendstream\nendobj\n"
            "trailer<</Root 1 0 R>>\n%%EOF"
        ).encode()
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = (
        'attachment; filename="apeiro-compliance-report.pdf"'
    )
    return resp
