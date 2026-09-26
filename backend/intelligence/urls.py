from django.urls import path

from . import views

urlpatterns = [
    # URL intake
    path("analyze/", views.analyze, name="intelligence-analyze"),
    path(
        "public/analyze/",
        views.public_analyze,
        name="intelligence-public-analyze",
    ),
    # Activation
    path("activate/", views.activate, name="intelligence-activate"),
    path(
        "quick-monitor/",
        views.quick_monitor,
        name="intelligence-quick-monitor",
    ),
    # Recipes
    path("recipes/", views.recipes, name="intelligence-recipes"),
    # Product intelligence
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
]
