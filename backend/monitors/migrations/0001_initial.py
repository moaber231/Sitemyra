import uuid

import django.core.validators
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Monitor",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=150)),
                ("url", models.URLField(validators=[django.core.validators.URLValidator(schemes=("http", "https"))])),
                ("active", models.BooleanField(default=True)),
                ("check_interval", models.PositiveIntegerField(choices=[(300, "5 minutes"), (900, "15 minutes"), (1800, "30 minutes"), (3600, "60 minutes")], default=3600)),
                ("timeout", models.PositiveIntegerField(default=15, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(120)])),
                ("next_check_at", models.DateTimeField(blank=True, null=True)),
                ("last_checked_at", models.DateTimeField(blank=True, null=True)),
                ("last_success_at", models.DateTimeField(blank=True, null=True)),
                ("last_changed_at", models.DateTimeField(blank=True, null=True)),
                ("last_content_hash", models.CharField(blank=True, max_length=64)),
                ("last_status_code", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="monitors", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="monitor",
            index=models.Index(fields=["user", "active"], name="monitors_mo_user_id_3afdff_idx"),
        ),
        migrations.AddIndex(
            model_name="monitor",
            index=models.Index(fields=["active", "next_check_at"], name="monitors_mo_active_2827c0_idx"),
        ),
        migrations.AddIndex(
            model_name="monitor",
            index=models.Index(fields=["user", "next_check_at"], name="monitors_mo_user_id_e83d93_idx"),
        ),
        migrations.AddConstraint(
            model_name="monitor",
            constraint=models.CheckConstraint(condition=Q(("timeout__gte", 1), ("timeout__lte", 120)), name="monitor_timeout_range"),
        ),
    ]
