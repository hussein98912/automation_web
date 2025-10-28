
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from ..models import ChatHistory
from rest_framework import status

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
    

