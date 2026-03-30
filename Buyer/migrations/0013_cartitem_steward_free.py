from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Buyer", "0012_order_steward_contribution_cents"),
    ]

    operations = [
        migrations.AddField(
            model_name="cartitem",
            name="is_steward_free",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="cartitem",
            name="steward_free_list_price_cents",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
