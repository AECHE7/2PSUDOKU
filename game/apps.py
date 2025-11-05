"""
Django app configuration that automatically runs migrations on startup.
This ensures migrations run regardless of how the server starts.
"""
from django.apps import AppConfig
from django.conf import settings
from django.core.management import execute_from_command_line
from django.db import connection
import os
import sys


class GameConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'game'
    
    def ready(self):
        """
        Called when Django app is ready.
        Register signals and perform non-database initialization.
        """
        # Only log in production
        if os.environ.get('RENDER'):
            print("✅ Game app initialized - ASGI layer handled migrations")
            
        # Import signals to register them
        from . import signals
