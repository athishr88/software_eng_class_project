from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Buyer", "0013_cartitem_steward_free"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="is_steward_free",
            field=models.BooleanField(default=False),
        ),
    ]
