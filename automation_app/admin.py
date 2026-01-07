from django.contrib import admin
from .models import CustomUser, Category, Service, Order, Payment,Plan

admin.site.register(CustomUser)
admin.site.register(Category)
admin.site.register(Service)
admin.site.register(Order)
admin.site.register(Payment)
@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price",
        "max_messages",
        "model_name",
        "allow_sdk",
        "allow_telegram",
        "stripe_price_id",
    )
    list_filter = (
        "allow_sdk",
        "allow_telegram",
    )
    search_fields = ("name", "stripe_price_id")
    ordering = ("price",)
    readonly_fields = ()
    fieldsets = (
        ("Basic Info", {"fields": ("name", "price", "is_active")}),
        ("Usage Limits", {"fields": ("max_messages", "max_tokens", "model_name")}),
        ("Access", {"fields": ("allow_sdk", "allow_telegram")}),
        ("Stripe", {"fields": ("stripe_price_id",)}),
    )