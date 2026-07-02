from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "amount", "currency", "status", "created_at")
    list_filter = ("status", "currency")
    search_fields = ("conversation_id", "iyzico_payment_id", "iyzico_token")
    readonly_fields = ("id", "created_at", "updated_at")
