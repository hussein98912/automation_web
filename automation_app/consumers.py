# automation_app/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

class NotificationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        from .models import Notification  

        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.group_name = f"user_{self.user_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        unread_count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            "type": "unread_count",
            "count": unread_count
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def send_notification(self, event):
        from .models import Notification  # ✅ Import inside method

        message = event['message']
        unread_count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'message': message,
            'unread_count': unread_count
        }))

    @database_sync_to_async
    def get_unread_count(self):
        from .models import Notification  # ✅ Import inside method
        return Notification.objects.filter(user_id=self.user_id, is_read=False).count()
