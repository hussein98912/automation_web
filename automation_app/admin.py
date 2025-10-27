from django.contrib import admin
from .models import CustomUser, Category, Service, Order, Payment

admin.site.register(CustomUser)
admin.site.register(Category)
admin.site.register(Service)
admin.site.register(Order)
admin.site.register(Payment)
