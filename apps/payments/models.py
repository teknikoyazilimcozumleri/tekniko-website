import uuid

from django.conf import settings
from django.db import models


class Payment(models.Model):
    """
    Single payment record for Iyzico Checkout Form flow.
    Tracks: which payment, which stage, and how it maps to Iyzico.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="TRY")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    iyzico_payment_id = models.CharField(max_length=100, blank=True, db_index=True)
    iyzico_token = models.CharField(max_length=500, blank=True)
    conversation_id = models.CharField(max_length=100, unique=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    return_url = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment {self.id} ({self.status})"
