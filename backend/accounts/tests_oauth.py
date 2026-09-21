"""Phase 3 OAuth tests — real authorization-code flow (mocked providers)."""

import os
from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import OAuthAccount, User


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


GOOGLE_ENV = {
    "GOOGLE_CLIENT_ID": "google-id",
    "GOOGLE_CLIENT_SECRET": "google-secret",
    "GOOGLE_REDIRECT_URI": "https://app.example.com/auth/callback",
}
GITHUB_ENV = {
    "GITHUB_CLIENT_ID": "github-id",
    "GITHUB_CLIENT_SECRET": "github-secret",
    "GITHUB_REDIRECT_URI": "https://app.example.com/auth/callback",
}


def google_mocks(email="guser@example.com", verified=True, sub="google-123"):
    def fake_post(url, **kwargs):
        assert "googleapis.com" in url
        data = kwargs.get("data", {})
        assert data.get("client_secret") == "google-secret"
        assert data.get("code")
        return FakeResponse({"access_token": "google-token"})

    def fake_get(url, **kwargs):
        assert kwargs["headers"]["Authorization"] == "Bearer google-token"
        return FakeResponse(
            {"email": email, "email_verified": verified, "sub": sub}
        )

    return fake_post, fake_get


def github_mocks(email="ghuser@example.com", verified=True, uid=4242):
    def fake_post(url, **kwargs):
        assert "github.com" in url
        data = kwargs.get("data", {})
        assert data.get("client_secret") == "github-secret"
        assert data.get("code")
        return FakeResponse({"access_token": "github-token"})

    def fake_get(url, **kwargs):
        assert kwargs["headers"]["Authorization"] == "Bearer github-token"
        if url.endswith("/user/emails"):
            return FakeResponse(
                [{"email": email, "primary": True, "verified": verified}]
            )
        return FakeResponse({"id": uid, "login": "octo"})

    return fake_post, fake_get


