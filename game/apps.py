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
        This runs migrations automatically on startup.
        """
        # Only run migrations in production and on web process startup
        if (os.environ.get('RENDER') and 
            not os.environ.get('MIGRATIONS_RAN') and
            'runserver' not in sys.argv and 
            'migrate' not in sys.argv and
            'shell' not in sys.argv and
            'collectstatic' not in sys.argv):
            
            print("🚀 AUTO-MIGRATION: Running migrations on Django startup...")
            
            try:
                # Test database connection first
                with connection.cursor() as cursor:
                    cursor.execute('SELECT 1')
                    print("✅ Database connection verified")
                
                # Check if auth_user table exists
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT COUNT(*) 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'auth_user'
                    """)
                    auth_table_exists = cursor.fetchone()[0] > 0
                
                if not auth_table_exists:
                    print("❌ auth_user table missing - running migrations...")
                    
                    # Run migrations
                    print("🔧 Migrating Django core apps...")
                    for app in ['contenttypes', 'auth', 'admin', 'sessions']:
                        execute_from_command_line(['manage.py', 'migrate', app, '--verbosity=1'])
                        print(f"✅ {app} migrated")
                    
                    print("🔧 Running all migrations...")
                    execute_from_command_line(['manage.py', 'migrate', '--verbosity=1'])
                    
                    # Verify auth_user table now exists
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT COUNT(*) FROM auth_user')
                        print(f"✅ auth_user table verified with {cursor.fetchone()[0]} users")
                    
                    print("🎉 AUTO-MIGRATION: Migrations completed successfully!")
                else:
                    print("✅ auth_user table exists - migrations already applied")
                
                # Set environment variable to prevent re-running
                os.environ['MIGRATIONS_RAN'] = '1'
                
            except Exception as e:
                print(f"❌ AUTO-MIGRATION failed: {e}")
                import traceback
                traceback.print_exc()
                # Don't sys.exit() - let Django continue and show the error
                
        elif os.environ.get('MIGRATIONS_RAN'):
            print("ℹ️ Migrations already completed this session")
