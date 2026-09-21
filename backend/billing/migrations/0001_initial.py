from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("plan", models.CharField(choices=[("free", "Free"), ("pro", "Pro"), ("business", "Business")], default="free", max_length=20)),
                ("status", models.CharField(choices=[("active", "Active"), ("trialing", "Trialing"), ("past_due", "Past due"), ("canceled", "Canceled"), ("incomplete", "Incomplete")], default="active", max_length=20)),
                ("stripe_customer_id", models.CharField(blank=True, default="", max_length=120)),
                ("stripe_subscription_id", models.CharField(blank=True, default="", max_length=120)),
                ("current_period_end", models.DateTimeField(blank=True, null=True)),
                ("cancel_at_period_end", models.BooleanField(default=False)),
                ("mrr_cents", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="subscription", to="accounts.user")),
            ],
        ),
    ]
