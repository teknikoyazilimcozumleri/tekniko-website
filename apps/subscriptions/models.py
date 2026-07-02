import uuid

from django.conf import settings
from django.db import models


class SubscriptionPlan(models.Model):
    """Abonelik paketi tanımı. Iyzico'da product + pricing plan ile eşleşir."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="TRY")
    interval = models.CharField(max_length=20, default="MONTHLY")  # MONTHLY, YEARLY vb.
    iyzico_product_reference_code = models.CharField(max_length=100, blank=True, null=True)
    iyzico_pricing_plan_reference_code = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return f"{self.name} ({self.price} {self.currency}/{self.interval})"


class Subscription(models.Model):
    """Kullanıcının bir plana aboneliği."""

    class Status(models.TextChoices):
        PENDING = "pending", "Beklemede"
        ACTIVE = "active", "Aktif"
        CANCELLED = "cancelled", "İptal"
        PAST_DUE = "past_due", "Ödeme gecikmiş"
        FAILED = "failed", "Başarısız"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    iyzico_subscription_reference_code = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    subscription_checkout_token = models.CharField(max_length=500, blank=True, db_index=True)  # token from initialize, to match callback
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.plan.name} ({self.status})"
