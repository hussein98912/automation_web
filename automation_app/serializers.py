from rest_framework import serializers
from .models import Category, Service, Order,Project,CustomUser,Notification,Payment,Activity
from .price import calculate_order_price
from rest_framework.serializers import ModelSerializer
from .models import ContactMessage,InstagramMessage, InstagramComment
from django.contrib.auth import get_user_model

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']

class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = "__all__"

class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = "__all__"
        read_only_fields = ['id']



class OrderSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    # Accept IDs when creating orders
    service_id = serializers.IntegerField(write_only=True, required=False)
    project_id = serializers.IntegerField(write_only=True, required=False)

    # Read-only nested objects
    service = ServiceSerializer(read_only=True)
    project = ProjectSerializer(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "user_name",
            "service",       # returned nested
            "service_id",    # accepted as input
            "project",
            "project_id",
            "industry",
            "host_duration",
            "workflow_name",
            "workflow_details",
            "total_price",
            "status",
            "created_at",
        ]
        read_only_fields = ["total_price", "status", "created_at"]

    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    def validate(self, attrs):
        # Make project/service objects
        service_id = attrs.pop("service_id", None)
        project_id = attrs.pop("project_id", None)

        if project_id:
            from automation_app.models import Project
            attrs["project"] = Project.objects.get(id=project_id)

        if service_id:
            from automation_app.models import Service
            attrs["service"] = Service.objects.get(id=service_id)

        return attrs

class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            'id',
            'username',
            'full_name',
            'email',
            'address',
            'phone_number',
            'is_active',
            'is_superuser',
            'date_joined'
        ]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'message', 'created_at', 'is_read']


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"



class ActivitySerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Activity
        fields = ["id", "user", "user_name", "action", "description", "created_at"]
        read_only_fields = ["id", "created_at","user"]


class TransactionSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source="order.service.title", read_only=True)
    order_status = serializers.CharField(source="order.status", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "order",
            "service_name",
            "amount",
            "status",
            "payment_date",
            "order_status",
        ]

class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ["id", "user", "full_name", "email", "company", "message", "created_at"]
        read_only_fields = ["user", "created_at"]



User = get_user_model()

class UpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["full_name","address", "phone_number","email"]




class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
    confirm_password = serializers.CharField(required=True)

    def validate(self, data):
        if data["new_password"] != data["confirm_password"]:
            raise serializers.ValidationError("New password and confirm password do not match.")
        return data
    

class InstagramIDUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['instagram_account_id', 'instagram_access_token']


class InstagramMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstagramMessage
        fields = ['id', 'user', 'recipient_id', 'sender_id', 'sender_username', 'message', 'reply', 'timestamp']
        read_only_fields = ['id', 'timestamp', 'user']

class InstagramCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstagramComment
        fields = ['id', 'user', 'recipient_id', 'sender_id', 'sender_username', 'comment', 'reply', 'timestamp']
        read_only_fields = ['id', 'timestamp', 'user']


class InstagramStatsSerializer(serializers.Serializer):
    total_messages = serializers.IntegerField()
    total_comments = serializers.IntegerField()
    total_conversations = serializers.IntegerField()