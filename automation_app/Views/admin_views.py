
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from ..models import ChatHistory,Activity
from rest_framework import status
from rest_framework import generics, permissions
from automation_app.serializers import ActivitySerializer

class AdminChatHistoryListAPIView(APIView):
    """
    Get all chat history for all users (Admin only).
    Requires admin privileges and JWT token.
    """
    permission_classes = [IsAdminUser]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        # Get all chat records ordered by most recent first
        chats = ChatHistory.objects.select_related('user').order_by('-timestamp')

        # Convert to JSON manually (you can use serializer instead)
        data = [
            {
                "id": chat.id,
                "username": chat.user.username if chat.user else None,
                "message": chat.message,
                "response": chat.response,
                "timestamp": chat.timestamp,
                "is_bot": chat.is_bot,
            }
            for chat in chats
        ]

        return Response(data, status=status.HTTP_200_OK)
    

class ActivityListCreateAPIView(generics.ListCreateAPIView):
    queryset = Activity.objects.all().order_by("-created_at")
    serializer_class = ActivitySerializer
    permission_classes = [permissions.IsAdminUser]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)