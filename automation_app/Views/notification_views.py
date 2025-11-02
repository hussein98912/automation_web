from rest_framework import generics, permissions
from rest_framework_simplejwt.authentication import JWTAuthentication
from ..models import Notification
from ..serializers import NotificationSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status


class UserNotificationListAPIView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only return notifications for the user from the token
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')
    

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def mark_notifications_read(request):
    """
    Mark notifications as read for the authenticated user.
    Optionally, you can send a list of notification IDs in the request body.
    """
    notification_ids = request.data.get('notification_ids', None)

    if notification_ids:
        # Mark specific notifications
        notifications = Notification.objects.filter(id__in=notification_ids, user=request.user)
    else:
        # Mark all unread notifications
        notifications = Notification.objects.filter(user=request.user, is_read=False)
    
    updated_count = notifications.update(is_read=True)
    
    serializer = NotificationSerializer(notifications, many=True)
    return Response({
        "updated_count": updated_count,
        "notifications": serializer.data
    }, status=status.HTTP_200_OK)





