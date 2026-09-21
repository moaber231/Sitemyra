from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Workspace, WorkspaceInvite, WorkspaceMembership
from .permissions import require_role, user_role_in_workspace
from .serializers import (
    InviteSerializer,
    MembershipSerializer,
    WorkspaceSerializer,
)


class WorkspaceViewSet(viewsets.ModelViewSet):
    serializer_class = WorkspaceSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Workspace.objects.all()
        return Workspace.objects.filter(
            Q(owner=user) | Q(memberships__user=user)
        ).distinct()

    def perform_create(self, serializer):
        workspace = serializer.save(owner=self.request.user)
        # Owner gets an explicit membership for uniform RBAC checks.
        WorkspaceMembership.objects.get_or_create(
            workspace=workspace,
            user=self.request.user,
            defaults={"role": WorkspaceMembership.OWNER},
        )

    def perform_update(self, serializer):
        workspace = self.get_object()
        if not require_role(self.request.user, workspace, minimum="admin"):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Only Owner/Admin can rename a workspace.")
        serializer.save()

    def perform_destroy(self, instance):
        if not require_role(self.request.user, instance, minimum="owner"):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Only the Owner can delete a workspace.")
        instance.delete()

    @action(detail=True, methods=["get", "post"])
    def members(self, request, pk=None):
        workspace = self.get_object()
        if request.method == "GET":
            if user_role_in_workspace(request.user, workspace) is None:
                return Response(
                    {"detail": "Not a workspace member."}, status=403
                )
            memberships = workspace.memberships.select_related("user")
            return Response(MembershipSerializer(memberships, many=True).data)
        # POST = change role (admin+ only)
        if not require_role(request.user, workspace, minimum="admin"):
            return Response(
                {"detail": "Only Owner/Admin can manage members."}, status=403
            )
        membership = get_object_or_404(
            WorkspaceMembership, workspace=workspace, pk=request.data.get("id")
        )
        new_role = request.data.get("role")
        if new_role not in dict(WorkspaceMembership.ROLE_CHOICES):
            return Response({"detail": "Invalid role."}, status=400)
        if new_role == WorkspaceMembership.OWNER and not require_role(
            request.user, workspace, minimum="owner"
        ):
            return Response(
                {"detail": "Only Owner can grant Owner role."}, status=403
            )
        membership.role = new_role
        membership.save(update_fields=["role"])
        return Response(MembershipSerializer(membership).data)

    @action(detail=True, methods=["delete"], url_path="members/(?P<member_id>[^/.]+)")
    def remove_member(self, request, pk=None, member_id=None):
        workspace = self.get_object()
        if not require_role(request.user, workspace, minimum="admin"):
            return Response(
                {"detail": "Only Owner/Admin can remove members."}, status=403
            )
        membership = get_object_or_404(
            WorkspaceMembership, workspace=workspace, pk=member_id
        )
        if membership.role == WorkspaceMembership.OWNER:
            return Response(
                {"detail": "Cannot remove an Owner."}, status=400
            )
        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get", "post"])
    def invites(self, request, pk=None):
        workspace = self.get_object()
        if request.method == "GET":
            if user_role_in_workspace(request.user, workspace) is None:
                return Response(
                    {"detail": "Not a workspace member."}, status=403
                )
            invites = workspace.invites.filter(accepted=False)
            return Response(InviteSerializer(invites, many=True).data)
        if not require_role(request.user, workspace, minimum="admin"):
            return Response(
                {"detail": "Only Owner/Admin can invite members."}, status=403
            )
        serializer = InviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(workspace=workspace, created_by=request.user)
        return Response(serializer.data, status=201)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def accept_invite(request, token):
    invite = get_object_or_404(WorkspaceInvite, token=token, accepted=False)
    # Email match is advisory; allow any authenticated user to claim in dev.
    WorkspaceMembership.objects.update_or_create(
        workspace=invite.workspace,
        user=request.user,
        defaults={"role": invite.role},
    )
    invite.accepted = True
    invite.save(update_fields=["accepted"])
    return Response(
        {
            "detail": f"Joined workspace {invite.workspace.name}.",
            "workspace_id": str(invite.workspace.id),
            "role": invite.role,
        }
    )
