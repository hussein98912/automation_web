from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated,AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth.models import User
from ..models import Notification,ChatHistory
from ..serializers import NotificationSerializer, CustomUserSerializer
from django.contrib.auth import get_user_model

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