from rest_framework import permissions

from .models import WorkspaceMembership


def user_role_in_workspace(user, workspace):
    if user.is_superuser:
        return WorkspaceMembership.OWNER
    if workspace.owner_id == user.id:
        return WorkspaceMembership.OWNER
    membership = (
        WorkspaceMembership.objects.filter(workspace=workspace, user=user).first()
    )
    return membership.role if membership else None


def require_role(user, workspace, minimum="viewer"):
    role = user_role_in_workspace(user, workspace)
    if role is None:
        return False
    rank = WorkspaceMembership.ROLE_RANK
    return rank.get(role, 0) >= rank.get(minimum, 1)


class IsWorkspaceMember(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        workspace = getattr(obj, "workspace", obj)
        return user_role_in_workspace(request.user, workspace) is not None


class IsWorkspaceAdminOrOwner(permissions.BasePermission):
    """Only Owner/Admin may manage API keys & webhook configs."""

    def has_object_permission(self, request, view, obj):
        workspace = getattr(obj, "workspace", obj)
        if request.method in permissions.SAFE_METHODS:
            return user_role_in_workspace(request.user, workspace) is not None
        return require_role(request.user, workspace, minimum="admin")
