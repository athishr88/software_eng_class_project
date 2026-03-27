# Generated/maintained to be idempotent on SQLite.
# The DB schema in this project may already include extra columns; this
# migration only adds `deposit_amount_cents` if the column is missing.

from django.db import migrations, models


def _sqlite_orderitem_columns(schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("PRAGMA table_info(Buyer_orderitem)")
        return {row[1] for row in cursor.fetchall()}


def _deposit_amount_cents_field():
    field = models.PositiveIntegerField(default=0)
    field.set_attributes_from_name("deposit_amount_cents")
    return field


def forward_add_deposit_amount_cents(apps, schema_editor):
    OrderItem = apps.get_model("Buyer", "OrderItem")
    if schema_editor.connection.vendor == "sqlite":
        cols = _sqlite_orderitem_columns(schema_editor)
        if "deposit_amount_cents" not in cols:
            schema_editor.add_field(OrderItem, _deposit_amount_cents_field())
        return

    schema_editor.add_field(OrderItem, _deposit_amount_cents_field())


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("Buyer", "0008_orderitem_deposit_required"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="orderitem",
                    name="deposit_amount_cents",
                    field=models.PositiveIntegerField(default=0),
                ),
            ],
            database_operations=[
                migrations.RunPython(forward_add_deposit_amount_cents, noop_reverse),
            ],
        ),
    ]

