from django.urls import path

from .views import (
    ApiKeyListCreateView,
    ApiKeyRevokeView,
    LoginView,
    MeView,
    RegisterView,
    oauth_callback,
    oauth_login,
    oauth_start,
    oauth_status,
    onboarding,
    refresh_view,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("oauth/", oauth_login, name="oauth-login"),
    path("oauth/status/", oauth_status, name="oauth-status"),
    path("oauth/<str:provider>/start/", oauth_start, name="oauth-start"),
    path(
        "oauth/<str:provider>/callback/",
        oauth_callback,
        name="oauth-callback",
    ),
    path("refresh/", refresh_view, name="refresh"),
    path("me/", MeView.as_view(), name="me"),
    path("onboarding/", onboarding, name="onboarding"),
    path("api-keys/", ApiKeyListCreateView.as_view(), name="api-keys"),
    path(
        "api-keys/<uuid:pk>/",
        ApiKeyRevokeView.as_view(),
        name="api-key-revoke",
    ),
]
