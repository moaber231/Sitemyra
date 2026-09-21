from django.db import migrations, models
import django.db.models.deletion
import uuid
import workspaces.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Workspace",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=150)),
                ("slug", models.SlugField(blank=True, max_length=180, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="owned_workspaces", to="accounts.user")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="WorkspaceMembership",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("role", models.CharField(choices=[("owner", "Owner"), ("admin", "Admin"), ("viewer", "Viewer")], default="viewer", max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="workspace_memberships", to="accounts.user")),
                ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="workspaces.workspace")),
            ],
        ),
        migrations.CreateModel(
            name="WorkspaceInvite",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("email", models.EmailField(max_length=254)),
                ("role", models.CharField(choices=[("owner", "Owner"), ("admin", "Admin"), ("viewer", "Viewer")], default="viewer", max_length=10)),
                ("token", models.CharField(default=workspaces.models.generate_invite_token, max_length=64, unique=True)),
                ("accepted", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sent_invites", to="accounts.user")),
                ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="invites", to="workspaces.workspace")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="workspacemembership",
            constraint=models.UniqueConstraint(fields=("workspace", "user"), name="unique_workspace_member"),
        ),
        migrations.AddIndex(
            model_name="workspacemembership",
            index=models.Index(fields=["workspace", "role"], name="workspaces__workspa_4b8c6e_idx"),
        ),
    ]
