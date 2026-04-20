from django.conf import settings
from django.db import models

from General.models import User, Book, Address, StewardContribution


class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=30, default="active")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart of {self.user.email}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE)
    book = models.ForeignKey("General.Book", on_delete=models.CASCADE)

    quantity = models.PositiveIntegerField()
    unit_price_cents = models.PositiveIntegerField()
    is_steward_free = models.BooleanField(default=False)
    # List price at time of free redemption (pool deduction); 0 if not a steward-free line.
    steward_free_list_price_cents = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cart", "book"], name="unique_cart_book")
        ]

    def __str__(self):
        return f"{self.book.title} x {self.quantity}"
    


class PaymentMethod(models.Model):
    """
    Saved card display data for checkout. Only last4 + meta are stored — never full PAN or CVV.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="payment_methods",
    )
    cardholder_name = models.CharField(max_length=120)
    brand = models.CharField(max_length=40)
    last4 = models.CharField(max_length=4)
    exp_month = models.PositiveSmallIntegerField()
    exp_year = models.PositiveSmallIntegerField()
    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "-updated_at"]

    def __str__(self):
        return f"{self.brand} *{self.last4} ({self.user.email})"


class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
        ("refunded", "Refunded"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
<<<<<<< HEAD
    shipping_address = models.ForeignKey(Address, on_delete=models.SET_NULL, blank=True, null=True)
    steward_contribution = models.ForeignKey(
        StewardContribution,
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="orders",
    )

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="pending")

    subtotal_cents = models.PositiveIntegerField()
    tax_cents = models.PositiveIntegerField(default=0)
    fees_cents = models.PositiveIntegerField(default=0)
    discount_cents = models.PositiveIntegerField(default=0)
    total_cents = models.PositiveIntegerField()
=======
    shipping_address = models.ForeignKey("ShippingAddress", on_delete=models.SET_NULL, blank=True, null=True)
    payment_method = models.ForeignKey("PaymentMethod", on_delete=models.SET_NULL, blank=True, null=True)
    
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="pending")

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    fees = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount_cents = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
>>>>>>> recover-missing-work

    # Optional checkout add-on; $1 contribution → 10 steward progress points (stored on User).
    steward_contribution_cents = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    

    def __str__(self):
        return f"Order {self.id} - {self.user.username}"

    @property
    def total_dollars(self):
        return self.total_cents / 100.0

    @property
    def discount_dollars(self):
        return self.discount_cents / 100.0

    @property
    def tax_dollars(self):
        return self.tax_cents / 100.0

    @property
    def fees_dollars(self):
        return self.fees_cents / 100.0

    @property
    def subtotal_dollars(self):
        return self.subtotal_cents / 100.0

    @property
    def steward_contribution_dollars(self):
        return self.steward_contribution_cents / 100.0


class OrderItem(models.Model):
<<<<<<< HEAD
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="orderitem")
    book = models.ForeignKey(Book, on_delete=models.CASCADE)

    # Denormalized at checkout (same moment as OrderItemBookSnapshot). default="" is for migration backfill only.
    title = models.CharField(max_length=255, default="")
    author = models.CharField(max_length=255, default="")

    deposit_required = models.BooleanField(default=False)
    # Stored in cents to avoid floating point issues.
    deposit_amount_cents = models.PositiveIntegerField(default=0)

    quantity = models.PositiveIntegerField()
    unit_price_cents = models.PositiveIntegerField()
    line_total_cents = models.PositiveIntegerField()
    is_steward_free = models.BooleanField(default=False)
=======
    order = models.ForeignKey("Order", on_delete=models.CASCADE, related_name="items")
    book = models.ForeignKey("General.Book", on_delete=models.SET_NULL, null=True, blank=True)

    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
>>>>>>> recover-missing-work

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def deposit_amount(self) -> float:
        """Deposit amount in dollars (for templates)."""
        return self.deposit_amount_cents / 100.0

    def __str__(self):
        return f" {self.book} x {self.quantity})"

class ReturnRequest(models.Model):
    STATUS_CHOICES = [
        ("requested", "Requested"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("received", "Received"),
        ("refunded", "Refunded"),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    reason = models.TextField()

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="requested")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"ReturnRequest for Order {self.order_id}"
<<<<<<< HEAD


class SellerReturnReceipt(models.Model):
    """
    Records that a seller received returned inventory for an order and triggered
    buyer credit + removal of that seller's lines from their sales totals.
    """

    return_request = models.ForeignKey(
        ReturnRequest,
        on_delete=models.CASCADE,
        related_name="seller_receipts",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="return_receipts_given",
    )
    amount_credited_cents = models.PositiveIntegerField(
        help_text="Sum of this seller's line totals for the order (credited to buyer).",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["return_request", "seller"],
                name="unique_seller_return_receipt_per_return",
            )
        ]

    def __str__(self):
        return f"SellerReturnReceipt rr={self.return_request_id} seller={self.seller_id}"
=======
    
class ShippingAddress(models.Model):
    user=models.ForeignKey(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default="USA")
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=20)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.full_name} - {self.address_line_1}"
    
class PaymentMethod(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    cardholder = models.CharField(max_length=100, blank=True)
    processor_token = models.CharField(max_length=225)
    last4 = models.CharField(max_length=4)
    brand = models.CharField(max_length=30)
    exp_month = models.IntegerField()
    exp_year = models.IntegerField()
    is_default = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.brand} ending in {self.last4}"
    
class ReturnRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("received", "Recieved"),
        ("refunded", "Refunded"),
    ]

    order = models.ForeignKey("Order", on_delete=models.CASCADE)
    order_item = models.ForeignKey("OrderItem", on_delete=models.CASCADE, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    reason = models.TextField()
    details = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Return Request #{self.id} for Order #{self.order.id}"
    
class Review(models.Model):
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    book = models.ForeignKey("General.Book", on_delete=models.CASCADE)
    order = models.ForeignKey("Order", on_delete=models.CASCADE)
    order_item = models.ForeignKey("OrderItem", on_delete=models.CASCADE)
    rating = models.PositiveIntegerField()
    comment = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "order_item")

    def __str__(self):
        return f"{self.book.title} for {self.rating} stars"
>>>>>>> recover-missing-work
