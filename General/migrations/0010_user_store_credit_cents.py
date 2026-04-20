from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("General", "0009_clear_book_cover_image_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="store_credit_cents",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
