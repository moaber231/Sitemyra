from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("workspaces", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="OAuthAccount",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("provider", models.CharField(choices=[("google", "Google"), ("github", "GitHub")], max_length=20)),
                ("provider_user_id", models.CharField(max_length=255)),
                ("email", models.EmailField(blank=True, default="", max_length=254)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="oauth_accounts", to="accounts.user")),
            ],
        ),
        migrations.CreateModel(
            name="OnboardingProgress",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("step", models.PositiveSmallIntegerField(default=1)),
                ("completed", models.BooleanField(default=False)),
                ("first_monitor_id", models.UUIDField(blank=True, null=True)),
                ("engine", models.CharField(blank=True, default="", max_length=20)),
                ("webhook_configured", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="onboarding", to="accounts.user")),
            ],
        ),
        migrations.CreateModel(
            name="ApiKey",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=120)),
                ("prefix", models.CharField(default="", max_length=20)),
                ("key_hash", models.CharField(max_length=64)),
                ("scopes", models.CharField(blank=True, default="monitors:read monitors:write", max_length=255)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("revoked", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="api_keys", to="accounts.user")),
                ("workspace", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="api_keys", to="workspaces.workspace")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="oauthaccount",
            constraint=models.UniqueConstraint(fields=("provider", "provider_user_id"), name="unique_oauth_identity"),
        ),
        migrations.AddIndex(
            model_name="apikey",
            index=models.Index(fields=["prefix"], name="accounts_ap_prefix_3d2c46_idx"),
        ),
    ]
