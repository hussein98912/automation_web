from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated,AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth.models import User
from ..models import Notification,ChatHistory,Project, Order, CustomUser ,ContactMessage,InstagramMessage, InstagramComment,FacebookComment,FacebookMessage,BusinessSession
from ..serializers import NotificationSerializer, CustomUserSerializer,ContactMessageSerializer,UpdateProfileSerializer,ChangePasswordSerializer,InstagramStatsSerializer,FacebookStatsSerializer,BusinessSessionUpdateSerializer
from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view, permission_classes
from django.contrib.auth import update_session_auth_hash
from django.http import JsonResponse
from datetime import datetime, timedelta
import requests
from django.shortcuts import get_object_or_404
from django.views import View
from datetime import datetime, time
from ..utils import get_month_range,gpt_classify_text
from collections import Counter

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
    permission_classes = [IsAuthenticated]

    def get(self, request, instagram_account_id):
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
            fb_data = response.json()

            # Keep ONLY the insights data, remove paging
            cleaned = {
                "data": fb_data.get("data", [])
            }

            return Response(cleaned)

        else:
            return Response({
                "error": "Failed to fetch data",
                "status": response.status_code,
                "details": response.json()
            }, status=500)
        

class FacebookEngagementInsightsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, instagram_account_id):
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
            data = response.json()

            # Return only the "data" array, remove paging
            cleaned = {
                "data": data.get("data", [])
            }

            return Response(cleaned)

        else:
            return Response({
                "error": "Failed to fetch insights",
                "status": response.status_code,
                "details": response.json()
            }, status=500)
        

class instagramProfileView(APIView):
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
    permission_classes = [permissions.IsAuthenticated]

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

        # Keep ONLY media items, remove paging
        cleaned_media = fb_data.get("data", [])

        # Get last 5 comments from DB
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

        # Final response
        result = {
            "media": cleaned_media,           # removed paging
            "last_5_comments": serialized_comments
        }

        return Response(result)
    


    




class FacebookPageProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, page_id):
        # Use whichever token you store (page access token or generic token with page rights)
        access_token = request.user.instagram_access_token  # or request.user.instagram_access_token if you reuse that
        if not access_token:
            return Response({"error": "User does not have a Facebook Page access token"}, status=400)

        url = f"https://graph.facebook.com/v24.0/{page_id}"
        params = {
            "fields": "id,name,link,category,picture,fan_count,about,followers_count",
            "access_token": access_token
        }

        response = requests.get(url, params=params)
        return Response(response.json())
    
class FacebookPostsWithCommentsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, page_id):
        # Get the user token
        access_token = request.user.facebook_access_token
        if not access_token:
            return Response({"error": "User has no Facebook Page access token"}, status=400)

        fb_url = f"https://graph.facebook.com/v24.0/{page_id}/posts"
        params = {
            "fields": "id,message,created_time,attachments{media},permalink_url,shares,likes.summary(true),comments.summary(true)",
            "access_token": access_token,
            "limit": 10
        }

        fb_response = requests.get(fb_url, params=params)
        fb_data = fb_response.json()

        raw_posts = fb_data.get("data", [])

        cleaned_posts = []

        for post in raw_posts:
            # Remove paging inside likes
            if "likes" in post:
                post["likes"].pop("paging", None)

            # Remove paging inside comments
            if "comments" in post:
                post["comments"].pop("paging", None)

            cleaned_posts.append(post)

        # Last 5 comments from DB
        last_comments = FacebookComment.objects.filter(
            recipient_id=page_id
        ).order_by("-timestamp")[:5]

        serialized_comments = [
            {
                "sender_id": c.sender_id,
                "sender_name": c.sender_name,
                "comment": c.comment,
                "reply": c.reply,
                "timestamp": c.timestamp
            }
            for c in last_comments
        ]

        return Response({
            "posts": cleaned_posts,
            "last_5_comments": serialized_comments
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def facebook_stats(request):
    user = request.user

    if not user.facebook_page_id:
        return Response({"error": "User does not have a Facebook Page ID."}, status=400)

    page_id = user.facebook_page_id

    # Count total messages received
    total_messages = FacebookMessage.objects.filter(recipient_page_id=page_id).count()

    # Count total comments received
    total_comments = FacebookComment.objects.filter(recipient_id=page_id).count()

    # Total conversations (unique senders from both messages and comments)
    message_senders = FacebookMessage.objects.filter(recipient_page_id=page_id).values_list('sender_id', flat=True)
    comment_senders = FacebookComment.objects.filter(recipient_id=page_id).values_list('sender_id', flat=True)

    unique_senders = set(list(message_senders) + list(comment_senders))
    total_conversations = len(unique_senders)

    data = {
        "total_messages": total_messages,
        "total_comments": total_comments,
        "total_conversations": total_conversations
    }

    # You can reuse the same serializer or create a new one for Facebook stats
    serializer = FacebookStatsSerializer(data)  # rename if needed
    return Response(serializer.data)


class FacebookPageInsightsMetricView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, page_id):
        user = request.user

        access_token = user.facebook_access_token  
        if not access_token:
            return Response({"error": "Facebook access token missing"}, status=400)

        metric = request.GET.get("metric", "page_impressions_unique")
        since = request.GET.get("since")
        until = request.GET.get("until")

        if not since or not until:
            today = datetime.today().date()
            since = (today - timedelta(days=7)).isoformat()
            until = today.isoformat()

        url = f"https://graph.facebook.com/v19.0/{page_id}/insights/{metric}"
        params = {
            "access_token": access_token,
            "period": "day",
            "since": since,
            "until": until,
        }

        fb_response = requests.get(url, params=params)
        data = fb_response.json()

        if "error" in data:
            return Response({"error": "Facebook API error", "details": data}, status=400)

        # 🔥 REMOVE PAGING IF EXISTS
        if "paging" in data:
            del data["paging"]

        return Response(data)
    


class FacebookPageInsightsMultiMetricView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, page_id):
        user = request.user

        access_token = user.facebook_access_token  
        if not access_token:
            return Response({"error": "Facebook access token missing"}, status=400)

        # get metrics list from URL
        metrics = request.GET.get("metric")
        if not metrics:
            return Response({"error": "Metric parameter is required"}, status=400)

        url = f"https://graph.facebook.com/v24.0/{page_id}/insights"

        params = {
            "metric": metrics,
            "access_token": access_token,
        }

        fb_response = requests.get(url, params=params)
        data = fb_response.json()

        if "error" in data:
            return Response({"error": "Facebook API error", "details": data}, status=400)

        # remove paging if exists
        if "paging" in data:
            del data["paging"]

        return Response(data)

