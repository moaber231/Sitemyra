"""Production OAuth (Google/GitHub) — authorization-code flow.

Secrets never leave the server: the frontend only ever sees the provider
authorization URL (built here) and the short-lived ``code``/``state``
returned by the provider to the callback page.

State (CSRF) protection is stateless: a signed, timestamped, unguessable
nonce bound to the provider via the signer salt. No DB table required.
"""

import json
import logging
import os
import secrets
from urllib.parse import urlencode

import httpx
from django.conf import settings
from django.core import signing

logger = logging.getLogger(__name__)

GOOGLE = "google"
GITHUB = "github"
PROVIDERS = (GOOGLE, GITHUB)

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


class OAuthError(Exception):
    """Safe, user-facing OAuth failure (no tokens/secrets attached)."""

    def __init__(self, code: str, detail: str, http_status: int = 400):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.http_status = http_status


def _state_ttl_seconds() -> int:
    try:
        return max(60, int(os.getenv("OAUTH_STATE_TTL_SECONDS", "600")))
    except ValueError:
        return 600


def _signer(provider: str) -> signing.TimestampSigner:
    return signing.TimestampSigner(salt=f"apeiro-oauth-{provider}")


def is_provider_configured(provider: str) -> bool:
    """True only when the server can run a real code exchange."""
    if provider == GOOGLE:
        return bool(
            os.getenv("GOOGLE_CLIENT_ID", "").strip()
            and os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
        )
    if provider == GITHUB:
        return bool(
            os.getenv("GITHUB_CLIENT_ID", "").strip()
            and os.getenv("GITHUB_CLIENT_SECRET", "").strip()
        )
    return False


def expected_redirect_uri(provider: str) -> str:
    """Canonical redirect URI registered at the provider."""
    if provider == GOOGLE:
        explicit = os.getenv("GOOGLE_REDIRECT_URI", "").strip()
    elif provider == GITHUB:
        explicit = os.getenv("GITHUB_REDIRECT_URI", "").strip()
    else:
        explicit = ""
    if explicit:
        return explicit.rstrip("/")
    frontend = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    return f"{str(frontend).rstrip('/')}/auth/callback"


def _redirect_is_safe_for_prod(redirect_uri: str) -> bool:
    if settings.DEBUG:
        return True
    return redirect_uri.startswith("https://")


def mint_state(provider: str) -> str:
    payload = json.dumps({"nonce": secrets.token_urlsafe(24)})
    return _signer(provider).sign(payload)


def verify_state(provider: str, state: str) -> None:
    if not state:
        raise OAuthError("invalid_state", "Missing OAuth state.", 400)
    try:
        raw = _signer(provider).unsign(state, max_age=_state_ttl_seconds())
        payload = json.loads(raw)
        if not payload.get("nonce"):
            raise ValueError("empty nonce")
    except signing.SignatureExpired:
        raise OAuthError("invalid_state", "OAuth state expired.", 400)
    except (signing.BadSignature, ValueError, TypeError):
        raise OAuthError("invalid_state", "Invalid OAuth state.", 400)


def build_authorization_url(provider: str) -> tuple[str, str]:
    """Return (authorization_url, state). Raises OAuthError when disabled."""
    if provider not in PROVIDERS:
        raise OAuthError("unknown_provider", "Unknown OAuth provider.", 400)
    if not is_provider_configured(provider):
        raise OAuthError(
            "oauth_unavailable",
            "Single sign-on is not configured. "
            "Please sign in with email and password.",
            503,
        )
    redirect_uri = expected_redirect_uri(provider)
    if not _redirect_is_safe_for_prod(redirect_uri):
        logger.warning("OAuth start refused: insecure redirect for %s", provider)
        raise OAuthError(
            "oauth_misconfigured",
            "Single sign-on is misconfigured. Contact support.",
            503,
        )
    state = mint_state(provider)
    if provider == GOOGLE:
        params = {
            "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
        return f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}", state
    params = {
        "client_id": os.getenv("GITHUB_CLIENT_ID", ""),
        "redirect_uri": redirect_uri,
        "scope": "read:user user:email",
        "state": state,
    }
    return f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}", state


