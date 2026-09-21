from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class ApiKeyAuthentication(BaseAuthentication):
    """Authenticate `Authorization: Bearer apeiro_...` developer tokens.

    Falls through (returns None) for non-apeiro tokens so JWT still works.
    Workspace role is enforced at the view layer; Viewers get read-only.
    """

    keyword = "Bearer"

    def authenticate_header(self, request):
        return 'Bearer realm="api"'

    def authenticate(self, request):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header.startswith("Bearer "):
            return None
        raw = header[len("Bearer "):].strip()
        if not raw.startswith("apeiro_"):
            return None
        from .models import ApiKey

        key_hash = ApiKey.hash_secret(raw)
        try:
            api_key = ApiKey.objects.select_related("user", "workspace").get(
                key_hash=key_hash, revoked=False
            )
        except ApiKey.DoesNotExist:
            raise AuthenticationFailed("Invalid API key.")
        if not api_key.user.is_active:
            raise AuthenticationFailed("Account inactive.")
        api_key.last_used_at = timezone.now()
        api_key.save(update_fields=["last_used_at"])
        # Attach the key so views can apply workspace RBAC.
        request.api_key = api_key
        return (api_key.user, None)
