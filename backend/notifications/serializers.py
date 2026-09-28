from rest_framework import serializers

from .models import (
    AlertChannel,
    NotificationDelivery,
    NotificationEvent,
    NotificationPreference,
)


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    email_delivery_configured = serializers.SerializerMethodField()

    class Meta:
        model = NotificationPreference
        fields = (
            "email_on_change",
            "email_on_failure",
            "email_on_recovery",
            "email_weekly_digest",
            "email_delivery_configured",
        )
        read_only_fields = ("email_delivery_configured",)

    def get_email_delivery_configured(self, _obj):
        from common.integration_status import smtp_missing_environment

        return not smtp_missing_environment()


class AlertChannelSerializer(serializers.ModelSerializer):
    # Write-only secret; reads return a masked preview.
    config = serializers.CharField(write_only=True, required=True)
    config_preview = serializers.CharField(
        source="masked_config", read_only=True
    )

    class Meta:
        model = AlertChannel
        fields = (
            "id",
            "channel_type",
            "name",
            "workspace",
            "config",
            "config_preview",
            "verified",
            "created_at",
        )
        read_only_fields = ("id", "config_preview", "verified", "created_at")

    def validate_channel_type(self, value):
        # Email is delivered via account SMTP + NotificationPreference, not
        # as an HTTP channel; SMS has no provider. Reject new records for
        # both; existing rows remain readable as "unsupported".
        if value in AlertChannel.UNSUPPORTED_TYPES:
            if value == AlertChannel.SMS:
                raise serializers.ValidationError(
                    "Channel type 'sms' is not implemented. "
                    "Use slack, discord, or webhook."
                )
            raise serializers.ValidationError(
                f"Channel type '{value}' is not delivered as a webhook. "
                "Email alerts use your account email (see notification "
                "preferences). Use slack, discord, or webhook."
            )
        return value

    def create(self, validated_data):
        raw = validated_data.pop("config", "")
        validated_data["config_encrypted"] = raw
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "config" in validated_data:
            instance.config_encrypted = validated_data.pop("config")
        return super().update(instance, validated_data)


class NotificationDeliveryHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationDelivery
        fields = ("channel_type", "status", "attempts", "created_at")
        read_only_fields = fields


class NotificationHistorySerializer(serializers.ModelSerializer):
    monitor_id = serializers.UUIDField(read_only=True)
    monitor_name = serializers.CharField(source="monitor.name", read_only=True)
    deliveries = NotificationDeliveryHistorySerializer(many=True, read_only=True)

    class Meta:
        model = NotificationEvent
        fields = (
            "id",
            "monitor_id",
            "monitor_name",
            "event_type",
            "created_at",
            "deliveries",
        )
        read_only_fields = fields
