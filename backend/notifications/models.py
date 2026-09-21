import uuid

from django.conf import settings
from django.db import models

from common.crypto import EncryptedTextField


class NotificationPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    email_on_change = models.BooleanField(default=True)
    email_on_failure = models.BooleanField(default=True)
    email_on_recovery = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class NotificationEvent(models.Model):
    CHANGE = "change"
    FAILURE = "failure"
    RECOVERY = "recovery"

    EVENT_CHOICES = (
        (CHANGE, "Change"),
        (FAILURE, "Failure"),
        (RECOVERY, "Recovery"),
    )

    monitor = models.ForeignKey(
        "monitors.Monitor",
        on_delete=models.CASCADE,
        related_name="notification_events",
    )
    monitor_check = models.ForeignKey(
        "monitors.MonitorCheck",
        on_delete=models.CASCADE,
        related_name="notification_events",
    )
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_CHOICES,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["monitor_check", "event_type"],
                name="unique_notification_event_per_check",
            )
        ]
        indexes = [
            models.Index(
                fields=["monitor", "event_type", "-created_at"]
            ),
        ]


class AlertChannel(models.Model):
    """User / workspace alert destinations. Secrets encrypted at rest.

    `config_encrypted` holds the webhook URL (Slack, Discord, generic
    webhook) encrypted with Fernet; never returned in full via API.

    Email delivery uses the account email via NotificationPreference +
    Django SMTP and is NOT represented as an HTTP channel. SMS is not
    implemented and stays rejected at the serializer layer.
    """

    SLACK = "slack"
    DISCORD = "discord"
    EMAIL = "email"
    WEBHOOK = "webhook"
    SMS = "sms"
    TYPE_CHOICES = (
        (SLACK, "Slack"),
        (DISCORD, "Discord"),
        (EMAIL, "Email"),
        (WEBHOOK, "Webhook"),
        (SMS, "SMS"),
    )
    # Phase 1: only these deliver via a real provider today. EMAIL/SMS
    # choices are retained for DB compatibility but treated as unsupported.
    SUPPORTED_TYPES = (SLACK, DISCORD, WEBHOOK)
    UNSUPPORTED_TYPES = (EMAIL, SMS)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="alert_channels",
    )
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="alert_channels",
        null=True,
        blank=True,
    )
    channel_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    name = models.CharField(max_length=120)
    # Encrypted webhook URL / API key / phone number.
    config_encrypted = EncryptedTextField(default="", blank=True)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def masked_config(self) -> str:
        raw = self.config_encrypted or ""
        if len(raw) <= 12:
            return "••••"
        return f"{raw[:6]}…{raw[-4:]}"

    def __str__(self):
        return f"{self.name} ({self.channel_type})"


class MonitorAlertChannel(models.Model):
    """Explicit monitor → channel routing (Phase 7).

    A monitor only notifies channels linked here. No owner-wide or
    workspace-wide fan-out: unlinked channels are never notified.
    Tenant isolation is enforced at attach time (channel must belong to
    the requesting user) and re-checked at dispatch time.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    monitor = models.ForeignKey(
        "monitors.Monitor",
        on_delete=models.CASCADE,
        related_name="alert_routes",
    )
    channel = models.ForeignKey(
        AlertChannel,
        on_delete=models.CASCADE,
        related_name="monitor_routes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["monitor", "channel"],
                name="unique_monitor_channel",
            )
        ]
        indexes = [
            models.Index(fields=["monitor"]),
            models.Index(fields=["channel"]),
        ]

    def __str__(self):
        return f"{self.monitor_id} -> {self.channel_id}"


class NotificationDelivery(models.Model):
    """Observable per-channel delivery record (Phase 7).

    One row per (event, channel) attempt-batch. `channel` is null for
    owner-email (SMTP) deliveries. Never stores secrets.
    """

    DELIVERED = "delivered"
    FAILED = "failed"
    SKIPPED = "skipped"
    STATUS_CHOICES = (
        (DELIVERED, "Delivered"),
        (FAILED, "Failed"),
        (SKIPPED, "Skipped"),
    )

    event = models.ForeignKey(
        NotificationEvent,
        on_delete=models.CASCADE,
        related_name="deliveries",
        null=True,
        blank=True,
    )
    monitor = models.ForeignKey(
        "monitors.Monitor",
        on_delete=models.CASCADE,
        related_name="notification_deliveries",
    )
    channel = models.ForeignKey(
        AlertChannel,
        on_delete=models.SET_NULL,
        related_name="deliveries",
        null=True,
        blank=True,
    )
    # Denormalized for safe log/API use without joining secrets.
    channel_type = models.CharField(max_length=20, default="")
    event_type = models.CharField(max_length=20, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    attempts = models.PositiveSmallIntegerField(default=1)
    # Truncated provider detail (status code / error class). No URLs/secrets.
    detail = models.CharField(max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["monitor", "-created_at"]),
            models.Index(fields=["channel", "-created_at"]),
        ]
