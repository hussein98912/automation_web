import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Notification

class NotificationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        from .models import Notification
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.group_name = f"user_{self.user_id}"

        # Join group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

        # Send current unread count
        unread_count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            "type": "unread_count",
            "count": unread_count
        }))

    async def disconnect(self, close_code):
        # Leave group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    # Receive message from group
    async def send_notification(self, event):
        message = event['message']
        unread_count = await self.get_unread_count()

        await self.send(text_data=json.dumps({
            'type': 'notification',
            'message': message,
            'unread_count': unread_count
        }))

    @database_sync_to_async
    def get_unread_count(self):
        from .models import Notification
        return Notification.objects.filter(user_id=self.user_id, is_read=False).count()
