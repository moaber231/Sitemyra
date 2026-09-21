from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import WorkspaceViewSet, accept_invite

router = DefaultRouter()
router.register("", WorkspaceViewSet, basename="workspace")

urlpatterns = [
    path("invites/<str:token>/accept/", accept_invite, name="workspace-accept-invite"),
    path("", include(router.urls)),
]
