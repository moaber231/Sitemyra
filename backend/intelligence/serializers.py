"""DRF serializers for the intelligence layer.

All output is a projection of evidence: every value the UI shows is either
a stored fact, a stored before/after, or a rule-derived label that names
the rule. No field is synthesised here.
"""

from rest_framework import serializers

from .models import (
    DiscoveredTarget,
    ProductChange,
    ProductSnapshot,
    ProductWatch,
    UrlAnalysis,
)
from .models import Competitor as _Competitor, CompetitorCandidate as _CompetitorCandidate
from .services import product_diff


class DiscoveredTargetSerializer(serializers.ModelSerializer):
    kind_label = serializers.SerializerMethodField()

    class Meta:
        model = DiscoveredTarget
        fields = (
            "id",
            "url",
            "kind",
            "kind_label",
            "label",
            "why",
            "confidence",
            "relevance",
            "is_product",
            "is_primary",
        )
        read_only_fields = fields

    def get_kind_label(self, obj) -> str:
        from .services.classify import KIND_LABELS

        return KIND_LABELS.get(obj.kind, "Page")


class UrlAnalysisSerializer(serializers.ModelSerializer):
    """The intake result: what Sitemyra found, and why."""

    targets = DiscoveredTargetSerializer(many=True, read_only=True)
    target_count = serializers.SerializerMethodField()
    page_kind_label = serializers.SerializerMethodField()
    found_count = serializers.SerializerMethodField()
    recipe_slug = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = UrlAnalysis
        fields = (
            "id",
            "url",
            "status",
            "page_kind",
            "page_kind_label",
            "classification_confidence",
            "classification_rationale",
            "product_detected",
            "facts",
            "summary",
            "status_code",
            "response_time_ms",
            "fetched_at",
            "expires_at",
            "targets",
            "target_count",
            "found_count",
            "recipe_slug",
        )
        read_only_fields = (
            "id",
            "url",
            "status",
            "page_kind",
            "page_kind_label",
            "classification_confidence",
            "classification_rationale",
            "product_detected",
            "facts",
            "summary",
            "status_code",
            "response_time_ms",
            "fetched_at",
            "expires_at",
            "targets",
            "target_count",
            "found_count",
        )

    def get_target_count(self, obj) -> int:
        cached = getattr(obj, "target_count_cache", None)
        if cached is not None:
            return cached
        return obj.targets.count()

    def get_found_count(self, obj) -> int:
        return self.get_target_count(obj)

    def get_page_kind_label(self, obj) -> str:
        from .services.classify import KIND_LABELS

        return KIND_LABELS.get(obj.page_kind, "Page")


class ProductSnapshotSerializer(serializers.ModelSerializer):
    discount_percent = serializers.SerializerMethodField()
    availability_label = serializers.SerializerMethodField()
    evidence_source_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductSnapshot
        fields = (
            "id",
            "product_watch",
            "monitor_check",
            "captured_at",
            "name",
            "brand",
            "sku",
            "price",
            "list_price",
            "discount_percent",
            "currency",
            "availability",
            "availability_label",
            "condition",
            "rating",
            "review_count",
            "description",
            "badges",
            "variants",
            "images",
            "bundles",
            "specs",
            "shipping",
            "price_valid_until",
            "source_url",
            "evidence_source_url",
            "extraction",
            "evidence",
            "changed_fields",
        )
        read_only_fields = fields

    def get_discount_percent(self, obj):
        percent = product_diff.discount_percent(obj.list_price, obj.price)
        if percent is None:
            return None
        return float(round(percent, 1))

    def get_availability_label(self, obj) -> str:
        return (obj.availability or "").replace("_", " ") or "not published"

    def get_evidence_source_url(self, obj) -> str:
        return obj.source_url or ""


class ProductChangeSerializer(serializers.ModelSerializer):
    severity_label = serializers.SerializerMethodField()
    category_label = serializers.SerializerMethodField()
    summary_line = serializers.SerializerMethodField()

    class Meta:
        model = ProductChange
        fields = (
            "id",
            "product_watch",
            "previous_snapshot",
            "current_snapshot",
            "monitor_check",
            "field",
            "label",
            "before",
            "after",
            "severity",
            "severity_label",
            "category",
            "category_label",
            "basis",
            "rule",
            "evidence",
            "source_url",
            "created_at",
            "summary_line",
        )
        read_only_fields = fields

    def get_severity_label(self, obj) -> str:
        return product_diff.SEVERITY_LABELS.get(obj.severity, "Informational")

    def get_category_label(self, obj) -> str:
        return dict(ProductChange.CATEGORY_CHOICES).get(obj.category, "Content")

    def get_summary_line(self, obj) -> str:
        return product_diff.format_change_line(
            {
                "field": obj.field,
                "label": obj.label,
                "before": obj.before,
                "after": obj.after,
            },
            currency="",
        )


