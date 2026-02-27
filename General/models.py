from django.db import models

class User(models.Model):
    ROLE_CHOICES = [
        ("buyer", "Buyer"),
        ("steward", "Steward"),
        ("seller", "Seller"),
        ("admin", "Admin"),
    ]

    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    phone = models.CharField(max_length=50, blank=True, null=True)

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    steward_verified = models.BooleanField(default=False)
    steward_city = models.CharField(max_length=120, blank=True, null=True)

    is_active = models.BooleanField(default=True)

    last_login = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.email

class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    label = models.CharField(max_length=100, blank=True, null=True)
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True, null=True)

    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=30)
    country = models.CharField(max_length=100)

    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - {self.label}"

class Book(models.Model):
    seller_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    isbn = models.CharField(max_length=40, blank=True, null=True)
    language = models.CharField(max_length=60, blank=True, null=True)
    publisher = models.CharField(max_length=255, blank=True, null=True)
    publication_year = models.IntegerField(blank=True, null=True)

    cover_image_url = models.TextField(blank=True, null=True)

    condition = models.CharField(max_length=100)

    base_price_cents = models.PositiveIntegerField()

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

class Inventory(models.Model):
    book = models.OneToOneField(Book, on_delete=models.CASCADE)

    quantity_available = models.PositiveIntegerField()
    quantity_reserved = models.PositiveIntegerField(default=0)
    reorder_threshold = models.PositiveIntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.book.title} inventory"

class StewardContribution(models.Model):
    steward_user = models.ForeignKey(User, on_delete=models.CASCADE)

    contributor_name = models.CharField(max_length=120)
    contributor_city = models.CharField(max_length=120)

    amount_cents = models.PositiveIntegerField()

    message = models.CharField(max_length=255, blank=True, null=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.contributor_name} from {self.contributor_city}"

class Notification(models.Model):
    TYPE_CHOICES = [
        ("info", "Info"),
        ("order", "Order"),
        ("flag", "Flag"),
        ("warning", "Warning"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=30, choices=TYPE_CHOICES, default="info")

    title = models.CharField(max_length=120, blank=True, null=True)
    message = models.TextField()

    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification {self.id} to {self.user.email}"