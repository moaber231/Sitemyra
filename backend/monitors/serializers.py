from urllib.parse import urlparse

from rest_framework import serializers

from .models import Monitor, MonitorCheck


class MonitorSerializer(serializers.ModelSerializer):
    status = serializers.ReadOnlyField()
    last_response_time_ms = serializers.SerializerMethodField()

    class Meta:
        model = Monitor
        fields = (
            "id",
            "name",
            "url",
            "workspace",
            "active",
            "check_interval",
            "timeout",
            "next_check_at",
            "last_checked_at",
            "last_success_at",
            "last_changed_at",
            "last_content_hash",
            "last_status_code",
            "last_response_time_ms",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "active",
            "next_check_at",
            "last_checked_at",
            "last_success_at",
            "last_changed_at",
            "last_content_hash",
            "last_status_code",
            "last_response_time_ms",
            "status",
            "created_at",
            "updated_at",
        )

    def get_last_response_time_ms(self, obj):
        # latest_check is prefetched as a single-row list on list views
        # (plan D9): one query total instead of one per monitor.
        latest_check = obj.latest_check

        if not latest_check:
            return None

        return latest_check.response_time_ms

    def validate_url(self, value):
        parsed = urlparse(value)

        if parsed.scheme.lower() not in ("http", "https"):
            raise serializers.ValidationError(
                "Only HTTP and HTTPS URLs are supported."
            )

        if not parsed.hostname:
            raise serializers.ValidationError("Invalid URL.")

        if parsed.username or parsed.password:
            raise serializers.ValidationError(
                "URLs containing credentials are not supported."
            )

        if parsed.port is not None and parsed.port not in (80, 443):
            raise serializers.ValidationError(
                "Only ports 80 and 443 are supported."
            )

        return value

    def validate_check_interval(self, value):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            from billing.models import get_plan_for_user, plan_limits

            plan = get_plan_for_user(request.user)
            minimum = plan_limits(plan)["min_interval_seconds"]
            if value < minimum:
                raise serializers.ValidationError(
                    f"Plan '{plan}' requires check_interval >= {minimum}s. "
                    "Upgrade for faster checks."
                )
        return value

    def validate_workspace(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        from workspaces.permissions import user_role_in_workspace

        if (
            request
            and user_role_in_workspace(request.user, value) is None
        ):
            raise serializers.ValidationError(
                "You are not a member of this workspace."
            )
        return value


class MonitorCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonitorCheck
        fields = (
            "id",
            "monitor",
            "checked_at",
            "status_code",
            "response_time_ms",
            "content_hash",
            "changed",
            "error",
            "created_at",
        )
        read_only_fields = fields