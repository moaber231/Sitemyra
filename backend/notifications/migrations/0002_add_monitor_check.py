from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
        ("monitors", "0002_monitorcheck"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificationevent",
            name="monitor_check",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="notification_events",
                to="monitors.monitorcheck",
            ),
        ),
        migrations.AlterField(
            model_name="notificationevent",
            name="monitor_check",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="notification_events",
                to="monitors.monitorcheck",
            ),
        ),
        migrations.AddConstraint(
            model_name="notificationevent",
            constraint=models.UniqueConstraint(
                fields=("monitor_check", "event_type"),
                name="unique_notification_event_per_check",
            ),
        ),
    ]
