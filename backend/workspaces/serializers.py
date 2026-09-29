from rest_framework import serializers

from .models import Workspace, WorkspaceInvite, WorkspaceMembership


class WorkspaceSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = ("id", "name", "slug", "role", "member_count", "created_at")
        read_only_fields = ("id", "slug", "role", "member_count", "created_at")

    def get_role(self, obj):
        from .permissions import user_role_in_workspace

        user = self.context["request"].user
        return user_role_in_workspace(user, obj)

    def get_member_count(self, obj):
        return obj.memberships.count() + 1  # +owner


class MembershipSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = WorkspaceMembership
        fields = ("id", "user", "email", "role", "created_at")
        read_only_fields = ("id", "user", "email", "created_at")


class InviteSerializer(serializers.ModelSerializer):
    # Where the inviter goes when email is unavailable or fails. Derived, and
    # only ever visible to Owner/Admin because the whole endpoint is gated.
    accept_url = serializers.SerializerMethodField()

    class Meta:
        model = WorkspaceInvite
        fields = (
            "id",
            "email",
            "role",
            "token",
            "accepted",
            "created_at",
            "accept_url",
            "email_status",
            "email_sent_at",
            "email_error",
        )
        read_only_fields = (
            "id",
            "token",
            "accepted",
            "created_at",
            "accept_url",
            "email_status",
            "email_sent_at",
            "email_error",
        )

    def get_accept_url(self, obj):
        from .invitation_email import invitation_accept_url

        return invitation_accept_url(obj)

    def validate_role(self, value):
        if value == WorkspaceMembership.OWNER:
            raise serializers.ValidationError(
                "Owner role cannot be granted via invite. Transfer ownership instead."
            )
        return value
