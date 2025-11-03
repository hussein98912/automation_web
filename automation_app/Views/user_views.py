from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated,AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth.models import User
from ..models import Notification,ChatHistory,Project, Order, CustomUser
from ..serializers import NotificationSerializer, CustomUserSerializer
from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view, permission_classes



User = get_user_model()


class UserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [AllowAny]




class UserNotificationListAPIView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only return notifications for the user from the token
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')
    

class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]  # Requires valid access token

    def get(self, request):
        user = request.user  # Automatically set by JWTAuthentication
        serializer = CustomUserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class ChatHistoryListAPIView(APIView):
    """
    Get all chat history for the authenticated user.
    Requires JWT token in Authorization header.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        # Filter chats by authenticated user ID
        user_id = str(request.user.id)
        chats = ChatHistory.objects.filter(user_id=user_id).order_by('-timestamp')

        # Convert to JSON manually (or use a serializer if preferred)
        data = [
            {
                "id": chat.id,
                "message": chat.message,
                "response": chat.response,
                "timestamp": chat.timestamp,
                "is_bot": chat.is_bot
            }
            for chat in chats
        ]

        return Response(data, status=status.HTTP_200_OK)
    

@api_view(["GET"])
@permission_classes([IsAuthenticated])   # remove if you want it public
def dashboard_stats(request):

    total_projects = Project.objects.count()
    active_users = CustomUser.objects.filter(is_active=True).count()

    active_orders = Order.objects.filter(
        status__in=["in_progress", "ready_for_payment"]
    ).count()

    pending_orders = Order.objects.filter(status="pending").count()

    return Response({
        "total_projects": total_projects,
        "active_users": active_users,
        "active_orders": active_orders,
        "pending_orders": pending_orders
    })