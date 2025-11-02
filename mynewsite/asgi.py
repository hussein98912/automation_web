import os
import django
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application  # ✅ Correct import

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mynewsite.settings")
django.setup()  # Optional but safe for Channels

import automation_app.routing  # Import after setup

application = ProtocolTypeRouter({
    "http": get_asgi_application(),  # ✅ Use the function directly
    "websocket": AuthMiddlewareStack(
        URLRouter(
            automation_app.routing.websocket_urlpatterns
        )
    ),
})
