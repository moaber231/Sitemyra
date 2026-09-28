import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("monitors", "0005_monitorcheck_monitors_mo_checked_5587c0_idx"),
    ]

    operations = [
        migrations.AlterField(
            model_name="monitor",
            name="url",
            field=models.URLField(
                max_length=1000,
                validators=[
                    django.core.validators.URLValidator(schemes=("http", "https"))
                ],
            ),
        ),
    ]
