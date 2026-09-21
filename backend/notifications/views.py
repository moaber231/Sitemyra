from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.models import get_plan_for_user, plan_limits
from workspaces.models import Workspace
from workspaces.permissions import require_role

from .models import AlertChannel, NotificationPreference
from .serializers import AlertChannelSerializer, NotificationPreferenceSerializer
from .services import test_channel_delivery


class NotificationPreferenceView(generics.RetrieveUpdateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = NotificationPreferenceSerializer

    def get_object(self):
        preferences, _ = NotificationPreference.objects.get_or_create(
            user=self.request.user
        )
        return preferences


class AlertChannelListCreateView(generics.ListCreateAPIView):
    serializer_class = AlertChannelSerializer

    def get_queryset(self):
        return AlertChannel.objects.filter(
            user=self.request.user
        ).select_related("workspace")

    def create(self, request, *args, **kwargs):
        # Enforce plan-based alert channel limits (metered usage).
        plan = get_plan_for_user(request.user)
        limit = plan_limits(plan)["max_alert_channels"]
        current = AlertChannel.objects.filter(user=request.user).count()
        if current >= limit:
            return Response(
                {
                    "detail": (
                        f"Plan '{plan}' allows {limit} alert channel(s). "
                        "Upgrade to add more."
                    )
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )
        workspace_id = request.data.get("workspace")
        if workspace_id:
            workspace = get_object_or_404(Workspace, pk=workspace_id)
            # RBAC: Viewers cannot create webhook configs.
            if not require_role(request.user, workspace, minimum="admin"):
                return Response(
                    {
                        "detail": (
                            "Only workspace Owner/Admin can configure "
                            "webhooks."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AlertChannelDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AlertChannelSerializer

    def get_queryset(self):
        return AlertChannel.objects.filter(user=self.request.user)

    def update(self, request, *args, **kwargs):
        channel = self.get_object()
        if channel.workspace_id and not require_role(
            request.user, channel.workspace, minimum="admin"
        ):
            return Response(
                {"detail": "Only workspace Owner/Admin can edit webhooks."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        channel = self.get_object()
        if channel.workspace_id and not require_role(
            request.user, channel.workspace, minimum="admin"
        ):
            return Response(
                {"detail": "Only workspace Owner/Admin can delete webhooks."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)


class AlertChannelTestView(APIView):
    """POST /channels/<uuid>/test/ — verify a channel via the real path.

    Authenticated, owner-only (404 for other tenants — no oracle).
    Uses the same delivery implementation as real notifications and
    never returns secrets. 200 + ok:true means delivered; 502 + ok:false
    means the provider rejected/failed it (nothing is faked).
    """

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, pk):
        channel = get_object_or_404(
            AlertChannel, pk=pk, user=request.user
        )
        if channel.workspace_id and not require_role(
            request.user, channel.workspace, minimum="admin"
        ):
            return Response(
                {"detail": "Only workspace Owner/Admin can test webhooks."},
                status=status.HTTP_403_FORBIDDEN,
            )
        result = test_channel_delivery(channel, user=request.user)
        payload = {
            "ok": bool(result.get("ok")),
            "channel_id": str(channel.id),
            "channel_type": channel.channel_type,
            "verified": channel.verified,
            "config_preview": channel.masked_config,
            "attempts": result.get("attempts", 0),
            "detail": (
                "Test notification delivered."
                if result.get("ok")
                else result.get("error", "Delivery failed.")
            ),
        }
        if result.get("status_code") is not None:
            payload["status_code"] = result["status_code"]
        if result.get("ok"):
            return Response(payload, status=status.HTTP_200_OK)
        if result.get("status") == "skipped" or result.get("permanent"):
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload, status=status.HTTP_502_BAD_GATEWAY)
