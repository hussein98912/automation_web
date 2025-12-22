from django.db import models
from django.contrib.auth.models import AbstractUser,User
from django.db import models
from django.conf import settings
from .price import calculate_order_price
import hashlib

class CustomUser(AbstractUser):
    full_name = models.CharField(max_length=200)
    address = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(unique=True)

    instagram_account_id = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        unique=True,
        help_text="Enter the Instagram Business/Creator Account ID"
    )

    facebook_page_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Facebook Page ID linked to this user"
    )
    instagram_access_token = models.TextField(
        blank=True,
        null=True,
        help_text="Access token for Instagram Graph API"
    )
    facebook_access_token = models.TextField(
        blank=True,
        null=True,
        help_text="Access token for Facebook Graph API"
    )

    REQUIRED_FIELDS = ["full_name", "email", "phone_number"]
    
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

    price = models.CharField(max_length=50, blank=True, null=True)  
    timeline = models.CharField(max_length=100, blank=True, null=True)  
    complexity = models.CharField(max_length=50, blank=True, null=True) 
    video = models.FileField(upload_to="project_videos/", blank=True, null=True)
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
        null=True,
        blank=True,
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
    project = models.ForeignKey(
    Project,
    on_delete=models.SET_NULL,
    null=True, blank=True,
    related_name="orders"
    )
def save(self, *args, **kwargs):
    if self.project:
        # Project order
        self.total_price = float(self.project.price or 0)
    elif self.service:
        # Service order
        self.total_price = calculate_order_price(self.service.title, self.host_duration)
    else:
        # Neither service nor project
        self.total_price = 0

    super().save(*args, **kwargs)



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
    payment_date = models.DateTimeField(null=True, blank=True)
    transaction_id = models.CharField(max_length=255, blank=True, null=True)

    def save(self, *args, **kwargs):
        # جلب الحالة القديمة إذا السطر موجود
        if self.pk:
            old_status = Payment.objects.get(pk=self.pk).status
        else:
            old_status = None

        # تغير الـ status إلى paid سواء من pending أو failed
        if old_status in ["pending", "failed"] and self.status == "paid":
            from django.utils import timezone
            self.payment_date = timezone.now()

        super().save(*args, **kwargs)

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
        ("update_service", "Updated a Service"),
        ("delete_service", "Deleted a Service"),
        ("create_project", "Created a Project"),
        ("update_project", "Updated a Project"),
        ("delete_project", "Deleted a Project"),
        ("edit_order", "Edited an Order"),
        ("delete_order", "Deleted an Order"),
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



class ContactMessage(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contact_messages",
        null=True,  # allow anonymous messages if needed
        blank=True
    )
    
    full_name = models.CharField(max_length=150)
    email = models.EmailField()
    company = models.CharField(max_length=150, blank=True, null=True)
    message = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message from {self.full_name}"
    

class InstagramMessage(models.Model):
    user = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='instagram_messages'
    )
    recipient_id = models.CharField(max_length=50) 
    sender_id = models.CharField(max_length=50)  # Instagram sender numeric ID
    sender_username = models.CharField(max_length=100, blank=True, null=True)
    message = models.TextField()                 # message received from sender
    reply = models.TextField(blank=True, null=True)  # reply sent to sender
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["recipient_id", "timestamp"]),
        ]
    def __str__(self):
        return f"Message from {self.sender_username or self.sender_id} to {self.user.username}"




class InstagramComment(models.Model):
    user = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='instagram_comments'
    )
    recipient_id = models.CharField(max_length=50) 
    sender_id = models.CharField(max_length=50)
    sender_username = models.CharField(max_length=100, blank=True, null=True)
    comment = models.TextField()                 # comment text
    reply = models.TextField(blank=True, null=True)  # reply to comment
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["recipient_id", "timestamp"]),
        ]
    def __str__(self):
        return f"Comment from {self.sender_username or self.sender_id} to {self.user.username}"



class FacebookMessage(models.Model):
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='facebook_messages'
    )
    sender_id = models.CharField(max_length=50)                    
    sender_name = models.CharField(max_length=100, blank=True, null=True)
    recipient_page_id = models.CharField(max_length=50)             
    message = models.TextField()                                    
    reply = models.TextField(blank=True, null=True)   
    timestamp = models.DateTimeField(auto_now_add=True)             

    class Meta:
        indexes = [
            models.Index(fields=["recipient_page_id", "timestamp"]),
        ]
    def __str__(self):
        return f"FB Message from {self.sender_name or self.sender_id} to page {self.recipient_page_id}"


class FacebookComment(models.Model):
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='facebook_comments'
    )
    recipient_id = models.CharField(max_length=100)                        
    sender_id = models.CharField(max_length=50)                       
    sender_name = models.CharField(max_length=100, blank=True, null=True)
    comment = models.TextField()                                     
    reply = models.TextField(blank=True, null=True)                   
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["recipient_id", "timestamp"]),
        ]
    def __str__(self):
        return f"FB Comment from {self.sender_name or self.sender_id} on post {self.post_id}"


class BusinessSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='ai_agents'   
    )
    name = models.CharField(max_length=150,null=True)
    business_type = models.CharField(max_length=100)
    business_description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    chat_history = models.JSONField(default=list)

    def __str__(self):
        return f"{self.business_type} session for {self.user.username if self.user else 'Anonymous'}"
    


# ai_agent/models.py
class BusinessSessionOrder(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending Review"),
        ("ready_for_payment", "Ready for Payment"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="business_session_orders"
    )

    session = models.ForeignKey(
        BusinessSession,
        on_delete=models.CASCADE,
        related_name="orders"
    )

    order_details = models.TextField(blank=True)

    # Admin will set this later
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="pending"
    )
    
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} for {self.session.name}"


class AgentAPIKey(models.Model):
    agent = models.ForeignKey(
        BusinessSession,
        on_delete=models.CASCADE,
        related_name="api_keys"
    )
    key_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    @staticmethod
    def hash_key(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode()).hexdigest()

    def __str__(self):
        return f"API key for agent {self.agent.id}"
    


class SDKChatSession(models.Model):
    api_key = models.ForeignKey(AgentAPIKey, on_delete=models.CASCADE)
    session_id = models.CharField(max_length=100)
    chat_history = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("api_key", "session_id")



class TelegramBot(models.Model):
    business_session = models.ForeignKey(
        BusinessSession,
        on_delete=models.CASCADE,
        related_name="telegram_bots"
    )
    bot_token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Telegram bot for session {self.business_session.id}"