from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from workspaces.models import Workspace
from workspaces.permissions import require_role

from .models import ApiKey, OnboardingProgress
from .oauth import (
    PROVIDERS,
    OAuthError,
    build_authorization_url,
    exchange_code,
    expected_redirect_uri,
    is_provider_configured,
    link_or_create_user,
    verify_state,
)
from .serializers import (
    ApiKeySerializer,
    LoginSerializer,
    OAuthLoginSerializer,
    OnboardingSerializer,
    RegisterSerializer,
    UserSerializer,
)


class RegisterView(generics.CreateAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()
        # Every user starts on Free with an onboarding record.
        from billing.models import get_or_create_subscription

        get_or_create_subscription(user)
        OnboardingProgress.objects.get_or_create(user=user)
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "user": UserSerializer(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=201,
        )


class LoginView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


refresh_view = TokenRefreshView.as_view()


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def oauth_status(request):
    """Public provider availability (no secrets). Drives the login UI."""
    return Response(
        {
            "providers": {
                provider: {
                    "enabled": is_provider_configured(provider),
                    "redirect_uri": (
                        expected_redirect_uri(provider)
                        if is_provider_configured(provider)
                        else None
                    ),
                }
                for provider in PROVIDERS
            }
        }
    )


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def oauth_start(request, provider):
    """Begin login: mint state and return the provider authorization URL."""
    if provider not in PROVIDERS:
        return Response(
            {"detail": "Unknown OAuth provider.", "code": "unknown_provider"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        authorization_url, state = build_authorization_url(provider)
    except OAuthError as exc:
        return Response(
            {"detail": exc.detail, "code": exc.code},
            status=exc.http_status,
        )
    return Response(
        {
            "authorization_url": authorization_url,
            "provider": provider,
            "state": state,
        }
    )


def _complete_oauth_flow(provider, code, state):
    """Shared callback logic: state -> exchange -> verify -> link -> JWT."""
    verify_state(provider, state)
    email, verified, provider_user_id = exchange_code(provider, code)
    if not verified:
        raise OAuthError(
            "email_unverified",
            "Your provider email address is not verified. Verify it "
            "with the provider, then try again.",
            403,
        )
    user, created = link_or_create_user(provider, email, provider_user_id)
    refresh = RefreshToken.for_user(user)
    return {
        "user": UserSerializer(user).data,
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "provider": provider,
        "created": created,
    }


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def oauth_callback(request, provider):
    """Provider redirect target (via the frontend callback page).

    Validates ``state``, exchanges ``code`` server-side, verifies the
    provider email, links/creates the account, and mints app JWTs.
    """
    if provider not in PROVIDERS:
        return Response(
            {"detail": "Unknown OAuth provider.", "code": "unknown_provider"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if request.query_params.get("error"):
        # User denied authorization (or provider error): never authenticated.
        return Response(
            {
                "detail": "Authorization was not granted.",
                "code": "access_denied",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    code = (request.query_params.get("code") or "").strip()
    state = (request.query_params.get("state") or "").strip()
    if not code:
        return Response(
            {
                "detail": "Missing authorization code.",
                "code": "invalid_callback",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        return Response(_complete_oauth_flow(provider, code, state))
    except OAuthError as exc:
        return Response(
            {"detail": exc.detail, "code": exc.code},
            status=exc.http_status,
        )


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def oauth_login(request):
    """SSO entry point for Google/GitHub OAuth alongside JWT.

    Authorization-code flow only: a provider-issued ``code`` is exchanged
    server-side, the provider identity is verified, and the account is
    linked/created per the documented rules. Raw ``email`` values are
    never accepted as proof of identity.
    """
    serializer = OAuthLoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    provider = serializer.validated_data["provider"]
    code = (serializer.validated_data.get("code") or "").strip()
    if provider not in PROVIDERS:
        return Response(
            {"detail": "Unknown OAuth provider.", "code": "unknown_provider"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not code:
        return Response(
            {
                "detail": (
                    "Single sign-on requires a provider authorization "
                    "code. Start at GET /api/auth/oauth/<provider>/start/."
                ),
                "code": "code_required",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    # NOTE: the POST flow has no browser state round-trip, so it cannot
    # validate CSRF state; prefer the GET start/callback flow for browser
    # logins. The code exchange + verified-email linking below still apply.
    try:
        email, verified, provider_user_id = exchange_code(provider, code)
        if not verified:
            raise OAuthError(
                "email_unverified",
                "Your provider email address is not verified. Verify it "
                "with the provider, then try again.",
                403,
            )
        user, created = link_or_create_user(provider, email, provider_user_id)
    except OAuthError as exc:
        return Response(
            {"detail": exc.detail, "code": exc.code},
            status=exc.http_status,
        )

    refresh = RefreshToken.for_user(user)
    return Response(
        {
            "user": UserSerializer(user).data,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "provider": provider,
            "created": created,
        }
    )


class ApiKeyListCreateView(generics.ListCreateAPIView):
    serializer_class = ApiKeySerializer

    def get_queryset(self):
        return ApiKey.objects.filter(
            user=self.request.user, revoked=False
        ).select_related("workspace")

    def create(self, request, *args, **kwargs):
        name = (request.data.get("name") or "default").strip()[:120]
        workspace_id = request.data.get("workspace")
        scopes = request.data.get("scopes") or ""
        workspace = None
        if workspace_id:
            workspace = get_object_or_404(Workspace, pk=workspace_id)
            # RBAC: only Owner/Admin may generate workspace-scoped keys.
            # Viewers get 403. Personal keys (no workspace) are always OK.
            if not require_role(request.user, workspace, minimum="admin"):
                return Response(
                    {
                        "detail": (
                            "Only workspace Owner/Admin can generate "
                            "workspace API keys."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        obj, raw = ApiKey.generate(request.user, name, workspace, scopes)
        data = ApiKeySerializer(obj).data
        data["key"] = raw  # shown exactly once
        return Response(data, status=status.HTTP_201_CREATED)


class ApiKeyRevokeView(generics.DestroyAPIView):
    serializer_class = ApiKeySerializer

    def get_queryset(self):
        return ApiKey.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        instance.revoked = True
        instance.save(update_fields=["revoked"])


@api_view(["GET", "PATCH"])
@permission_classes([permissions.IsAuthenticated])
def onboarding(request):
    progress, _ = OnboardingProgress.objects.get_or_create(user=request.user)
    if request.method == "GET":
        return Response(OnboardingSerializer(progress).data)
    serializer = OnboardingSerializer(progress, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)
