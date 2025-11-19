from rest_framework import serializers
from .models import Category, Service, Order,Project,CustomUser,Notification,Payment,Activity
from .price import calculate_order_price
from rest_framework.serializers import ModelSerializer


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
    service = ServiceSerializer(read_only=True)
    project = ProjectSerializer(read_only=True) 
    class Meta:
        model = Order
        fields = [
            'id',
            'user_name',
            'service',
            'project',
            'industry',
            'host_duration',
            'workflow_name',
            'workflow_details',
            'total_price',
            'status',
            'created_at',
        ]
        read_only_fields = ['total_price','status','created_at']
        
    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

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