from decimal import Decimal

from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.artifact_storage import (
    StorageError,
    backend_name,
    load_bytes,
    presigned_get_url,
    url_expires_seconds,
)

from .advanced_tasks import run_advanced_monitor
from .models import (
    AdvancedMonitorConfig,
    ChangeDiff,
    Monitor,
    PricePoint,
)


class AdvancedMonitorConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdvancedMonitorConfig
        fields = [
            "mode",
            "selector",
            "price_selector",
            "price_currency",
            "screenshot_threshold",
        ]

    def validate(self, attrs):
        mode = attrs.get(
            "mode",
            getattr(
                self.instance,
                "mode",
                AdvancedMonitorConfig.HTTP,
            ),
        )

        selector = attrs.get(
            "selector",
            getattr(self.instance, "selector", ""),
        )

        price_selector = attrs.get(
            "price_selector",
            getattr(self.instance, "price_selector", ""),
        )

        threshold = attrs.get(
            "screenshot_threshold",
            getattr(
                self.instance,
                "screenshot_threshold",
                Decimal("0.500"),
            ),
        )

        if mode in {
            AdvancedMonitorConfig.DOM,
            AdvancedMonitorConfig.SCREENSHOT,
        } and not selector.strip():
            raise serializers.ValidationError(
                {
                    "selector": (
                        "A CSS selector is required for this mode."
                    )
                }
            )

        if mode == AdvancedMonitorConfig.PRICE:
            if not price_selector.strip():
                raise serializers.ValidationError(
                    {
                        "price_selector": (
                            "A CSS selector is required for price tracking."
                        )
                    }
                )

        if threshold <= 0 or threshold > 100:
            raise serializers.ValidationError(
                {
                    "screenshot_threshold": (
                        "Threshold must be greater than 0 and at most 100."
                    )
                }
            )

        return attrs


def _owned_monitor(request, monitor_id):
    return get_object_or_404(
        Monitor,
        id=monitor_id,
        user=request.user,
    )


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def advanced_config(request, monitor_id):
    monitor = _owned_monitor(request, monitor_id)

    config, _ = AdvancedMonitorConfig.objects.get_or_create(
        monitor=monitor,
    )

    if request.method == "GET":
        return Response(
            AdvancedMonitorConfigSerializer(config).data
        )

    serializer = AdvancedMonitorConfigSerializer(
        config,
        data=request.data,
        partial=True,
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()

    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def test_advanced_monitor(request, monitor_id):
    monitor = _owned_monitor(request, monitor_id)

    config, _ = AdvancedMonitorConfig.objects.get_or_create(
        monitor=monitor,
    )

    if config.mode == AdvancedMonitorConfig.HTTP:
        return Response(
            {
                "detail": (
                    "Advanced test requires DOM, screenshot, "
                    "or price mode."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    task = run_advanced_monitor.delay(
        str(monitor.id)
    )

    return Response(
        {
            "status": "queued",
            "task_id": task.id,
            "monitor_id": str(monitor.id),
        },
        status=status.HTTP_202_ACCEPTED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def monitor_diffs(request, monitor_id):
    monitor = _owned_monitor(request, monitor_id)

    limit = min(
        max(
            int(request.query_params.get("limit", 50)),
            1,
        ),
        100,
    )

    diffs = (
        ChangeDiff.objects
        .filter(monitor=monitor)
        .select_related(
            "previous_check",
            "current_check",
        )
        .order_by("-created_at")[:limit]
    )

    data = [
        {
            "id": str(diff.id),
            "type": diff.diff_type,
            "summary": diff.summary,
            "diff_percentage": (
                float(diff.diff_percentage)
                if diff.diff_percentage is not None
                else None
            ),
            # Keys only: internal paths are never exposed. The download
            # endpoint authorizes the owner and streams (local) or
            # redirects to a short-lived signed URL (s3).
            "artifact_available": bool(diff.artifact_path),
            "artifact_type": diff.diff_type,
            "artifact_download_url": (
                reverse(
                    "artifact-download",
                    kwargs={"diff_id": str(diff.id)},
                )
                if diff.artifact_path
                else None
            ),
            "previous_check_id": str(
                diff.previous_check_id
            ),
            "current_check_id": str(
                diff.current_check_id
            ),
            "created_at": diff.created_at,
        }
        for diff in diffs
    ]

    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def artifact_download(request, diff_id):
    """Owner-authorized artifact download (tenant isolated).

    Local backend: streams bytes. S3 backend: 302 redirect to a
    short-lived presigned URL (credentials stay server-side).
    Unknown diffs, other users' diffs, and missing objects all 404
    without distinguishing (no cross-tenant oracle).
    """
    import io

    diff = get_object_or_404(
        ChangeDiff.objects.select_related("monitor"),
        id=diff_id,
        monitor__user=request.user,
    )
    if not diff.artifact_path:
        return Response(
            {"detail": "No artifact for this diff."},
            status=status.HTTP_404_NOT_FOUND,
        )
    if backend_name() == "s3":
        try:
            url = presigned_get_url(diff.artifact_path)
        except StorageError:
            return Response(
                {"detail": "Artifact not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        response = HttpResponse(status=302)
        response["Location"] = url
        response["Cache-Control"] = (
            f"private, max-age={url_expires_seconds()}"
        )
        return response
    try:
        content = load_bytes(diff.artifact_path)
    except StorageError:
        return Response(
            {"detail": "Artifact not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    key = diff.artifact_path
    if key.endswith(".png"):
        content_type = "image/png"
        filename = f"{diff_id}.png"
    elif key.endswith((".html", ".htm")):
        content_type = "text/html"
        filename = f"{diff_id}.html"
    else:
        content_type = "application/octet-stream"
        filename = f"{diff_id}.bin"
    response = FileResponse(
        io.BytesIO(content),
        content_type=content_type,
        filename=filename,
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def monitor_prices(request, monitor_id):
    monitor = _owned_monitor(request, monitor_id)

    limit = min(
        max(
            int(request.query_params.get("limit", 50)),
            1,
        ),
        100,
    )

    prices = (
        PricePoint.objects
        .filter(monitor=monitor)
        .order_by("-created_at")[:limit]
    )

    data = [
        {
            "id": str(point.id),
            "check_id": str(point.monitor_check_id),
            "price": str(point.price),
            "currency": point.currency,
            "raw_value": point.raw_value,
            "created_at": point.created_at,
        }
        for point in prices
    ]

    return Response(data)
