import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, URLValidator
from django.db import models
from django.db.models import Q


class Monitor(models.Model):
    INTERVAL_30_SECONDS = 30
    INTERVAL_1_MINUTE = 60
    INTERVAL_5_MINUTES = 300
    INTERVAL_15_MINUTES = 900
    INTERVAL_30_MINUTES = 1800
    INTERVAL_60_MINUTES = 3600

    INTERVAL_CHOICES = (
        (INTERVAL_30_SECONDS, "30 seconds"),
        (INTERVAL_1_MINUTE, "1 minute"),
        (INTERVAL_5_MINUTES, "5 minutes"),
        (INTERVAL_15_MINUTES, "15 minutes"),
        (INTERVAL_30_MINUTES, "30 minutes"),
        (INTERVAL_60_MINUTES, "60 minutes"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="monitors",
    )

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="monitors",
        null=True,
        blank=True,
    )

    name = models.CharField(max_length=150)

    url = models.URLField(
        validators=[URLValidator(schemes=("http", "https"))]
    )

    active = models.BooleanField(default=True)

    check_interval = models.PositiveIntegerField(
        choices=INTERVAL_CHOICES,
        default=INTERVAL_60_MINUTES,
    )

    timeout = models.PositiveIntegerField(
        default=15,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(120),
        ],
    )

    next_check_at = models.DateTimeField(null=True, blank=True)

    last_checked_at = models.DateTimeField(null=True, blank=True)

    last_success_at = models.DateTimeField(null=True, blank=True)

    last_changed_at = models.DateTimeField(null=True, blank=True)

    last_content_hash = models.CharField(
        max_length=64,
        blank=True,
    )

    last_status_code = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(fields=["user", "active"]),
            models.Index(fields=["active", "next_check_at"]),
            models.Index(fields=["user", "next_check_at"]),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(timeout__gte=1) & Q(timeout__lte=120),
                name="monitor_timeout_range",
            ),
        ]

    @property
    def status(self):
        if not self.active:
            return "paused"

        if not self.last_checked_at:
            return "never_checked"

        latest_check = self.checks.order_by("-checked_at").first()

        if not latest_check:
            return "never_checked"

        if latest_check.error:
            return "failing"

        if latest_check.changed:
            return "changed"

        return "healthy"

    def __str__(self):
        return self.name


class MonitorCheck(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    monitor = models.ForeignKey(
        Monitor,
        on_delete=models.CASCADE,
        related_name="checks",
    )

    checked_at = models.DateTimeField()

    status_code = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    response_time_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    content_hash = models.CharField(
        max_length=64,
        blank=True,
    )

    changed = models.BooleanField(default=False)

    error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-checked_at"]

        indexes = [
            models.Index(
                fields=["monitor", "-checked_at"],
            ),
            models.Index(
                fields=["monitor", "changed"],
            ),
        ]

    def __str__(self):
        return f"{self.monitor.name} - {self.checked_at}"


class AdvancedMonitorConfig(models.Model):
    HTTP = "http"
    DOM = "dom"
    SCREENSHOT = "screenshot"
    PRICE = "price"

    MODE_CHOICES = (
        (HTTP, "HTTP"),
        (DOM, "DOM"),
        (SCREENSHOT, "Screenshot"),
        (PRICE, "Price"),
    )

    monitor = models.OneToOneField(
        Monitor,
        on_delete=models.CASCADE,
        related_name="advanced_config",
    )

    mode = models.CharField(
        max_length=20,
        choices=MODE_CHOICES,
        default=HTTP,
    )

    selector = models.TextField(
        blank=True,
        default="",
        help_text="Optional CSS selector limiting the monitored content.",
    )

    price_selector = models.TextField(
        blank=True,
        default="",
        help_text="CSS selector used by price monitors.",
    )

    price_currency = models.CharField(
        max_length=3,
        blank=True,
        default="",
    )

    screenshot_threshold = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=0.500,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.monitor.name} ({self.mode})"


class ChangeDiff(models.Model):
    DOM = "dom"
    SCREENSHOT = "screenshot"
    PRICE = "price"

    DIFF_TYPES = (
        (DOM, "DOM"),
        (SCREENSHOT, "Screenshot"),
        (PRICE, "Price"),
    )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    monitor = models.ForeignKey(
        Monitor,
        on_delete=models.CASCADE,
        related_name="change_diffs",
    )

    previous_check = models.ForeignKey(
        MonitorCheck,
        on_delete=models.CASCADE,
        related_name="previous_change_diffs",
    )

    current_check = models.ForeignKey(
        MonitorCheck,
        on_delete=models.CASCADE,
        related_name="current_change_diffs",
    )

    diff_type = models.CharField(
        max_length=20,
        choices=DIFF_TYPES,
    )

    summary = models.TextField(
        blank=True,
        default="",
    )

    diff_percentage = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
    )

    artifact_path = models.TextField(
        blank=True,
        default="",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["monitor", "-created_at"],
            ),
        ]

    def __str__(self):
        return f"{self.monitor.name} - {self.diff_type}"


class PricePoint(models.Model):
    monitor = models.ForeignKey(
        Monitor,
        on_delete=models.CASCADE,
        related_name="price_points",
    )

    monitor_check = models.OneToOneField(
        MonitorCheck,
        on_delete=models.CASCADE,
        related_name="price_point",
    )

    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    currency = models.CharField(
        max_length=3,
    )

    raw_value = models.CharField(
        max_length=100,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["monitor", "-created_at"],
            ),
        ]

    def __str__(self):
        return f"{self.monitor.name}: {self.price} {self.currency}"
