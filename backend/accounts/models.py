import hashlib
import secrets
import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # Phase 3: competitive-intelligence narration is OPT-IN. Off by
    # default, and it has no effect at all unless a provider is configured.
    # When off, Sitemyra makes no outbound AI request.
    ai_narration_enabled = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        self.email = self.__class__.objects.normalize_email(self.email).lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


class OAuthAccount(models.Model):
    """Links a user to a Google/GitHub SSO identity."""

    GOOGLE = "google"
    GITHUB = "github"
    PROVIDER_CHOICES = ((GOOGLE, "Google"), (GITHUB, "GitHub"))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="oauth_accounts",
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    provider_user_id = models.CharField(max_length=255)
    email = models.EmailField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_user_id"],
                name="unique_oauth_identity",
            )
        ]

    def __str__(self):
        return f"{self.user} via {self.provider}"


class OnboardingProgress(models.Model):
    """3-step onboarding wizard state: URL -> engine -> webhook."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="onboarding",
    )
    step = models.PositiveSmallIntegerField(default=1)
    completed = models.BooleanField(default=False)
    first_monitor_id = models.UUIDField(null=True, blank=True)
    engine = models.CharField(max_length=20, blank=True, default="")
    webhook_configured = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Onboarding({self.user}, step={self.step})"


class ApiKey(models.Model):
    """Developer Bearer tokens for programmatic headless monitoring.

    Only a SHA-256 hash is stored; the raw secret is shown once at creation.
    Prefix (apeiro_XXXX) allows identification without leaking the secret.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_keys",
    )
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="api_keys",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=120)
    prefix = models.CharField(max_length=20, default="")
    key_hash = models.CharField(max_length=64)
    scopes = models.CharField(max_length=255, blank=True, default="monitors:read monitors:write")
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["prefix"])]

    @staticmethod
    def hash_secret(raw: str) -> str:
        return hashlib.sha256(raw.encode()).hexdigest()

    @classmethod
    def generate(cls, user, name, workspace=None, scopes=""):
        raw = f"apeiro_{secrets.token_urlsafe(32)}"
        prefix = raw[:14]
        obj = cls.objects.create(
            user=user,
            workspace=workspace,
            name=name,
            prefix=prefix,
            key_hash=cls.hash_secret(raw),
            scopes=scopes or "monitors:read monitors:write",
        )
        return obj, raw

    def __str__(self):
        return f"{self.name} ({self.prefix}...)"
