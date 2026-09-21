from django.urls import path

from .views import (
    AlertChannelDetailView,
    AlertChannelListCreateView,
    AlertChannelTestView,
    NotificationPreferenceView,
)

urlpatterns = [
    path(
        "preferences/",
        NotificationPreferenceView.as_view(),
        name="notification-preferences",
    ),
    path("channels/", AlertChannelListCreateView.as_view(), name="alert-channels"),
    path(
        "channels/<uuid:pk>/test/",
        AlertChannelTestView.as_view(),
        name="alert-channel-test",
    ),
    path(
        "channels/<uuid:pk>/",
        AlertChannelDetailView.as_view(),
        name="alert-channel-detail",
    ),
]
