from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated,AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth.models import User
from ..models import Notification,ChatHistory,Project, Order, CustomUser ,ContactMessage,InstagramMessage, InstagramComment
from ..serializers import NotificationSerializer, CustomUserSerializer,ContactMessageSerializer,UpdateProfileSerializer,ChangePasswordSerializer,InstagramStatsSerializer
from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view, permission_classes
from django.contrib.auth import update_session_auth_hash
from django.http import JsonResponse
from datetime import datetime, timedelta
import requests
from django.views import View

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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def instagram_stats(request):
    user = request.user

    if not user.instagram_account_id:
        return Response({"error": "User does not have an Instagram account ID."}, status=400)

    recipient_id = user.instagram_account_id

    # Count total messages received
    total_messages = InstagramMessage.objects.filter(recipient_id=recipient_id).count()

    # Count total comments received
    total_comments = InstagramComment.objects.filter(recipient_id=recipient_id).count()

    # Total conversations (unique senders from both messages and comments)
    message_senders = InstagramMessage.objects.filter(recipient_id=recipient_id).values_list('sender_id', flat=True)
    comment_senders = InstagramComment.objects.filter(recipient_id=recipient_id).values_list('sender_id', flat=True)

    unique_senders = set(list(message_senders) + list(comment_senders))
    total_conversations = len(unique_senders)

    data = {
        "total_messages": total_messages,
        "total_comments": total_comments,
        "total_conversations": total_conversations
    }

    serializer = InstagramStatsSerializer(data)
    return Response(serializer.data)


class FacebookInsightsView(APIView):
    permission_classes = [IsAuthenticated]  # any logged-in user (admin or regular)

    def get(self, request, instagram_account_id):
        # Use the logged-in user's token
        access_token = request.user.instagram_access_token
        if not access_token:
            return Response({"error": "Instagram access token missing"}, status=400)

        today = datetime.today().date()
        default_since = today - timedelta(days=28)
        since = request.GET.get("since", default_since.isoformat())
        until = request.GET.get("until", today.isoformat())

        url = f"https://graph.facebook.com/v23.0/{instagram_account_id}/insights"
        params = {
            "metric": "reach",
            "period": "day",
            "since": since,
            "until": until,
            "access_token": access_token
        }

        response = requests.get(url, params=params)
        if response.status_code == 200:
            return Response(response.json())
        else:
            return Response({
                "error": "Failed to fetch data",
                "status": response.status_code,
                "details": response.json()
            }, status=500)
        

class FacebookEngagementInsightsView(APIView):
    permission_classes = [IsAuthenticated]   # allow any logged-in user

    def get(self, request, instagram_account_id):
        # Get the user's saved access token
        access_token = request.user.instagram_access_token
        if not access_token:
            return Response({"error": "User has no Instagram access token"}, status=400)

        url = f"https://graph.facebook.com/v19.0/{instagram_account_id}/insights"

        params = {
            "metric": "likes,comments,shares,saves",
            "period": "day",
            "metric_type": "total_value",
            "access_token": access_token
        }

        response = requests.get(url, params=params)

        if response.status_code == 200:
            return Response(response.json())
        else:
            return Response({
                "error": "Failed to fetch insights",
                "status": response.status_code,
                "details": response.json()
            }, status=500)
        

class FacebookProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]  # users + admin

    def get(self, request, instagram_id):
        access_token = request.user.instagram_access_token
        
        if not access_token:
            return Response({"error": "User does not have an Instagram access token"}, status=400)

        url = f"https://graph.facebook.com/v23.0/{instagram_id}"
        params = {
            "fields": "username,profile_picture_url,followers_count,follows_count,media_count",
            "access_token": access_token
        }

        response = requests.get(url, params=params)
        return Response(response.json())



class InstagramMediaWithCommentsView(APIView):
    permission_classes = [permissions.IsAuthenticated]  # allow admin + users

    def get(self, request, instagram_id):
        # Get the user token
        access_token = request.user.instagram_access_token
        if not access_token:
            return Response({"error": "User has no Instagram access token"}, status=400)

        # Facebook API media URL
        fb_url = f"https://graph.facebook.com/v23.0/{instagram_id}/media"
        params = {
            "fields": "id,media_type,media_url,thumbnail_url,permalink,timestamp,caption,like_count,comments_count",
            "access_token": access_token,
            "limit": 10
        }

        # Call META API
        fb_response = requests.get(fb_url, params=params)
        fb_data = fb_response.json()

        # Get last 5 comments for this IG account
        last_comments = InstagramComment.objects.filter(
            recipient_id=instagram_id
        ).order_by("-timestamp")[:5]

        serialized_comments = [
            {
                "sender_id": c.sender_id,
                "sender_username": c.sender_username,
                "comment": c.comment,
                "reply": c.reply,
                "timestamp": c.timestamp
            }
            for c in last_comments
        ]

        # Combine result
        result = {
            "media": fb_data,          # from META Graph API
            "last_5_comments": serialized_comments  # from DB
        }

        return Response(result)