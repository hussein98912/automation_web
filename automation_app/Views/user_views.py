from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated,AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth.models import User
from ..models import Notification,ChatHistory,Project, Order, CustomUser ,ContactMessage
from ..serializers import NotificationSerializer, CustomUserSerializer,ContactMessageSerializer,UpdateProfileSerializer,ChangePasswordSerializer
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


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def send_message(request):
    serializer = ContactMessageSerializer(data=request.data)
    
    if serializer.is_valid():
        serializer.save(user=request.user)  # attach user here
        return Response(
            {"message": "Your message has been sent successfully."},
            status=status.HTTP_201_CREATED
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_my_messages(request):
    messages = ContactMessage.objects.filter(user=request.user).order_by("-created_at")
    serializer = ContactMessageSerializer(messages, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_message(request, message_id):
    try:
        message = ContactMessage.objects.get(id=message_id, user=request.user)
    except ContactMessage.DoesNotExist:
        return Response({"error": "Message not found"}, status=404)

    serializer = ContactMessageSerializer(message)
    return Response(serializer.data)



@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_profile(request):
    user = request.user
    serializer = UpdateProfileSerializer(user, data=request.data, partial=True)

    if serializer.is_valid():
        serializer.save()
        return Response({"message": "Profile updated successfully"}, status=200)

    return Response(serializer.errors, status=400)




@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def change_password(request):
    serializer = ChangePasswordSerializer(data=request.data)

    if serializer.is_valid():
        user = request.user

        # Check old password
        if not user.check_password(serializer.validated_data["old_password"]):
            return Response({"error": "Old password is incorrect"}, status=status.HTTP_400_BAD_REQUEST)

        # Set new password
        user.set_password(serializer.validated_data["new_password"])
        user.save()

        # Keep the user logged in after password change
        update_session_auth_hash(request, user)

        return Response(
            {"message": "Password changed successfully"},
            status=status.HTTP_200_OK
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)