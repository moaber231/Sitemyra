from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("monitors", "0003_advancedmonitorconfig_changediff_pricepoint"),
        ("workspaces", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="monitor",
            name="workspace",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="monitors", to="workspaces.workspace"),
        ),
        migrations.AlterField(
            model_name="monitor",
            name="check_interval",
            field=models.PositiveIntegerField(choices=[(30, "30 seconds"), (60, "1 minute"), (300, "5 minutes"), (900, "15 minutes"), (1800, "30 minutes"), (3600, "60 minutes")], default=3600),
        ),
    ]
