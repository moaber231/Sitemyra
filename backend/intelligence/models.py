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

import hashlib
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


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


# ==========================================================================
# Phase 2 — Competitors, discovery candidates and the market feed.
#
# These are DERIVED records. A SignalEvent is built from a row that already
# exists (a ProductChange, a changed MonitorCheck, a ChangeDiff); it never
# invents a change and it never re-derives one. `source_key` makes that
# derivation idempotent, so a retried task or a re-run of the beat tick
# cannot duplicate a feed entry.
# ==========================================================================


class Competitor(models.Model):
    """A tracked business, grouped by registrable domain.

    Created automatically when a monitor is activated, so pre-existing
    monitors are enriched rather than migrated.
    """

    RELATIONSHIP_TRACKED = "tracked"
    RELATIONSHIP_DIRECT = "direct"
    RELATIONSHIP_ADJACENT = "adjacent"
    RELATIONSHIP_ALTERNATIVE = "alternative"
    RELATIONSHIP_CHOICES = (
        (RELATIONSHIP_TRACKED, "Tracked"),
        (RELATIONSHIP_DIRECT, "Direct competitor"),
        (RELATIONSHIP_ADJACENT, "Adjacent competitor"),
        (RELATIONSHIP_ALTERNATIVE, "Alternative"),
    )

    STATE_ACTIVE = "active"
    STATE_QUIET = "quiet"
    STATE_PAUSED = "paused"
    STATE_CHOICES = (
        (STATE_ACTIVE, "Changed recently"),
        (STATE_QUIET, "No significant change detected"),
        (STATE_PAUSED, "Not monitored"),
    )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="competitors",
    )

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="competitors",
        null=True,
        blank=True,
    )

    name = models.CharField(max_length=200)

    homepage_url = models.URLField(max_length=1000)

    # Registrable domain, e.g. "example.co.uk" for shop.example.co.uk.
    domain = models.CharField(max_length=255, db_index=True)

    relationship = models.CharField(
        max_length=20,
        choices=RELATIONSHIP_CHOICES,
        default=RELATIONSHIP_TRACKED,
    )

    # Set only from observed facts, never asserted. Same constraint as
    # ChangeExplanation: a competitive-intelligence product must be able to
    # show why it thinks this is a competitor.
    relationship_reasons = models.JSONField(default=list, blank=True)

    # Verbatim signal that justified the relationship, for the battlecard.
    signals = models.JSONField(default=list, blank=True)

    first_seen_at = models.DateTimeField(null=True, blank=True)

    last_activity_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_activity_at", "name"]
        indexes = [
            models.Index(fields=["user", "domain"]),
            models.Index(fields=["workspace", "-last_activity_at"]),
            models.Index(fields=["user", "-last_activity_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "domain"],
                name="unique_competitor_per_user_domain",
            )
        ]

    def __str__(self):
        return self.name


class CompetitorCandidate(models.Model):
    """A proposed competitor. NEVER monitored until approved.

    This is the safety property of Feature 2: discovery produces
    suggestions with their reasons attached, and the user decides.
    """

    RELATIONSHIP_CHOICES = Competitor.RELATIONSHIP_CHOICES

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    competitor = models.ForeignKey(
        Competitor,
        on_delete=models.CASCADE,
        related_name="candidates",
    )

    url = models.URLField(max_length=1000)

    domain = models.CharField(max_length=255)

    relationship = models.CharField(
        max_length=20,
        choices=RELATIONSHIP_CHOICES,
        default=Competitor.RELATIONSHIP_ADJACENT,
    )

    # A list of factual statements: "Product category: project management",
    # "Shared capability keywords: 'invoicing', 'gantt'". Never "they are a
    # big competitor".
    reasons = models.JSONField(default=list, blank=True)

    confidence = models.CharField(
        max_length=10,
        choices=UrlAnalysis.CONFIDENCE_CHOICES,
        default=UrlAnalysis.CONFIDENCE_MEDIUM,
    )

    approved = models.BooleanField(default=False)

    approved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-confidence", "domain"]
        indexes = [
            models.Index(fields=["competitor", "approved"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["competitor", "url"],
                name="unique_candidate_per_competitor_url",
            )
        ]

    def __str__(self):
        return f"{self.relationship}: {self.url}"


class SignalEvent(models.Model):
    """One entry in the chronological market feed.

    Derived, never authored: `source_key` points at the row it came from
    (a ProductChange, a MonitorCheck, a ChangeDiff) and makes the
    derivation idempotent.
    """

    KIND_PRICING = "pricing"
    KIND_PRODUCTS = "products"
    KIND_FEATURES = "features"
    KIND_MARKETING = "marketing"
    KIND_CONTENT = "content"
    KIND_HIRING = "hiring"
    KIND_OTHER = "other"
    KIND_CHOICES = (
        (KIND_PRICING, "Pricing"),
        (KIND_PRODUCTS, "Products"),
        (KIND_FEATURES, "Features"),
        (KIND_MARKETING, "Marketing"),
        (KIND_CONTENT, "Content"),
        (KIND_HIRING, "Hiring"),
        (KIND_OTHER, "Other"),
    )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="signal_events",
    )

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="signal_events",
        null=True,
        blank=True,
    )

    competitor = models.ForeignKey(
        Competitor,
        on_delete=models.CASCADE,
        related_name="signal_events",
        null=True,
        blank=True,
    )

    # CASCADE: deleting a monitor removes its feed entries. A feed entry
    # about a page that no longer exists is worse than no feed entry.
    monitor = models.ForeignKey(
        "monitors.Monitor",
        on_delete=models.CASCADE,
        related_name="signal_events",
    )

    monitor_check = models.ForeignKey(
        "monitors.MonitorCheck",
        on_delete=models.CASCADE,
        related_name="signal_events",
        null=True,
        blank=True,
    )

    product_change = models.ForeignKey(
        ProductChange,
        on_delete=models.CASCADE,
        related_name="signal_events",
        null=True,
        blank=True,
    )

    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_OTHER)

    headline = models.CharField(max_length=300)

    summary = models.TextField(blank=True, default="")

    # Human-readable before/after, kept small so the feed row stays cheap.
    before = models.CharField(max_length=300, blank=True, default="")
    after = models.CharField(max_length=300, blank=True, default="")

    severity = models.CharField(
        max_length=20,
        choices=ProductChange.SEVERITY_CHOICES,
        default="informational",
    )

    source_url = models.URLField(max_length=1000, blank=True, default="")

    # Idempotency key for the derivation. Unique.
    source_key = models.CharField(max_length=120, unique=True)

    evidence = models.JSONField(default=dict, blank=True)

    detected_at = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-detected_at", "-created_at"]
        indexes = [
            models.Index(fields=["user", "-detected_at"]),
            models.Index(fields=["user", "kind", "-detected_at"]),
            models.Index(fields=["competitor", "-detected_at"]),
            models.Index(fields=["workspace", "-detected_at"]),
            models.Index(fields=["monitor", "-detected_at"]),
        ]

    def __str__(self):
        return f"{self.kind}: {self.headline}"