#instagram analysis -------------------------------------------------------------------------------------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def instagram_monthly_report(request):
    user = request.user

    if not user.instagram_account_id:
        return Response({"error": "Instagram account not connected"}, status=400)

    year = request.GET.get("year")
    month = request.GET.get("month")

    start_date, end_date = get_month_range(year, month)
    instagram_id = user.instagram_account_id

    # Use datetime range for timezone-safe filtering
    start_datetime = datetime.combine(start_date, time.min)
    end_datetime = datetime.combine(end_date, time.max)

    messages = InstagramMessage.objects.filter(
        recipient_id=instagram_id,
        timestamp__range=(start_datetime, end_datetime)
    )

    comments = InstagramComment.objects.filter(
        recipient_id=instagram_id,
        timestamp__range=(start_datetime, end_datetime)
    )

    unique_senders = set(
        list(messages.values_list("sender_id", flat=True)) +
        list(comments.values_list("sender_id", flat=True))
    )

    days = (end_date - start_date).days + 1

    return Response({
        "period": f"{start_date.strftime('%Y-%m')}",
        "messages": {
            "total": messages.count(),
            "daily_avg": round(messages.count() / days, 2)
        },
        "comments": {
            "total": comments.count(),
            "daily_avg": round(comments.count() / days, 2)
        },
        "conversations": len(unique_senders)
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def instagram_best_worst_posts(request):
    user = request.user

    year = request.GET.get("year")
    month = request.GET.get("month")

    start_date, end_date = get_month_range(year, month)

    instagram_id = user.instagram_account_id
    access_token = user.instagram_access_token

    url = f"https://graph.facebook.com/v23.0/{instagram_id}/media"
    params = {
        "fields": "id,permalink,timestamp,like_count,comments_count",
        "access_token": access_token,
        "limit": 50
    }

    data = requests.get(url, params=params).json().get("data", [])

    posts = []
    for post in data:
        post_date = datetime.fromisoformat(post["timestamp"]).date()
        if start_date <= post_date <= end_date:
            likes = post.get("like_count", 0)
            comments = post.get("comments_count", 0)
            post["engagement"] = likes + comments
            posts.append(post)

    if not posts:
        return Response({"message": "No posts in this month"})

    best_post = max(posts, key=lambda x: x["engagement"])
    worst_post = min(posts, key=lambda x: x["engagement"])

    return Response({
        "period": f"{start_date.strftime('%Y-%m')}",
        "best_post": {
            "permalink": best_post["permalink"],
            "likes": best_post["like_count"],
            "comments": best_post["comments_count"],
            "engagement": best_post["engagement"]
        },
        "worst_post": {
            "permalink": worst_post["permalink"],
            "likes": worst_post["like_count"],
            "comments": worst_post["comments_count"],
            "engagement": worst_post["engagement"]
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def instagram_complaints_and_reviews(request):
    user = request.user

    year = request.GET.get("year")
    month = request.GET.get("month")

    start_date, end_date = get_month_range(year, month)
    instagram_id = user.instagram_account_id

    messages = InstagramMessage.objects.filter(
        recipient_id=instagram_id,
        timestamp__date__range=(start_date, end_date)
    )

    comments = InstagramComment.objects.filter(
        recipient_id=instagram_id,
        timestamp__date__range=(start_date, end_date)
    )

    complaints = []
    sentiment_count = {"Positive": 0, "Neutral": 0, "Negative": 0}

    # Combine messages and comments
    for obj in list(messages) + list(comments):
        text = getattr(obj, "message", None) or obj.comment

        # GPT classification
        sentiment = gpt_classify_text(text, task="sentiment")
        complaint = gpt_classify_text(text, task="complaint")

        # Count sentiment
        if sentiment in sentiment_count:
            sentiment_count[sentiment] += 1

        # Collect complaints
        if complaint == "Yes":
            complaints.append(text)

    top_complaints = Counter(complaints).most_common(5)

    return Response({
        "period": f"{start_date.strftime('%Y-%m')}",
        "top_complaints": [{"topic": k, "count": v} for k, v in top_complaints],
        "reviews": sentiment_count
    })


# FACEBOOK ANALYSIS -----------------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def facebook_monthly_report(request):
    user = request.user

    page_id = user.facebook_page_id
    if not page_id:
        return Response({"error": "Facebook page not connected"}, status=400)

    year = request.GET.get("year")
    month = request.GET.get("month")

    start_date, end_date = get_month_range(year, month)
    start_datetime = datetime.combine(start_date, time.min)
    end_datetime = datetime.combine(end_date, time.max)

    messages = FacebookMessage.objects.filter(
        recipient_page_id=page_id,
        timestamp__range=(start_datetime, end_datetime)
    )

    comments = FacebookComment.objects.filter(
        recipient_id=page_id,
        timestamp__range=(start_datetime, end_datetime)
    )

    unique_senders = set(
        list(messages.values_list("sender_id", flat=True)) +
        list(comments.values_list("sender_id", flat=True))
    )

    days = (end_date - start_date).days + 1

    return Response({
        "period": f"{start_date.strftime('%Y-%m')}",
        "messages": {
            "total": messages.count(),
            "daily_avg": round(messages.count() / days, 2)
        },
        "comments": {
            "total": comments.count(),
            "daily_avg": round(comments.count() / days, 2)
        },
        "conversations": len(unique_senders)
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def facebook_best_worst_posts(request):
    user = request.user
    page_id = user.facebook_page_id
    access_token = user.facebook_access_token

    if not page_id or not access_token:
        return Response({"error": "Facebook page or access token missing"}, status=400)

    year = request.GET.get("year")
    month = request.GET.get("month")
    start_date, end_date = get_month_range(year, month)

    url = f"https://graph.facebook.com/v24.0/{page_id}/posts"
    params = {
        "fields": "id,message,created_time,permalink_url,shares,likes.summary(true),comments.summary(true)",
        "access_token": access_token,
        "limit": 50
    }

    data = requests.get(url, params=params).json().get("data", [])

    posts = []
    for post in data:
        post_date = datetime.fromisoformat(post["created_time"].replace("Z", "+00:00")).date()
        if start_date <= post_date <= end_date:
            likes = post.get("likes", {}).get("summary", {}).get("total_count", 0)
            comments_count = post.get("comments", {}).get("summary", {}).get("total_count", 0)
            post["engagement"] = likes + comments_count
            post["likes"] = likes
            post["comments_count"] = comments_count
            posts.append(post)

    if not posts:
        return Response({"message": "No posts in this month"})

    best_post = max(posts, key=lambda x: x["engagement"])
    worst_post = min(posts, key=lambda x: x["engagement"])

    return Response({
        "period": f"{start_date.strftime('%Y-%m')}",
        "best_post": {
            "permalink": best_post["permalink_url"],
            "likes": best_post["likes"],
            "comments": best_post["comments_count"],
            "engagement": best_post["engagement"]
        },
        "worst_post": {
            "permalink": worst_post["permalink_url"],
            "likes": worst_post["likes"],
            "comments": worst_post["comments_count"],
            "engagement": worst_post["engagement"]
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def facebook_complaints_and_reviews(request):
    user = request.user
    page_id = user.facebook_page_id

    if not page_id:
        return Response({"error": "Facebook page not connected"}, status=400)

    year = request.GET.get("year")
    month = request.GET.get("month")
    start_date, end_date = get_month_range(year, month)

    messages = FacebookMessage.objects.filter(
        recipient_page_id=page_id,
        timestamp__date__range=(start_date, end_date)
    )

    comments = FacebookComment.objects.filter(
        recipient_id=page_id,
        timestamp__date__range=(start_date, end_date)
    )

    complaints = []
    sentiment_count = {"Positive": 0, "Neutral": 0, "Negative": 0}

    for obj in list(messages) + list(comments):
        text = getattr(obj, "message", None) or getattr(obj, "comment", "")

        sentiment = gpt_classify_text(text, task="sentiment")
        complaint = gpt_classify_text(text, task="complaint")

        if sentiment in sentiment_count:
            sentiment_count[sentiment] += 1

        if complaint == "Yes":
            complaints.append(text)

    top_complaints = Counter(complaints).most_common(5)

    return Response({
        "period": f"{start_date.strftime('%Y-%m')}",
        "top_complaints": [{"topic": k, "count": v} for k, v in top_complaints],
        "reviews": sentiment_count
    })


N8N_AVAILABILITY_URL = "https://n8n.urbatech.io/webhook/b9745a63-953f-41da-8e97-750caa30571e/get-availability"
N8N_AUTH_TOKEN = "f6b5bed0-c896-484b-b610-b6ef3f72b893"


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_available_time_slots(request):

    headers = {
        "Authorization": N8N_AUTH_TOKEN
    }

    try:
        response = requests.get(
            N8N_AVAILABILITY_URL,
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
    except requests.exceptions.RequestException:
        return Response(
            {"error": "Failed to fetch availability"},
            status=status.HTTP_502_BAD_GATEWAY
        )

    data = response.json()

    if isinstance(data, list):
        available_slots = data
    elif isinstance(data, dict):
        available_slots = data.get("available_slots", [])
    else:
        available_slots = []

    return Response(
        {"available_slots": available_slots},
        status=status.HTTP_200_OK
    )


N8N_CREATE_MEETING_URL = "https://n8n.urbatech.io/webhook/2a216d4f-4843-485a-a8ae-10901a9b81f0/create-meeting"
N8N_AUTH_TOKEN = "f6b5bed0-c896-484b-b610-b6ef3f72b893"



@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_meeting(request):
    user = request.user

    # 1. Email comes ONLY from token
    if not user.email:
        return Response(
            {"error": "User email not found"},
            status=status.HTTP_400_BAD_REQUEST
        )

    customer_email = user.email

    # 2. Data from frontend
    meeting_start_time = request.data.get("meeting_start_time")
    user_time_zone = request.data.get("user_time_zone")

    if not meeting_start_time or not user_time_zone:
        return Response(
            {"error": "meeting_start_time and user_time_zone are required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # 3. Payload for n8n
    payload = {
        "customer_email": customer_email,
        "meeting_start_time": meeting_start_time,
        "user_time_zone": user_time_zone
    }

    # 4. Call n8n
    try:
        response = requests.post(
            N8N_CREATE_MEETING_URL,
            json=payload,
            headers={
                "Authorization": N8N_AUTH_TOKEN,
                "Content-Type": "application/json"
            },
            timeout=15
        )
    except requests.RequestException as e:
        return Response(
            {"error": "Failed to connect to meeting service"},
            status=status.HTTP_502_BAD_GATEWAY
        )

    # 5. Handle n8n response
    if response.status_code not in [200, 201]:
        return Response(
            {
                "error": "Meeting creation failed",
                "details": response.text
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    return Response(
        {
            "message": "Meeting created successfully",
            "data": response.json()
        },
        status=status.HTTP_201_CREATED
    )


class BusinessSessionUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, session_id):
        session = get_object_or_404(
            BusinessSession,
            id=session_id,
            user=request.user
        )

        serializer = BusinessSessionUpdateSerializer(
            session,
            data=request.data
        )

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer.save()

        return Response(
            {
                "message": "Business session updated successfully",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )