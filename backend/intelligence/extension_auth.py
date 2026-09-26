"""Authentication for the browser extension (Phase 6).

A deliberately narrow replacement for the developer API-key path, added
as a *separate* class rather than a mode of ``ApiKeyAuthentication`` so the
two credential types can never be confused with one another:

* distinct token prefix (``sitemyra_ext_``), so a leaked extension token
  is obvious in a log and can never be mistaken for a developer key;
* a dedicated table, so revoking one does not touch developer keys;
* a hard scope ceiling of ``monitors:read monitors:write`` — it can never
  reach billing, alert channels, exports, reports, workspaces or
  organization membership, no matter what the caller asks for;
* the same SSRF, plan-limit and tenant rules as every other path, because
  the extension calls the *same* endpoints rather than privileged ones.

The raw token is never stored, never logged, and never returned twice.
"""

import logging

from django.utils import timezone
from rest_framework import authentication, exceptions

logger = logging.getLogger(__name__)

EXTENSION_KEYWORD = "sitemyra_ext_"

# Deny-by-default allowlist, keyed by URL name.
#
# An extension token authenticates as the user, so without this a token
# minted in a browser could call billing, exports, reports, alert channels
# and organization endpoints — the "read and create monitors, nothing else"
# promise would be false.
#
# Resolution happens before view dispatch, so `request.resolver_match` is
# available during authentication and the decision is made in exactly one
# place. Anything NOT listed here is refused, so a new endpoint is denied
# until it is deliberately opened. That is the safe default for a
# credential that lives in a browser.
EXTENSION_ALLOWED_VIEWS = frozenset(
    {
        # Phase 1 — monitoring only.
        "intelligence-quick-monitor",
        "intelligence-analyze",
        "intelligence-activate",
        "intelligence-recipes",
        "intelligence-public-analyze",
        "intelligence-product-watch-list",
        "intelligence-product-watch-detail",
        "intelligence-product-watch-timeline",
        "intelligence-monitor-product",
        "monitors-list",
        "monitor-detail",
        "monitor-pause",
        "monitor-resume",
        "monitor-test",
        "monitor-checks",
        "monitor-changes",
        # Phase 2 — reading the intelligence the extension created.
        "intelligence-feed",
        "intelligence-pulse",
        "intelligence-overview",
        "intelligence-competitor-list",
        "intelligence-competitor-detail",
        "intelligence-competitor-activity",
        "intelligence-event-detail",
    }
)

EXTENSION_SCOPE_ERROR = (
    "This credential can only create and read monitors. Sign in with your "
    "account token to use this endpoint."
)


class ExtensionTokenAuthentication(authentication.BaseAuthentication):
    """Authenticate ``Authorization: Bearer sitemyra_ext_…``.

    Returns ``None`` for any other credential so the normal JWT and
    developer-key paths continue to apply, and exposes
    ``authenticate_header`` so a missing token yields 401 rather than 403.
    """

    keyword = "Bearer"

    def authenticate_header(self, request):
        return 'Bearer realm="api"'

    def authenticate(self, request):
        from intelligence.models import BrowserSession

        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header.startswith(f"{self.keyword} "):
            return None
        raw = header[len(self.keyword) + 1:].strip()
        if not raw.startswith(EXTENSION_KEYWORD):
            return None

        session = (
            BrowserSession.objects.select_related("user", "workspace")
            .filter(token_hash=BrowserSession.hash_secret(raw), revoked_at__isnull=True)
            .first()
        )
        if session is None:
            raise exceptions.AuthenticationFailed("Invalid extension token.")
        if session.expires_at <= timezone.now():
            raise exceptions.AuthenticationFailed("This extension session has expired.")
        if not session.user.is_active:
            raise exceptions.AuthenticationFailed("Account inactive.")

        if not self.view_allows_extension(request):
            logger.warning(
                "intelligence extension token refused for a denied view "
                "[session_id=%s path=%s]",
                session.id, request.path,
            )
            raise exceptions.AuthenticationFailed(EXTENSION_SCOPE_ERROR)

        session.last_used_at = timezone.now()
        session.save(update_fields=["last_used_at"])
        request.extension_session = session
        return (session.user, None)

    @staticmethod
    def view_allows_extension(request) -> bool:
        """True when the resolved view is on the allowlist.

        Deny-by-default: an unresolvable match is a refusal.
        """
        match = getattr(request, "resolver_match", None)
        name = getattr(match, "url_name", None)
        if not name:
            return False
        return name in EXTENSION_ALLOWED_VIEWS

    @staticmethod
    def scope_allows(session, scope: str) -> bool:
        """Scope check for a view that wants to be extra careful.

        Views that accept an extension token should call this; the default
        for the intelligence endpoints is that the session scope already
        limits them to monitor read/write.
        """
        return scope in (session.scopes or "").split()
