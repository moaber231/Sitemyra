from django.urls import path

from . import (
    views,
    views_phase2,
    views_phase3,
    views_phase4,
    views_phase5,
    views_phase6,
)

urlpatterns = [
    # ------------------------------------------------------------------
    # Phase 1 — URL intake
    # ------------------------------------------------------------------
    path("analyze/", views.analyze, name="intelligence-analyze"),
    path(
        "public/analyze/",
        views.public_analyze,
        name="intelligence-public-analyze",
    ),
    path("activate/", views.activate, name="intelligence-activate"),
    path(
        "quick-monitor/",
        views.quick_monitor,
        name="intelligence-quick-monitor",
    ),
    path("recipes/", views.recipes, name="intelligence-recipes"),
    path(
        "product-watches/",
        views.ProductWatchListView.as_view(),
        name="intelligence-product-watch-list",
    ),
    path(
        "product-watches/<uuid:watch_id>/",
        views.ProductWatchDetailView.as_view(),
        name="intelligence-product-watch-detail",
    ),
    path(
        "product-watches/<uuid:watch_id>/timeline/",
        views.ProductWatchTimelineView.as_view(),
        name="intelligence-product-watch-timeline",
    ),
    path(
        "monitors/<uuid:monitor_id>/product/",
        views.MonitorProductView.as_view(),
        name="intelligence-monitor-product",
    ),
    # ------------------------------------------------------------------
    # Phase 2 — feed, pulse, competitors, discovery
    # ------------------------------------------------------------------
    path("feed/", views_phase2.feed, name="intelligence-feed"),
    path("pulse/", views_phase2.pulse, name="intelligence-pulse"),
    path("overview/", views_phase2.overview, name="intelligence-overview"),
    path(
        "competitors/",
        views_phase2.CompetitorListView.as_view(),
        name="intelligence-competitor-list",
    ),
    path(
        "competitors/discover/",
        views_phase2.discover,
        name="intelligence-competitor-discover",
    ),
    path(
        "competitors/approve/",
        views_phase2.approve_candidate,
        name="intelligence-competitor-approve",
    ),
    path(
        "competitors/<uuid:competitor_id>/",
        views_phase2.CompetitorDetailView.as_view(),
        name="intelligence-competitor-detail",
    ),
    path(
        "competitors/<uuid:competitor_id>/activity/",
        views_phase2.CompetitorActivityView.as_view(),
        name="intelligence-competitor-activity",
    ),
    # ------------------------------------------------------------------
    # Phase 3 — the alert deep link and market signals
    # ------------------------------------------------------------------
    path(
        "events/<uuid:event_id>/",
        views_phase3.signal_event_detail,
        name="intelligence-event-detail",
    ),
    path("signals/", views_phase3.signals_list, name="intelligence-signals"),
    path(
        "narration-preference/",
        views_phase3.NarrationPreferenceView.as_view(),
        name="intelligence-narration-preference",
    ),
    path(
        "signals/<uuid:signal_id>/review/",
        views_phase3.review_signal,
        name="intelligence-signal-review",
    ),
    path(
        "competitors/<uuid:competitor_id>/battlecard/",
        views_phase4.competitor_battlecard,
        name="intelligence-battlecard",
    ),
    # ------------------------------------------------------------------
    # Phase 4 — exports and reports
    # ------------------------------------------------------------------
    path("export/", views_phase4.export_intelligence, name="intelligence-export"),
    path("reports/", views_phase4.reports, name="intelligence-reports"),
    path(
        "reports/<uuid:report_id>/",
        views_phase4.report_detail,
        name="intelligence-report-detail",
    ),
    path(
        "reports/<uuid:report_id>/download/",
        views_phase4.report_download,
        name="intelligence-report-download",
    ),
    # ------------------------------------------------------------------
    # Phase 5 — agency / organizations
    # ------------------------------------------------------------------
    path("organizations/", views_phase5.organizations, name="intelligence-organizations"),
    path(
        "organizations/<uuid:organization_id>/",
        views_phase5.organization_detail,
        name="intelligence-organization-detail",
    ),
    path(
        "organizations/<uuid:organization_id>/members/",
        views_phase5.organization_members,
        name="intelligence-organization-members",
    ),
    path(
        "organizations/<uuid:organization_id>/workspaces/",
        views_phase5.organization_workspaces,
        name="intelligence-organization-workspaces",
    ),
    path(
        "organizations/<uuid:organization_id>/branding/",
        views_phase5.organization_branding,
        name="intelligence-organization-branding",
    ),
    # ------------------------------------------------------------------
    # Phase 6 — browser extension sessions
    # ------------------------------------------------------------------
    path(
        "extension-sessions/",
        views_phase6.extension_sessions,
        name="intelligence-extension-sessions",
    ),
    path(
        "extension-sessions/<uuid:session_id>/",
        views_phase6.extension_session_detail,
        name="intelligence-extension-session-detail",
    ),
    # ------------------------------------------------------------------
    path("_internal/derive/", views_phase2.derive_now, name="intelligence-derive-now"),
]
