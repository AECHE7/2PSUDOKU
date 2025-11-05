import os
import django
from django.core.asgi import get_asgi_application

# Set the Django settings module before importing anything Django-related
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Setup Django BEFORE importing models or other Django components
django.setup()

# ASGI-level migration check for Render deployment
if os.environ.get('RENDER') and not os.environ.get('ASGI_MIGRATIONS_RAN'):
    print("🚀 ASGI: Running critical migration check...")
    try:
        from django.db import connection
        from django.core.management import execute_from_command_line
        
        # Check if core tables exist and have required columns
        with connection.cursor() as cursor:
            # Check auth_user table
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'auth_user'
            """)
            auth_table_exists = cursor.fetchone()[0] > 0
            
            # Check if game_gamesession has difficulty column (race mode)
            difficulty_column_exists = False
            if auth_table_exists:
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'game_gamesession' 
                    AND column_name = 'difficulty'
                """)
                difficulty_column_exists = cursor.fetchone()[0] > 0
        
        if not auth_table_exists or not difficulty_column_exists:
            if not auth_table_exists:
                print("❌ ASGI: auth_user table missing - running emergency migrations...")
            else:
                print("❌ ASGI: difficulty column missing - running race-mode migrations...")
            
            execute_from_command_line(['manage.py', 'migrate', '--verbosity=1'])
            print("✅ ASGI: Emergency migrations completed")
        else:
            print("✅ ASGI: All required tables and columns exist")
            
        os.environ['ASGI_MIGRATIONS_RAN'] = '1'
        
    except Exception as e:
        print(f"⚠️ ASGI migration check failed: {e}")
        # Continue anyway - Django app config will handle it

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
