import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("Buyer", "0009_orderitem_deposit_amount_cents"),
    ]

    operations = [
        migrations.CreateModel(
            name="SellerReturnReceipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount_credited_cents", models.PositiveIntegerField(help_text="Sum of this seller's line totals for the order (credited to buyer).")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "return_request",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="seller_receipts",
                        to="Buyer.returnrequest",
                    ),
                ),
                (
                    "seller",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="return_receipts_given",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="sellerreturnreceipt",
            constraint=models.UniqueConstraint(fields=("return_request", "seller"), name="unique_seller_return_receipt_per_return"),
        ),
    ]
