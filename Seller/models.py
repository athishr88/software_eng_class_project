from django.db import models
from General.models import User


class SellerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    store_name = models.CharField(max_length=120, blank=True, null=True)
    is_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"SellerProfile: {self.user.email}"