from django.core.validators import MaxValueValidator
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "admin")
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ("buyer", "Buyer"),
        ("seller", "Seller"),
        ("admin", "Admin"),
    ]

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    phone = models.CharField(max_length=50, blank=True, null=True)

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    seller_approved = models.BooleanField(default=False)
    seller_approved_at = models.DateTimeField(blank=True, null=True)

    steward_verified = models.BooleanField(default=False)
    steward_city = models.CharField(max_length=120, blank=True, null=True)
    steward_progress = models.PositiveSmallIntegerField(
        default=0,
        validators=[MaxValueValidator(100)],
    )
    
    # Set when a steward redeems a free book; next free after FREE_BOOK_COOLDOWN (see General.steward).
    last_free_book_redeemed_at = models.DateTimeField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Store credit issued when sellers confirm return receipt (cents).
    store_credit_cents = models.PositiveIntegerField(default=0)

    objects = UserManager()


    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    def __str__(self):
        return self.email

    @property
    def is_steward(self):
        """Templates use this for steward-only UI; backed by `steward_verified`."""
        return bool(self.steward_verified)

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

    @property
    def price_dollars(self):
        """Price in dollars for display (base_price_cents / 100)."""
        return self.base_price_cents / 100.0

    @property
    def stock_quantity(self):
        """Available quantity from inventory, or 0 if no inventory record."""
        try:
            return self.inventory.quantity_available
        except Inventory.DoesNotExist:
            return 0

class Inventory(models.Model):
    book = models.OneToOneField(Book, on_delete=models.CASCADE)

    quantity_available = models.PositiveIntegerField()
    quantity_reserved = models.PositiveIntegerField(default=0)
    reorder_threshold = models.PositiveIntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.book.title} inventory"


class StewardPool(models.Model):
    """
    Singleton (pk=1): balance from steward checkout contributions, used to fund steward free books.
    Initial balance: $1,000,000.00.
    """

    pool_cents = models.PositiveBigIntegerField(default=100_000_000)

    class Meta:
        verbose_name = "Steward contribution pool"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)


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