class MarketSignal(models.Model):
    """A cross-competitor pattern (Phase 3).

    Presented as a MARKET SIGNAL with its evidence attached, never as a
    business opportunity and never as a prediction. A minimum evidence
    threshold is enforced by the detector, not by the UI.
    """

    KIND_PRICE_INCREASE_CLUSTER = "price_increase_cluster"
    KIND_PRICE_DECREASE_CLUSTER = "price_decrease_cluster"
    KIND_FEATURE_PARITY = "feature_parity"
    KIND_FEATURE_REMOVAL = "feature_removal"
    KIND_NEW_CATEGORY = "new_category"
    KIND_NEW_PRODUCT = "new_product"
    KIND_HIRING_PUSH = "hiring_push"
    KIND_CHOICES = (
        (KIND_PRICE_INCREASE_CLUSTER, "Several competitors increased prices"),
        (KIND_PRICE_DECREASE_CLUSTER, "Several competitors cut prices"),
        (KIND_FEATURE_PARITY, "Several competitors shipped a similar capability"),
        (KIND_FEATURE_REMOVAL, "A competitor removed a capability"),
        (KIND_NEW_CATEGORY, "A competitor entered a new category"),
        (KIND_NEW_PRODUCT, "A competitor published a new product page"),
        (KIND_HIRING_PUSH, "A competitor started hiring for a function"),
    )

    STATUS_NEW = "new"
    STATUS_REVIEWED = "reviewed"
    STATUS_DISMISSED = "dismissed"
    STATUS_CHOICES = (
        (STATUS_NEW, "New"),
        (STATUS_REVIEWED, "Reviewed"),
        (STATUS_DISMISSED, "Dismissed"),
    )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="market_signals",
    )

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="market_signals",
        null=True,
        blank=True,
    )

    kind = models.CharField(max_length=40, choices=KIND_CHOICES)

    headline = models.CharField(max_length=300)

    # Factual statement, e.g. "3 monitored competitors increased a published
    # price during the last 30 days."
    statement = models.TextField(blank=True, default="")

    # Explicitly a possibility, never advice.
    interpretation = models.TextField(blank=True, default="")

    window_days = models.PositiveSmallIntegerField(default=30)

    # [{competitor, signal_event, source_url, detected_at}] — the evidence
    # the signal is built from. Always non-empty.
    evidence = models.JSONField(default=list, blank=True)

    confidence = models.CharField(
        max_length=10,
        choices=UrlAnalysis.CONFIDENCE_CHOICES,
        default=UrlAnalysis.CONFIDENCE_MEDIUM,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_NEW,
    )

    # Idempotency: the same evidence set does not produce the same signal
    # twice.
    fingerprint = models.CharField(max_length=64, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "status"]),
            models.Index(fields=["workspace", "-created_at"]),
        ]

    def __str__(self):
        return self.headline