@override_settings(DEBUG=True)
class OAuthStatusStartTests(APITestCase):
    def test_status_reports_enabled_only_when_configured(self):
        with patch.dict(os.environ, {}, clear=False):
            for key in (
                "GOOGLE_CLIENT_ID",
                "GOOGLE_CLIENT_SECRET",
                "GITHUB_CLIENT_ID",
                "GITHUB_CLIENT_SECRET",
            ):
                os.environ.pop(key, None)
            response = self.client.get(reverse("oauth-status"))
            self.assertFalse(response.data["providers"]["google"]["enabled"])
            self.assertFalse(response.data["providers"]["github"]["enabled"])
            self.assertIsNone(
                response.data["providers"]["google"]["redirect_uri"]
            )

        with patch.dict(os.environ, {**GOOGLE_ENV, **GITHUB_ENV}):
            response = self.client.get(reverse("oauth-status"))
            self.assertTrue(response.data["providers"]["google"]["enabled"])
            self.assertTrue(response.data["providers"]["github"]["enabled"])
            # No secret values leak through the status endpoint.
            self.assertNotIn("google-secret", str(response.data))
            self.assertNotIn("github-secret", str(response.data))

    def test_start_returns_provider_url_and_state(self):
        with patch.dict(os.environ, GOOGLE_ENV, clear=False):
            response = self.client.get(
                reverse("oauth-start", kwargs={"provider": "google"})
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn(
                "accounts.google.com", response.data["authorization_url"]
            )
            self.assertTrue(response.data["state"])

    def test_start_unconfigured_returns_503(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GITHUB_CLIENT_ID", None)
            os.environ.pop("GITHUB_CLIENT_SECRET", None)
            response = self.client.get(
                reverse("oauth-start", kwargs={"provider": "github"})
            )
            self.assertEqual(
                response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE
            )
            self.assertEqual(response.data["code"], "oauth_unavailable")

    def test_start_unknown_provider(self):
        response = self.client.get(
            reverse("oauth-start", kwargs={"provider": "microsoft"})
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class OAuthInsecureRedirectTests(APITestCase):
    @override_settings(DEBUG=False)
    def test_http_redirect_refused_in_production(self):
        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "id",
                "GOOGLE_CLIENT_SECRET": "secret",
                "GOOGLE_REDIRECT_URI": "http://insecure.example.com/callback",
            },
            clear=False,
        ):
            response = self.client.get(
                reverse("oauth-start", kwargs={"provider": "google"})
            )
            self.assertEqual(
                response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE
            )
            self.assertEqual(response.data["code"], "oauth_misconfigured")


@override_settings(DEBUG=True)
class GoogleCallbackTests(APITestCase):
    def _start_state(self):
        with patch.dict(os.environ, GOOGLE_ENV, clear=False):
            response = self.client.get(
                reverse("oauth-start", kwargs={"provider": "google"})
            )
            return response.data["state"]

    def _callback(self, **params):
        url = reverse("oauth-callback", kwargs={"provider": "google"})
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return self.client.get(f"{url}?{query}")

    def test_successful_google_login_new_account(self):
        state = self._start_state()
        fake_post, fake_get = google_mocks()
        with patch.dict(os.environ, GOOGLE_ENV, clear=False), patch(
            "accounts.oauth.httpx.post", side_effect=fake_post
        ), patch("accounts.oauth.httpx.get", side_effect=fake_get):
            response = self._callback(code="auth-code", state=state)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertTrue(response.data["created"])
        user = User.objects.get(email="guser@example.com")
        self.assertFalse(user.has_usable_password())
        identity = OAuthAccount.objects.get(
            provider="google", provider_user_id="google-123"
        )
        self.assertEqual(identity.user, user)

    def test_invalid_state_rejected(self):
        fake_post, fake_get = google_mocks()
        with patch.dict(os.environ, GOOGLE_ENV, clear=False), patch(
            "accounts.oauth.httpx.post", side_effect=fake_post
        ), patch("accounts.oauth.httpx.get", side_effect=fake_get):
            response = self._callback(code="auth-code", state="bogus")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "invalid_state")
        self.assertFalse(User.objects.exists())

    def test_tampered_state_rejected(self):
        state = self._start_state() + "tampered"
        fake_post, fake_get = google_mocks()
        with patch.dict(os.environ, GOOGLE_ENV, clear=False), patch(
            "accounts.oauth.httpx.post", side_effect=fake_post
        ), patch("accounts.oauth.httpx.get", side_effect=fake_get):
            response = self._callback(code="auth-code", state=state)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "invalid_state")

    def test_missing_code_rejected(self):
        state = self._start_state()
        response = self._callback(state=state)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "invalid_callback")

    def test_denied_authorization(self):
        url = reverse("oauth-callback", kwargs={"provider": "google"})
        response = self.client.get(f"{url}?error=access_denied&state=x")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "access_denied")
        self.assertFalse(User.objects.exists())

    def test_unverified_email_rejected(self):
        state = self._start_state()
        fake_post, fake_get = google_mocks(verified=False)
        with patch.dict(os.environ, GOOGLE_ENV, clear=False), patch(
            "accounts.oauth.httpx.post", side_effect=fake_post
        ), patch("accounts.oauth.httpx.get", side_effect=fake_get):
            response = self._callback(code="auth-code", state=state)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "email_unverified")
        self.assertFalse(User.objects.exists())

    def test_repeat_login_returns_same_user(self):
        state = self._start_state()
        fake_post, fake_get = google_mocks()
        with patch.dict(os.environ, GOOGLE_ENV, clear=False), patch(
            "accounts.oauth.httpx.post", side_effect=fake_post
        ), patch("accounts.oauth.httpx.get", side_effect=fake_get):
            first = self._callback(code="c1", state=state)
            second = self._callback(code="c2", state=self._start_state())
        self.assertFalse(second.data["created"])
        self.assertEqual(first.data["user"], second.data["user"])
        self.assertEqual(User.objects.count(), 1)

    def test_email_conflict_not_merged(self):
        user_a = User.objects.create_user("a@example.com", "pw-a-strong")
        other = User.objects.create_user("b@example.com", "pw-b-strong")
        OAuthAccount.objects.create(
            user=user_a,
            provider="google",
            provider_user_id="google-123",
            email="a@example.com",
        )
        state = self._start_state()
        # Provider now reports the same subject with another user's email.
        fake_post, fake_get = google_mocks(email="b@example.com", sub="google-123")
        with patch.dict(os.environ, GOOGLE_ENV, clear=False), patch(
            "accounts.oauth.httpx.post", side_effect=fake_post
        ), patch("accounts.oauth.httpx.get", side_effect=fake_get):
            response = self._callback(code="auth-code", state=state)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "email_conflict")
        user_a.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(user_a.email, "a@example.com")
        self.assertEqual(other.email, "b@example.com")


