import os
import django
from django.core.asgi import get_asgi_application

# Set the Django settings module before importing anything Django-related
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Setup Django BEFORE importing models or other Django components
django.setup()

# Now we can safely import Django-dependent modules
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import game.routing

# Get the Django ASGI application
django_asgi_app = get_asgi_application()

# Define the main ASGI application
application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(
        URLRouter(
            game.routing.websocket_urlpatterns
        )
    ),
})