class ChangeExplanation(models.Model):
    """A stored explanation for one feed row.

    Phase 1 already produced a deterministic explanation for every change.
    That text is stored here with ``is_fallback=True`` and is **never**
    replaced: an AI narration, when enabled and when every citation
    resolves, is stored as a *second* row for the same event. The
    deterministic text therefore always survives.
    """

    CONFIDENCE_CHOICES = UrlAnalysis.CONFIDENCE_CHOICES

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    signal_event = models.ForeignKey(
        SignalEvent,
        on_delete=models.CASCADE,
        related_name="explanations",
    )

    what_changed = models.TextField(blank=True, default="")
    why_it_may_matter = models.TextField(blank=True, default="")
    what_to_check = models.TextField(blank=True, default="")

    confidence = models.CharField(
        max_length=10,
        choices=CONFIDENCE_CHOICES,
        default=UrlAnalysis.CONFIDENCE_MEDIUM,
    )

    # The rule names behind this text, e.g. ["rule:price"].
    basis = models.JSONField(default=list, blank=True)

    # [{field, before, after, source_url, detected_at, rule, ...}]
    evidence = models.JSONField(default=list, blank=True)

    # "rules" for the deterministic text, or "ai:<provider>" when a provider
    # produced it. Recorded so the UI can label the source of the text.
    model = models.CharField(max_length=60, blank=True, default="rules")

    is_fallback = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["signal_event", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.signal_event_id}: {self.what_changed[:60]}"


class Report(models.Model):
    """A dated, shareable competitive intelligence report.

    The composed payload is stored on the row so a download always
    reproduces exactly what was shared, even after the underlying signals
    age out of retention.
    """

    KIND_INTELLIGENCE = "intelligence"
    KIND_BATTLECARD = "battlecard"
    KIND_CHOICES = (
        (KIND_INTELLIGENCE, "Competitive intelligence"),
        (KIND_BATTLECARD, "Battlecard"),
    )

    STATUS_PENDING = "pending"
    STATUS_READY = "ready"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Generating"),
        (STATUS_READY, "Ready"),
        (STATUS_FAILED, "Failed"),
    )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="intelligence_reports",
    )

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="intelligence_reports",
        null=True,
        blank=True,
    )

    organization = models.ForeignKey(
        "intelligence.Organization",
        on_delete=models.CASCADE,
        related_name="reports",
        null=True,
        blank=True,
    )

    title = models.CharField(max_length=200)

    slug = models.CharField(max_length=80)

    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_INTELLIGENCE)

    period_start = models.DateTimeField()

    period_end = models.DateTimeField()

    competitor_ids = models.JSONField(default=list, blank=True)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )

    formats = models.JSONField(default=list, blank=True)

    # The composed report: executive summary, competitors, sections,
    # timeline, sources, and the flattened rows.
    payload = models.JSONField(default=dict, blank=True)

    meta = models.JSONField(default=dict, blank=True)

    branding = models.JSONField(default=dict, blank=True)

    error = models.TextField(blank=True, default="")

    generated_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["workspace", "-created_at"]),
            models.Index(fields=["organization", "-created_at"]),
        ]

    def __str__(self):
        return self.title


