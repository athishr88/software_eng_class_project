from django.db import migrations, models


def seed_steward_pool(apps, schema_editor):
    StewardPool = apps.get_model("General", "StewardPool")
    StewardPool.objects.get_or_create(pk=1, defaults={"pool_cents": 100_000_000})


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("General", "0011_user_steward_progress"),
    ]

    operations = [
        migrations.CreateModel(
            name="StewardPool",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("pool_cents", models.PositiveBigIntegerField(default=100_000_000)),
            ],
            options={
                "verbose_name": "Steward contribution pool",
            },
        ),
        migrations.AddField(
            model_name="user",
            name="last_free_book_redeemed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(seed_steward_pool, noop_reverse),
    ]
