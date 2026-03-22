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
    book = models.ForeignKey(Book, on_delete=models.CASCADE)

    quantity = models.PositiveIntegerField()
    unit_price_cents = models.PositiveIntegerField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cart", "book"], name="unique_cart_book")
        ]

    def __str__(self):
        return f"{self.book.title} x {self.quantity}"

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
    shipping_address = models.ForeignKey(Address, on_delete=models.SET_NULL, blank=True, null=True)
    steward_contribution = models.ForeignKey(
        StewardContribution,
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="pending")

    subtotal_cents = models.PositiveIntegerField()
    discount_cents = models.PositiveIntegerField(default=0)
    total_cents = models.PositiveIntegerField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    

    def __str__(self):
        return f"Order {self.id} - {self.user.email}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)

    quantity = models.PositiveIntegerField()
    unit_price_cents = models.PositiveIntegerField()
    line_total_cents = models.PositiveIntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"OrderItem {self.id} (Order {self.order_id})"


class OrderShippingAddress(models.Model):
    """
    Snapshot of the shipping address at the moment the order was placed.

    This prevents past orders from changing if the buyer edits their saved `Address`.
    """

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="shipping_snapshot")

    shipping_name = models.CharField(max_length=100, blank=True, null=True)
    shipping_line1 = models.CharField(max_length=255)
    shipping_line2 = models.CharField(max_length=255, blank=True, null=True)

    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100)
    shipping_postal_code = models.CharField(max_length=30)
    shipping_country = models.CharField(max_length=100)

    # Optional provenance to help debugging/auditing.
    source_address = models.ForeignKey(Address, on_delete=models.SET_NULL, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Shipping snapshot for Order {self.order_id}"


class OrderItemBookSnapshot(models.Model):
    """
    Snapshot of book details at the moment an order item was created.

    This allows cart/order history to show the purchased book's details even if
    the live `Book` listing is edited later.
    """

    order_item = models.OneToOneField(OrderItem, on_delete=models.CASCADE, related_name="book_snapshot")

    source_book = models.ForeignKey(Book, on_delete=models.SET_NULL, blank=True, null=True)

    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    isbn = models.CharField(max_length=40, blank=True, null=True)
    language = models.CharField(max_length=60, blank=True, null=True)
    publisher = models.CharField(max_length=255, blank=True, null=True)
    publication_year = models.IntegerField(blank=True, null=True)

    cover_image_url = models.TextField(blank=True, null=True)
    condition = models.CharField(max_length=100)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Book snapshot for OrderItem {self.order_item_id}"


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