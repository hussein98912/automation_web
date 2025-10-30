from django.db import models
from django.contrib.auth.models import AbstractUser,User
from django.db import models
from django.conf import settings
from .price import calculate_order_price

class CustomUser(AbstractUser):
    full_name = models.CharField(max_length=200)
    address = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(unique=True)

    REQUIRED_FIELDS = ["full_name", "email", "phone_number"]
    # username و password موجودة في AbstractUser
    def __str__(self):
        return self.username

# ===========================
#  تصنيف الخدمات (Category)
# ===========================
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

# ===========================
#  الخدمات (Service)
# ===========================
class Service(models.Model):
    icon = models.ImageField(upload_to="service_icons/", blank=True, null=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    features = models.JSONField(default=list, blank=True)
    #price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

# ===========================
# ===========================
class Project(models.Model):
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField()
    problem = models.TextField(blank=True, null=True)
    outcome = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=100)
    image = models.ImageField(upload_to="project_images/", blank=True, null=True)

    technologies = models.JSONField(default=list, blank=True)
    features = models.JSONField(default=list, blank=True)

    price = models.CharField(max_length=50, blank=True, null=True)  # "$2,499"
    timeline = models.CharField(max_length=100, blank=True, null=True)  # "2-3 weeks"
    complexity = models.CharField(max_length=50, blank=True, null=True)  # "Advanced"

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

# ===========================
#  الطلبات (Order)
# ===========================
class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("ready_for_payment", "Ready For Payment"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),       
    ]

    HOST_DURATION_CHOICES = [
        ("1_month", "1 month"),
        ("3_months", "3 months"),
        ("6_months", "6 months"),
        ("12_months", "12 months"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders"
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="orders"
    )
    workflow_name = models.CharField(max_length=200, blank=True)
    workflow_details = models.TextField(blank=True)
    attachment = models.FileField(upload_to='orders_attachments/', blank=True, null=True)
    
    host_duration = models.CharField(
        max_length=20,
        choices=HOST_DURATION_CHOICES,
        default="1_month",
        help_text="مدة الاستضافة للخدمة"
    )
    total_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    industry = models.CharField(max_length=50, blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Calculate total price from KB
        self.total_price = calculate_order_price(self.service.title, self.host_duration)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order #{self.id} - {self.user.username}"


# ===========================
#  الدفع (Payment)
# ===========================
class Payment(models.Model):
        STATUS_CHOICES = [
            ("pending", "Pending"),
            ("paid", "Paid"),
            ("failed", "Failed"),
        ]

        order = models.OneToOneField("Order", on_delete=models.CASCADE, related_name="payment")
        amount = models.DecimalField(max_digits=10, decimal_places=2)
        status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
        method = models.CharField(max_length=50, default="stripe")
        payment_date = models.DateTimeField(auto_now_add=True)
        transaction_id = models.CharField(max_length=255, blank=True, null=True)

        def __str__(self):
            return f"Payment for Order #{self.order.id}"



class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"Notification for {self.user.username}: {self.message}"




class ChatHistory(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    message = models.TextField()
    response = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_bot = models.BooleanField(default=False)



class Activity(models.Model):
    ACTION_CHOICES = [
        ("create_service", "Created a Service"),
        ("create_project", "Created a Project"),
        ("edit_order", "Edited an Order"),
    ]

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="activities"
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.action} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
