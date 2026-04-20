from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Buyer", "0011_alter_orderitem_order"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="steward_contribution_cents",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
