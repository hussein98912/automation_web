from rest_framework import serializers
from .models import Category, Service, Order,Project,ChatHistory,CustomUser,Notification
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

class ChatHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatHistory
        fields = "__all__"

class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            'id',
            'service',
            'industry',
            'host_duration',
            'workflow_name',
            'workflow_details',
            'total_price',
            'status',
            'created_at',
        ]
        read_only_fields = ['total_price','status','created_at']

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
