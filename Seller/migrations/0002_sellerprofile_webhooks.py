from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Seller", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="sellerprofile",
            name="webhook_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="sellerprofile",
            name="webhook_secret",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="sellerprofile",
            name="webhook_url",
            field=models.URLField(blank=True, default="", max_length=2048),
        ),
    ]
