import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils.text import slugify


def generate_invite_token():
    return secrets.token_urlsafe(32)


class Workspace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    # Phase 5: an agency client workspace. NULLABLE on purpose — every
    # existing personal workspace stays null and behaves exactly as before.
    organization = models.ForeignKey(
        "intelligence.Organization",
        on_delete=models.CASCADE,
        related_name="client_workspaces",
        null=True,
        blank=True,
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_workspaces",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:60] or "workspace"
            candidate = base
            i = 1
            while (
                Workspace.objects.filter(slug=candidate)
                .exclude(pk=self.pk)
                .exists()
            ):
                i += 1
                candidate = f"{base}-{i}"
            self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class WorkspaceMembership(models.Model):
    OWNER = "owner"
    ADMIN = "admin"
    VIEWER = "viewer"
    ROLE_CHOICES = (
        (OWNER, "Owner"),
        (ADMIN, "Admin"),
        (VIEWER, "Viewer"),
    )
    ROLE_RANK = {VIEWER: 1, ADMIN: 2, OWNER: 3}

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workspace_memberships",
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=VIEWER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "user"], name="unique_workspace_member"
            )
        ]
        indexes = [models.Index(fields=["workspace", "role"])]

    def __str__(self):
        return f"{self.user} -> {self.workspace} ({self.role})"


class WorkspaceInvite(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="invites"
    )
    email = models.EmailField()
    role = models.CharField(
        max_length=10,
        choices=WorkspaceMembership.ROLE_CHOICES,
        default=WorkspaceMembership.VIEWER,
    )
    token = models.CharField(max_length=64, unique=True, default=generate_invite_token)
    accepted = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_invites",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invite {self.email} -> {self.workspace}"
