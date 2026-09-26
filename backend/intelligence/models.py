"""Intelligence layer models — competitive signals derived from public pages.

These models **do not crawl anything themselves**. Every row here is
produced either by an analysis the user explicitly requested, or by a
check the existing monitoring engine was already performing. A product
watch therefore costs no extra HTTP request and no extra browser slot.

Data-handling rules enforced here:

* ``UrlAnalysis`` and everything below it are private to the owning user
  (or to a workspace the user can see). Nothing in this app is ever
  published, and no analysis is created for an unauthenticated request.
* Only facts that were already public at the fetched URL are stored, and
  each stored value keeps the raw text it came from.
"""

import uuid

from django.conf import settings
from django.db import models


class UrlAnalysis(models.Model):
    """A cached, per-user analysis of a URL the user submitted."""

    STATUS_OK = "ok"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_OK, "Analyzed"),
        (STATUS_FAILED, "Failed"),
    )

    CONFIDENCE_HIGH = "high"
    CONFIDENCE_MEDIUM = "medium"
    CONFIDENCE_LOW = "low"
    CONFIDENCE_CHOICES = (
        (CONFIDENCE_HIGH, "High"),
        (CONFIDENCE_MEDIUM, "Medium"),
        (CONFIDENCE_LOW, "Low"),
    )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="url_analyses",
    )

    url = models.URLField(max_length=1000)

    normalized_url = models.CharField(max_length=1000)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OK,
    )

    page_kind = models.CharField(max_length=40, default="other")

    classification_confidence = models.CharField(
        max_length=10,
        choices=CONFIDENCE_CHOICES,
        default=CONFIDENCE_LOW,
    )

    classification_rationale = models.TextField(blank=True, default="")

    # Full evidence map: {field: {value, method, raw}}.
    facts = models.JSONField(default=dict, blank=True)

    # Flat values-only projection, convenient for the API and for exports.
    summary = models.JSONField(default=dict, blank=True)

    product_detected = models.BooleanField(default=False)

    status_code = models.PositiveSmallIntegerField(null=True, blank=True)

    response_time_ms = models.PositiveIntegerField(null=True, blank=True)

    error = models.TextField(blank=True, default="")

    fetched_at = models.DateTimeField()

    expires_at = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fetched_at"]
        indexes = [
            models.Index(fields=["user", "-fetched_at"]),
            models.Index(fields=["user", "normalized_url"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"{self.normalized_url} ({self.status})"

    @property
    def target_count(self):
        cached = getattr(self, "target_count_cache", None)
        if cached is not None:
            return cached
        return self.targets.count()


class DiscoveredTarget(models.Model):
    """A page Sitemyra suggests monitoring, with a factual rationale."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    analysis = models.ForeignKey(
        UrlAnalysis,
        on_delete=models.CASCADE,
        related_name="targets",
    )

    url = models.URLField(max_length=1000)

    kind = models.CharField(max_length=40, default="other")

    label = models.CharField(max_length=200)

    # Why Sitemyra proposes this target. Built only from observable
    # signals (URL path, link text, structured data) — never a guess about
    # the competitor's strategy.
    why = models.TextField(blank=True, default="")

    confidence = models.CharField(
        max_length=10,
        choices=UrlAnalysis.CONFIDENCE_CHOICES,
        default=UrlAnalysis.CONFIDENCE_MEDIUM,
    )

    # 0-100 ordering heuristic (see intelligence/services/classify.py).
    # This ranks links; it is NOT a business or quality score and is never
    # presented as one.
    relevance = models.PositiveSmallIntegerField(default=0)

    is_product = models.BooleanField(default=False)

    # True only for the page the user actually submitted. Recipes always
    # keep it, even when its kind is outside the recipe.
    is_primary = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "-relevance", "url"]
        indexes = [
            models.Index(fields=["analysis", "-relevance"]),
            models.Index(fields=["kind"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["analysis", "url"],
                name="unique_target_per_analysis",
            )
        ]

    def __str__(self):
        return f"{self.kind}: {self.url}"


class ProductWatch(models.Model):
    """First-class tracking of one product page attached to a monitor.

    One watch per monitor, so deleting the monitor removes the watch and
    all its history (CASCADE) with no orphan cleanup required.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    monitor = models.OneToOneField(
        "monitors.Monitor",
        on_delete=models.CASCADE,
        related_name="product_watch",
    )

    name = models.CharField(max_length=250)

    brand = models.CharField(max_length=150, blank=True, default="")

    currency = models.CharField(max_length=8, blank=True, default="")

    # False when the URL was not confirmed to be a product page. We still
    # record observations, but the UI labels them as unconfirmed rather
    # than presenting them as a competitor product.
    product_detected = models.BooleanField(default=False)

    detection_note = models.CharField(max_length=300, blank=True, default="")

    first_seen_at = models.DateTimeField(null=True, blank=True)

    last_seen_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-updated_at"]),
        ]

    def __str__(self):
        return self.name

    @property
    def latest_snapshot(self):
        cached = getattr(self, "latest_snapshot_preview", None)
        if cached is not None:
            return cached[0] if cached else None
        return self.snapshots.order_by("-captured_at").first()


class ProductSnapshot(models.Model):
    """The observed state of a product on one check.

    Every field is nullable on purpose: a page that stops publishing a
    value must be recorded as "not published now", which is different from
    "the value is zero".
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    product_watch = models.ForeignKey(
        ProductWatch,
        on_delete=models.CASCADE,
        related_name="snapshots",
    )

    monitor_check = models.ForeignKey(
        "monitors.MonitorCheck",
        on_delete=models.CASCADE,
        related_name="product_snapshots",
        null=True,
        blank=True,
    )

    captured_at = models.DateTimeField()

    name = models.CharField(max_length=250, blank=True, default="")
    brand = models.CharField(max_length=150, blank=True, default="")
    sku = models.CharField(max_length=100, blank=True, default="")
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    list_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=8, blank=True, default="")
    availability = models.CharField(max_length=40, blank=True, default="")
    condition = models.CharField(max_length=60, blank=True, default="")
    rating = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    review_count = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True, default="")
    badges = models.JSONField(default=list, blank=True)
    variants = models.JSONField(default=list, blank=True)
    images = models.JSONField(default=list, blank=True)
    bundles = models.JSONField(default=list, blank=True)
    specs = models.JSONField(default=dict, blank=True)
    shipping = models.JSONField(default=dict, blank=True)
    price_valid_until = models.CharField(max_length=60, blank=True, default="")

    source_url = models.URLField(max_length=1000)

    # Which extraction path produced each value, so a change caused by a
    # different reading method is visible instead of being reported as a
    # competitor action.
    extraction = models.JSONField(default=dict, blank=True)

    # {field: raw text} — the evidence itself.
    evidence = models.JSONField(default=dict, blank=True)

    # Field names that differ from the previous snapshot.
    changed_fields = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-captured_at"]
        indexes = [
            models.Index(fields=["product_watch", "-captured_at"]),
            models.Index(fields=["captured_at"]),
        ]

    def __str__(self):
        return f"{self.product_watch_id} @ {self.captured_at}"


class ProductChange(models.Model):
    """One field-level change on a tracked product — the timeline row.

    This is the row an alert points at, an export includes, and Phase 2
    turns into a feed entry. It always carries before, after, the rule that
    classified it, the source URL and the detection time.
    """

    SEVERITY_CHOICES = (
        ("informational", "Informational"),
        ("minor", "Minor"),
        ("important", "Important"),
        ("critical", "Critical"),
    )

    CATEGORY_CHOICES = (
        ("pricing", "Pricing"),
        ("product", "Product"),
        ("features", "Features"),
        ("availability", "Availability"),
        ("content", "Content"),
        ("reviews", "Reviews"),
        ("marketing", "Marketing"),
    )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    product_watch = models.ForeignKey(
        ProductWatch,
        on_delete=models.CASCADE,
        related_name="changes",
    )

    previous_snapshot = models.ForeignKey(
        ProductSnapshot,
        on_delete=models.SET_NULL,
        related_name="changes_to",
        null=True,
        blank=True,
    )

    current_snapshot = models.ForeignKey(
        ProductSnapshot,
        on_delete=models.SET_NULL,
        related_name="changes_from",
        null=True,
        blank=True,
    )

    monitor_check = models.ForeignKey(
        "monitors.MonitorCheck",
        on_delete=models.SET_NULL,
        related_name="product_changes",
        null=True,
        blank=True,
    )

    field = models.CharField(max_length=40)

    label = models.CharField(max_length=80)

    before = models.TextField(blank=True, default="")

    after = models.TextField(blank=True, default="")

    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default="informational",
    )

    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default="content",
    )

    # Human-readable reason this row exists, e.g.
    # "Price decreased by 23.1% (129.00 → 99.00)."
    basis = models.TextField(blank=True, default="")

    # The named rule that classified it, e.g. "rule:price".
    rule = models.CharField(max_length=40, blank=True, default="")

    evidence = models.JSONField(default=dict, blank=True)

    source_url = models.URLField(max_length=1000, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product_watch", "-created_at"]),
            models.Index(fields=["category", "-created_at"]),
            models.Index(fields=["severity", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.label}: {self.before} → {self.after}"
