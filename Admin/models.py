from django.db import models
from General.models import User, Book


class FlagReport(models.Model):
    STATUS_CHOICES = [
        ("open", "Open"),
        ("reviewing", "Reviewing"),
        ("resolved", "Resolved"),
        ("dismissed", "Dismissed"),
    ]

    reporter_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="flags_made")

    target_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="flags_received",
    )

    target_book = models.ForeignKey(
        Book,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="flags_on_books",
    )

    flag_type = models.CharField(max_length=80)
    details = models.TextField(blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"FlagReport {self.id} {self.status}"