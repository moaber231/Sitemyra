from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("notifications", "0002_add_monitor_check"),
        ("workspaces", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AlertChannel",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("channel_type", models.CharField(choices=[("slack", "Slack"), ("discord", "Discord"), ("email", "Email"), ("webhook", "Webhook"), ("sms", "SMS")], max_length=20)),
                ("name", models.CharField(max_length=120)),
                ("config_encrypted", models.TextField(blank=True, default="")),
                ("verified", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="alert_channels", to="accounts.user")),
                ("workspace", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="alert_channels", to="workspaces.workspace")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
