from rest_framework import generics, permissions
from rest_framework_simplejwt.authentication import JWTAuthentication
from ..models import Notification
from ..serializers import NotificationSerializer

class UserNotificationListAPIView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only return notifications for the user from the token
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')
    

    