class ProductWatchSerializer(serializers.ModelSerializer):
    monitor_name = serializers.CharField(source="monitor.name", read_only=True)
    monitor_url = serializers.CharField(source="monitor.url", read_only=True)
    latest_snapshot = serializers.SerializerMethodField()
    change_count = serializers.SerializerMethodField()
    latest_severity = serializers.SerializerMethodField()

    class Meta:
        model = ProductWatch
        fields = (
            "id",
            "monitor",
            "monitor_name",
            "monitor_url",
            "name",
            "brand",
            "currency",
            "product_detected",
            "detection_note",
            "first_seen_at",
            "last_seen_at",
            "created_at",
            "latest_snapshot",
            "change_count",
            "latest_severity",
        )
        read_only_fields = fields

    def get_latest_snapshot(self, obj):
        snapshot = obj.latest_snapshot
        if snapshot is None:
            return None
        return ProductSnapshotSerializer(snapshot).data

    def get_change_count(self, obj) -> int:
        cached = getattr(obj, "change_count_cache", None)
        if cached is not None:
            return cached
        return obj.changes.count()

    def get_latest_severity(self, obj) -> str:
        row = obj.changes.order_by("-created_at").first()
        return row.severity if row else ""


class ActivationRequestSerializer(serializers.Serializer):
    """Input for POST /api/intelligence/activate/ and /quick-monitor/."""

    analysis_id = serializers.UUIDField(required=False, allow_null=True)
    url = serializers.CharField(required=False, allow_blank=True)
    target_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True
    )
    recipe = serializers.CharField(required=False, allow_blank=True)
    workspace = serializers.UUIDField(required=False, allow_null=True)
    check_interval = serializers.IntegerField(required=False, allow_null=True, min_value=30, max_value=86400)

    def validate(self, attrs):
        if not attrs.get("analysis_id") and not (attrs.get("url") or "").strip():
            raise serializers.ValidationError(
                "Provide either an analysis_id or a url."
            )
        return attrs


class AnalyzeRequestSerializer(serializers.Serializer):
    url = serializers.CharField()
    timeout = serializers.IntegerField(required=False, min_value=1, max_value=30)

    def validate_url(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Enter a URL to analyse.")
        return value.strip()


# ==========================================================================
# Phase 2 — feed, competitors, discovery
# ==========================================================================


class FeedEventSerializer(serializers.Serializer):
    """Read-only projection of one feed row. Not a ModelSerializer on
    purpose: the feed exposes competitor/monitor names and the kind icon,
    which are presentation concerns, not model fields."""

    id = serializers.CharField(read_only=True)
    kind = serializers.CharField(read_only=True)
    icon = serializers.CharField(read_only=True)
    headline = serializers.CharField(read_only=True)
    summary = serializers.CharField(read_only=True)
    before = serializers.CharField(read_only=True)
    after = serializers.CharField(read_only=True)
    severity = serializers.CharField(read_only=True)
    source_url = serializers.CharField(read_only=True)
    detected_at = serializers.DateTimeField(read_only=True)
    competitor_id = serializers.CharField(read_only=True, allow_null=True)
    competitor_name = serializers.CharField(read_only=True, allow_null=True)
    monitor_id = serializers.CharField(read_only=True, allow_null=True)
    monitor_name = serializers.CharField(read_only=True, allow_null=True)
    product_change_id = serializers.CharField(read_only=True, allow_null=True)
    monitor_check_id = serializers.CharField(read_only=True, allow_null=True)
    evidence = serializers.DictField(read_only=True)
    has_evidence = serializers.BooleanField(read_only=True)


class CompetitorCandidateSerializer(serializers.ModelSerializer):
    reason_list = serializers.SerializerMethodField()

    class Meta:
        model = _CompetitorCandidate
        fields = (
            "id",
            "url",
            "domain",
            "relationship",
            "reasons",
            "reason_list",
            "confidence",
            "approved",
            "approved_at",
        )
        read_only_fields = (
            "id",
            "reasons",
            "reason_list",
            "confidence",
            "approved",
            "approved_at",
        )

    def get_reason_list(self, obj) -> list:
        return list(obj.reasons or [])


class CompetitorSerializer(serializers.ModelSerializer):
    pulse = serializers.SerializerMethodField()
    monitor_urls = serializers.SerializerMethodField()

    class Meta:
        model = "intelligence.Competitor"
        fields = (
            "id",
            "name",
            "homepage_url",
            "domain",
            "relationship",
            "relationship_reasons",
            "signals",
            "first_seen_at",
            "last_activity_at",
            "created_at",
            "pulse",
            "monitor_urls",
        )
        read_only_fields = fields

    def get_pulse(self, obj) -> dict:
        from .services import feed as feed_service

        return feed_service.pulse_for_competitor(obj)

    def get_monitor_urls(self, obj) -> list:
        return list(obj.monitor_set.values_list("url", flat=True)[:50]) if hasattr(obj, "monitor_set") else []


class ApproveCandidateSerializer(serializers.Serializer):
    candidate_id = serializers.UUIDField()
    recipe = serializers.CharField(required=False, allow_blank=True)
    workspace = serializers.UUIDField(required=False, allow_null=True)
    check_interval = serializers.IntegerField(
        required=False, allow_null=True, min_value=30, max_value=86400
    )


class DiscoverRequestSerializer(serializers.Serializer):
    url = serializers.CharField()
    workspace = serializers.UUIDField(required=False, allow_null=True)

    def validate_url(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Enter your own site or product URL.")
        return value.strip()
