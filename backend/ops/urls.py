from django.urls import path

from .views import diagnostics, metrics

urlpatterns = [
    path("metrics/", metrics, name="ops-metrics"),
    path("diagnostics/", diagnostics, name="ops-diagnostics"),
]
