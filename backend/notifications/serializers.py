from rest_framework import serializers

from .models import AlertChannel, NotificationPreference


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = (
            "email_on_change",
            "email_on_failure",
            "email_on_recovery",
        )


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
