from django.contrib import admin
from .models import CustomUser, Category, Service, Order, Payment,Plan

admin.site.register(CustomUser)
admin.site.register(Category)
admin.site.register(Service)
admin.site.register(Order)
admin.site.register(Payment)
@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "max_messages", "max_tokens", "model_name")