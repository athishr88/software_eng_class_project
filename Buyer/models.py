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
    shipping_address = models.ForeignKey("ShippingAddress", on_delete=models.SET_NULL, blank=True, null=True)
    payment_method = models.ForeignKey("PaymentMethod", on_delete=models.SET_NULL, blank=True, null=True)
    
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="pending")

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    fees = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount_cents = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    

    def __str__(self):
        return f"Order {self.id} - {self.user.username}"


class OrderItem(models.Model):
    order = models.ForeignKey("Order", on_delete=models.CASCADE, related_name="items")
    book = models.ForeignKey("General.Book", on_delete=models.SET_NULL, null=True, blank=True)

    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    created_at = models.DateTimeField(auto_now_add=True)

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
