from django.db import migrations, models


def mark_existing_buyers_as_approved(apps, schema_editor):
    User = apps.get_model("General", "User")
    User.objects.filter(role="buyer").update(buyer_approved=True)


class Migration(migrations.Migration):

    dependencies = [
        ("General", "0013_user_seller_approved_user_seller_approved_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="buyer_approved",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="buyer_approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(mark_existing_buyers_as_approved, migrations.RunPython.noop),
    ]
