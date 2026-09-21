from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .advanced_api import (
    advanced_config,
    artifact_download,
    monitor_diffs,
    monitor_prices,
    test_advanced_monitor,
)
from .views import MonitorViewSet, compliance_export

router = DefaultRouter()
router.register("", MonitorViewSet, basename="monitor")

advanced_urlpatterns = [
    path(
        "advanced/",
        advanced_config,
        name="advanced-config",
    ),
    path(
        "advanced/test/",
        test_advanced_monitor,
        name="advanced-test",
    ),
    path(
        "diffs/",
        monitor_diffs,
        name="monitor-diffs",
    ),
    path(
        "prices/",
        monitor_prices,
        name="monitor-prices",
    ),
]

urlpatterns = [
    path(
        "export/compliance/",
        compliance_export,
        name="monitor-compliance-export",
    ),
    path(
        "artifacts/<uuid:diff_id>/download/",
        artifact_download,
        name="artifact-download",
    ),
    path(
        "<uuid:monitor_id>/",
        include((advanced_urlpatterns, "advanced")),
    ),
]

urlpatterns += router.urls