def _post_token(url: str, data: dict) -> dict:
    try:
        response = httpx.post(
            url,
            headers={"Accept": "application/json"},
            data=data,
            timeout=10,
        )
        body = response.json()
    except Exception:
        logger.warning("OAuth token exchange transport failure")
        raise OAuthError(
            "exchange_failed",
            "Could not complete sign-in with the provider.",
            502,
        )
    if isinstance(body, dict) and body.get("error"):
        logger.warning("OAuth token exchange rejected by provider")
        raise OAuthError(
            "exchange_failed",
            "Could not complete sign-in with the provider.",
            502,
        )
    if not isinstance(body, dict) or not body.get("access_token"):
        logger.warning("OAuth token exchange returned no access token")
        raise OAuthError(
            "exchange_failed",
            "Could not complete sign-in with the provider.",
            502,
        )
    return body


def _get_json(url: str, access_token: str) -> dict | list:
    try:
        response = httpx.get(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=10,
        )
        return response.json()
    except Exception:
        logger.warning("OAuth userinfo transport failure")
        raise OAuthError(
            "provider_error",
            "Could not verify your provider identity.",
            502,
        )


def exchange_code(provider: str, code: str) -> tuple[str, bool, str]:
    """Exchange ``code`` for (email, email_verified, provider_user_id).

    Never accepts a raw email as identity — every value here comes from a
    provider-verified response. Raises OAuthError on any failure.
    """
    redirect_uri = expected_redirect_uri(provider)
    if provider == GOOGLE:
        token = _post_token(
            GOOGLE_TOKEN_URL,
            {
                "code": code,
                "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        info = _get_json(GOOGLE_USERINFO_URL, token["access_token"])
        if not isinstance(info, dict):
            raise OAuthError("provider_error", "Invalid provider response.", 502)
        email = str(info.get("email", "") or "").lower().strip()
        verified = bool(info.get("email_verified"))
        subject = str(info.get("sub", "") or "")
        if not email or not subject:
            raise OAuthError(
                "email_required",
                "Your Google account did not provide an email address.",
                400,
            )
        return email, verified, subject
    if provider == GITHUB:
        token = _post_token(
            GITHUB_TOKEN_URL,
            {
                "code": code,
                "client_id": os.getenv("GITHUB_CLIENT_ID", ""),
                "client_secret": os.getenv("GITHUB_CLIENT_SECRET", ""),
            },
        )
        access_token = token["access_token"]
        me = _get_json(GITHUB_USER_URL, access_token)
        emails = _get_json(GITHUB_EMAILS_URL, access_token)
        if not isinstance(me, dict) or not isinstance(emails, list):
            raise OAuthError("provider_error", "Invalid provider response.", 502)
        subject = str(me.get("id", "") or "")
        primary = next(
            (e for e in emails if isinstance(e, dict) and e.get("primary")),
            None,
        )
        candidate = primary or next(
            (e for e in emails if isinstance(e, dict) and e.get("email")),
            None,
        )
        email = str((candidate or {}).get("email", "") or "").lower().strip()
        verified = bool((candidate or {}).get("verified"))
        if not email or not subject:
            raise OAuthError(
                "email_required",
                "Your GitHub account did not provide an email address.",
                400,
            )
        return email, verified, subject
    raise OAuthError("unknown_provider", "Unknown OAuth provider.", 400)


def link_or_create_user(provider: str, email: str, provider_user_id: str):
    """Apply the account-linking rules. Returns (user, created).

    1. Known provider identity -> that user (email conflict guarded).
    2. Verified email matches an existing account -> link, keep password.
    3. Otherwise -> create user with unusable password + link.
    Unverified callers must be rejected before calling (403 upstream).
    """
    from .models import OAuthAccount, OnboardingProgress, User

    identity = OAuthAccount.objects.select_related("user").filter(
        provider=provider, provider_user_id=provider_user_id
    ).first()
    if identity is not None:
        user = identity.user
        updates = []
        if user.email != email:
            clash = User.objects.filter(email=email).exclude(pk=user.pk).first()
            if clash is not None:
                raise OAuthError(
                    "email_conflict",
                    "This provider identity is linked to a different "
                    "account. Contact support.",
                    409,
                )
            user.email = email
            updates.append("email")
            user.save(update_fields=updates)
        if identity.email != email:
            identity.email = email
            identity.save(update_fields=["email"])
        return user, False

    user = User.objects.filter(email=email).first()
    created = False
    if user is None:
        user = User.objects.create_user(email=email, password=None)
        user.set_unusable_password()
        user.save()
        from billing.models import get_or_create_subscription

        get_or_create_subscription(user)
        OnboardingProgress.objects.get_or_create(user=user)
        created = True

    OAuthAccount.objects.get_or_create(
        provider=provider,
        provider_user_id=provider_user_id,
        defaults={"user": user, "email": email},
    )
    return user, created