class Battlecard(models.Model):
    """A living competitor profile.

    `fingerprint` covers the rows it was built from. When those rows
    change, the card is regenerated; until then the API reports that newer
    evidence exists. A battlecard that looks current but is not would be
    worse than no battlecard, so staleness is always surfaced.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    competitor = models.OneToOneField(
        Competitor,
        on_delete=models.CASCADE,
        related_name="battlecard",
    )

    sections = models.JSONField(default=dict, blank=True)

    positioning = models.TextField(blank=True, default="")

    sources = models.JSONField(default=list, blank=True)

    source_event_ids = models.JSONField(default=list, blank=True)

    fingerprint = models.CharField(max_length=64, blank=True, default="")

    generated_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-generated_at"]
        indexes = [
            models.Index(fields=["-generated_at"]),
        ]

    def __str__(self):
        return f"Battlecard: {self.competitor.name}"


# ==========================================================================
# Phase 5 — Agency mode
#
# An Organization is the new authorisation root. It is deliberately
# ADDITIVE: a personal account has no organization, keeps its personal
# Subscription, and behaves exactly as it does today. Joining an agency
# changes what the user can see; it never silently rewrites a plan.
# ==========================================================================


class Organization(models.Model):
    """An agency. Owns client workspaces, seats and branding."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_organizations",
    )

    name = models.CharField(max_length=200)

    slug = models.SlugField(max_length=80, unique=True)

    # White-label: agency name, tagline, primary colour, footer, and whether
    # the Sitemyra credit line is shown. Plain text only — never rendered as
    # HTML, and never a URL the server fetches.
    branding = models.JSONField(default=dict, blank=True)

    plan = models.CharField(
        max_length=20,
        choices=[(choice, label) for choice, label in __import__(
            "billing.models", fromlist=["PLAN_CHOICES"]
        ).PLAN_CHOICES],
        default="pro",
    )

    mrr_cents = models.PositiveIntegerField(default=0)

    stripe_customer_id = models.CharField(max_length=255, blank=True, default="")

    stripe_subscription_id = models.CharField(max_length=255, blank=True, default="")

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["owner"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return self.name


class OrganizationMembership(models.Model):
    """A seat on an agency account.

    `analyst` can build watchlists and reports but not manage seats or
    billing; `viewer` is read-only. This is the same rank discipline as
    the existing workspace roles.
    """

    OWNER = "owner"
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"
    ROLE_CHOICES = (
        (OWNER, "Owner"),
        (ADMIN, "Admin"),
        (ANALYST, "Analyst"),
        (VIEWER, "Viewer"),
    )
    ROLE_RANK = {VIEWER: 1, ANALYST: 2, ADMIN: 3, OWNER: 4}

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=VIEWER)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["organization", "-created_at"]
        indexes = [
            models.Index(fields=["organization", "role"]),
            models.Index(fields=["user"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"],
                name="unique_organization_member",
            )
        ]

    def __str__(self):
        return f"{self.user_id} @ {self.organization_id} ({self.role})"


class BrowserSession(models.Model):
    """A short-lived, scoped, revocable token for the browser extension.

    Phase 6 security invariants:

    * the raw token is shown **once** and stored only as a SHA-256 hash,
      exactly like the existing developer API keys;
    * it carries `monitors:read` + `monitors:write` and **nothing else** —
      no billing, no alert channels, no reports, no workspace membership;
    * it expires, and it can be revoked server-side, which takes effect on
      the next request;
    * it never appears in a URL, a log line, or a report.
    """

    SCOPES = "monitors:read monitors:write"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="browser_sessions",
    )

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="browser_sessions",
        null=True,
        blank=True,
    )

    label = models.CharField(max_length=120, default="Browser extension")

    token_hash = models.CharField(max_length=64, db_index=True)

    prefix = models.CharField(max_length=20)

    scopes = models.CharField(max_length=120, default=SCOPES)

    created_at = models.DateTimeField(auto_now_add=True)

    expires_at = models.DateTimeField()

    last_used_at = models.DateTimeField(null=True, blank=True)

    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"{self.label} ({self.prefix})"

    @property
    def is_active(self) -> bool:
        from django.utils import timezone

        return self.revoked_at is None and self.expires_at > timezone.now()

    @staticmethod
    def hash_secret(raw: str) -> str:
        return hashlib.sha256(raw.encode()).hexdigest()

    @classmethod
    def generate(cls, user, label="", workspace=None, ttl_days=30):
        raw = f"sitemyra_ext_{secrets.token_urlsafe(32)}"
        return (
            cls.objects.create(
                user=user,
                workspace=workspace,
                label=(label or "Browser extension")[:120],
                token_hash=cls.hash_secret(raw),
                prefix=raw[:20],
                scopes=cls.SCOPES,
                expires_at=timezone.now() + timedelta(days=max(1, min(int(ttl_days), 90))),
            ),
            raw,
        )