@override_settings(DEBUG=True)
class GitHubCallbackTests(APITestCase):
    def _callback(self, **params):
        url = reverse("oauth-callback", kwargs={"provider": "github"})
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return self.client.get(f"{url}?{query}")

    def test_successful_github_login_links_existing_password_account(self):
        user = User.objects.create_user(
            "ghuser@example.com", "a-strong-password"
        )
        with patch.dict(os.environ, GITHUB_ENV, clear=False):
            state = self.client.get(
                reverse("oauth-start", kwargs={"provider": "github"})
            ).data["state"]
        fake_post, fake_get = github_mocks()
        with patch.dict(os.environ, GITHUB_ENV, clear=False), patch(
            "accounts.oauth.httpx.post", side_effect=fake_post
        ), patch("accounts.oauth.httpx.get", side_effect=fake_get):
            response = self._callback(code="auth-code", state=state)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["created"])
        self.assertEqual(response.data["user"]["email"], "ghuser@example.com")
        identity = OAuthAccount.objects.get(
            provider="github", provider_user_id="4242"
        )
        self.assertEqual(identity.user, user)
        # Password login keeps working after linking.
        user.refresh_from_db()
        self.assertTrue(user.check_password("a-strong-password"))

    def test_github_unverified_email_rejected(self):
        with patch.dict(os.environ, GITHUB_ENV, clear=False):
            state = self.client.get(
                reverse("oauth-start", kwargs={"provider": "github"})
            ).data["state"]
        fake_post, fake_get = github_mocks(verified=False)
        with patch.dict(os.environ, GITHUB_ENV, clear=False), patch(
            "accounts.oauth.httpx.post", side_effect=fake_post
        ), patch("accounts.oauth.httpx.get", side_effect=fake_get):
            response = self._callback(code="auth-code", state=state)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "email_unverified")
        self.assertFalse(User.objects.exists())

    def test_github_no_usable_email(self):
        with patch.dict(os.environ, GITHUB_ENV, clear=False):
            state = self.client.get(
                reverse("oauth-start", kwargs={"provider": "github"})
            ).data["state"]

        def fake_get_empty(url, **kwargs):
            if url.endswith("/user/emails"):
                return FakeResponse([])
            return FakeResponse({"id": 99, "login": "noemail"})

        with patch.dict(os.environ, GITHUB_ENV, clear=False), patch(
            "accounts.oauth.httpx.post",
            return_value=FakeResponse({"access_token": "t"}),
        ), patch("accounts.oauth.httpx.get", side_effect=fake_get_empty):
            response = self._callback(code="auth-code", state=state)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "email_required")
        self.assertFalse(User.objects.exists())

    def test_cross_provider_state_rejected(self):
        # State minted for google must not validate on the github callback.
        with patch.dict(
            os.environ, {**GOOGLE_ENV, **GITHUB_ENV}, clear=False
        ):
            google_state = self.client.get(
                reverse("oauth-start", kwargs={"provider": "google"})
            ).data["state"]
        fake_post, fake_get = github_mocks()
        with patch.dict(os.environ, GITHUB_ENV, clear=False), patch(
            "accounts.oauth.httpx.post", side_effect=fake_post
        ), patch("accounts.oauth.httpx.get", side_effect=fake_get):
            response = self._callback(code="auth-code", state=google_state)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "invalid_state")


@override_settings(DEBUG=True)
class PasswordAuthUnaffectedTests(APITestCase):
    def test_password_login_refresh_me_and_logout(self):
        User.objects.create_user("user@example.com", "a-strong-password")
        login = self.client.post(
            reverse("login"),
            {"email": "user@example.com", "password": "a-strong-password"},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login.data['access']}"
        )
        me = self.client.get(reverse("me"))
        self.assertEqual(me.status_code, status.HTTP_200_OK)

        refresh = self.client.post(
            reverse("refresh"),
            {"refresh": login.data["refresh"]},
            format="json",
        )
        self.assertEqual(refresh.status_code, status.HTTP_200_OK)
        # Logout is client-side token discard: tokens simply stop being sent.
        self.client.credentials()
        anonymous = self.client.get(reverse("me"))
        self.assertEqual(
            anonymous.status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_self_asserted_email_still_rejected(self):
        response = self.client.post(
            reverse("oauth-login"),
            {
                "provider": "google",
                "email": "victim@example.com",
                "provider_user_id": "google:victim@example.com",
            },
            format="json",
        )
        self.assertIn(
            response.status_code,
            (
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_503_SERVICE_UNAVAILABLE,
            ),
        )
        self.assertFalse(
            User.objects.filter(email="victim@example.com").exists()
        )
