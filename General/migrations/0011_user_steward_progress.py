import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("General", "0010_user_store_credit_cents"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="steward_progress",
            field=models.PositiveSmallIntegerField(
                default=0,
                validators=[django.core.validators.MaxValueValidator(100)],
            ),
        ),
    ]
