# mynewsite/asgi.py
import os
import django
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mynewsite.settings")
django.setup()  # ✅ Ensure apps are ready before imports

import automation_app.routing  # import after setup

application = ProtocolTypeRouter({
    "http": django.core.asgi.get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            automation_app.routing.websocket_urlpatterns
        )
    ),
})
