# Clear cover_image_url for all books so covers use book_images/ (or default.jpg)

from django.db import migrations


def clear_cover_image_url(apps, schema_editor):
    Book = apps.get_model("General", "Book")
    Book.objects.all().update(cover_image_url=None)


def noop_reverse(apps, schema_editor):
    pass  # We don't restore previous URLs; leave as null


class Migration(migrations.Migration):

    dependencies = [
        ("General", "0008_alter_user_role"),
    ]

    operations = [
        migrations.RunPython(clear_cover_image_url, noop_reverse),
    ]
