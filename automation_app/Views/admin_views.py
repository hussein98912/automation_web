
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from ..models import ChatHistory,Activity,CustomUser, InstagramMessage, InstagramComment,FacebookMessage,FacebookComment
from ..serializers import InstagramMessageSerializer, InstagramCommentSerializer,FacebookMessageSerializer,FacebookCommentSerializer
from rest_framework import status
from rest_framework import generics, permissions
from automation_app.serializers import ActivitySerializer,InstagramIDUpdateSerializer,AdminUpdateSocialSerializer
from rest_framework.authentication import SessionAuthentication
from rest_framework.authentication import TokenAuthentication

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



class UpdateInstagramIDView(APIView):
    permission_classes = [permissions.IsAdminUser]  # only admin can update

    def post(self, request, user_id):
        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = InstagramIDUpdateSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Instagram ID, Instagram access token, and Facebook Page ID updated successfully"})
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        

# --- Messages ---
class InstagramMessageView(APIView):
    permission_classes = []

    # POST: Save message
    def post(self, request):
        recipient_id = request.data.get('recipient_id')
        sender_id = request.data.get('sender_id')
        sender_username = request.data.get('sender_username')
        message_text = request.data.get('message')
        reply_text = request.data.get('reply', None)

        # Find the user by recipient_id
        try:
            user = CustomUser.objects.get(instagram_account_id=recipient_id)
        except CustomUser.DoesNotExist:
            user = None  # or return error if preferred

        msg = InstagramMessage.objects.create(
            user=user,  # assign the user here
            recipient_id=recipient_id,
            sender_id=sender_id,
            sender_username=sender_username,
            message=message_text,
            reply=reply_text
        )

        serializer = InstagramMessageSerializer(msg)
        return Response({"message": "Message saved", "data": serializer.data}, status=status.HTTP_201_CREATED)

    # GET: Retrieve all messages for a recipient
    def get(self, request, recipient_id):
        messages = InstagramMessage.objects.filter(recipient_id=recipient_id).order_by('-timestamp')
        serializer = InstagramMessageSerializer(messages, many=True)
        return Response(serializer.data)




# --- Comments ---
class InstagramCommentView(APIView):
    permission_classes = []

    def post(self, request):
        recipient_id = request.data.get('recipient_id')
        sender_id = request.data.get('sender_id')
        sender_username = request.data.get('sender_username')
        comment_text = request.data.get('comment')
        reply_text = request.data.get('reply', None)

        # Try to find the user by recipient_id
        try:
            user = CustomUser.objects.get(instagram_account_id=recipient_id)
        except CustomUser.DoesNotExist:
            user = None  # optional: you can return an error if you prefer

        comment = InstagramComment.objects.create(
            user=user,  # assign the user here
            recipient_id=recipient_id,
            sender_id=sender_id,
            sender_username=sender_username,
            comment=comment_text,
            reply=reply_text
        )

        serializer = InstagramCommentSerializer(comment)
        return Response(
            {"message": "Comment saved", "data": serializer.data},
            status=status.HTTP_201_CREATED
        )




# --- Facebook Messages ---
class FacebookMessageView(APIView):
    permission_classes = []

    # POST: Save message
    def post(self, request):
        recipient_page_id = request.data.get('recipient_page_id')
        sender_id = request.data.get('sender_id')
        sender_name = request.data.get('sender_name')
        message_text = request.data.get('message')
        reply_text = request.data.get('reply', None)

        # Automatically get the user by recipient_page_id
        try:
            user = CustomUser.objects.get(facebook_page_id=recipient_page_id)
        except CustomUser.DoesNotExist:
            user = None

        msg = FacebookMessage.objects.create(
            user=user,
            sender_id=sender_id,
            sender_name=sender_name,
            recipient_page_id=recipient_page_id,
            message=message_text,
            reply=reply_text
        )

        serializer = FacebookMessageSerializer(msg)
        return Response({"message": "Message saved", "data": serializer.data}, status=status.HTTP_201_CREATED)

    # GET: Retrieve all messages for a recipient page
    def get(self, request, recipient_page_id):
        messages = FacebookMessage.objects.filter(recipient_page_id=recipient_page_id).order_by('-id')
        serializer = FacebookMessageSerializer(messages, many=True)
        return Response(serializer.data)


# --- Facebook Comments ---
class FacebookCommentView(APIView):
    permission_classes = []

    # POST: Save comment
    def post(self, request):
        recipient_id = request.data.get('recipient_id')
        sender_id = request.data.get('sender_id')
        sender_name = request.data.get('sender_name')
        comment_text = request.data.get('comment')
        reply_text = request.data.get('reply', None)

        # Automatically get the user by recipient_id
        try:
            user = CustomUser.objects.get(facebook_page_id=recipient_id)
        except CustomUser.DoesNotExist:
            user = None

        comment = FacebookComment.objects.create(
            user=user,
            recipient_id=recipient_id,
            sender_id=sender_id,
            sender_name=sender_name,
            comment=comment_text,
            reply=reply_text
        )

        serializer = FacebookCommentSerializer(comment)
        return Response({"message": "Comment saved", "data": serializer.data}, status=status.HTTP_201_CREATED)

    # GET: Retrieve all comments for a post
    def get(self, request, post_id):
        comments = FacebookComment.objects.filter(post_id=post_id).order_by('-timestamp')
        serializer = FacebookCommentSerializer(comments, many=True)
        return Response(serializer.data)


class AdminUpdateSocialView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, user_id):
        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminUpdateSocialSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"success": "User social info updated", "user": serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
