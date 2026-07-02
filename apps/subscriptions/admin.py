from django.contrib import admin
from .models import Subscription, SubscriptionPlan


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "price", "currency", "interval", "is_active", "sort_order")
    list_filter = ("is_active", "currency", "interval")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "plan", "status", "current_period_end", "created_at")
    list_filter = ("status", "plan")
    search_fields = ("iyzico_subscription_reference_code", "user__username")
    readonly_fields = ("id", "created_at", "updated_at")
