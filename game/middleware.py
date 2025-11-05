"""
Emergency migration middleware - runs migrations if auth_user table is missing.
This is the absolute last line of defense against migration failures.
"""
from django.http import HttpResponse
from django.db import connection
from django.core.management import execute_from_command_line
import os


class EmergencyMigrationMiddleware:
    """
    Middleware that checks for auth_user table on every request
    and runs migrations if it's missing.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.migrations_checked = False
    
    def __call__(self, request):
        # Only check once per process and only in production
        if (not self.migrations_checked and 
            os.environ.get('RENDER') and 
            not os.environ.get('MIDDLEWARE_MIGRATIONS_RAN')):
            
            try:
                # Quick auth_user table check
                with connection.cursor() as cursor:
                    cursor.execute('SELECT COUNT(*) FROM auth_user LIMIT 1')
                    # If this succeeds, table exists
                    print("✅ MIDDLEWARE: auth_user table verified")
                    
            except Exception as e:
                if 'does not exist' in str(e):
                    print("❌ MIDDLEWARE: auth_user missing - EMERGENCY MIGRATION!")
                    
                    try:
                        # Emergency migration execution
                        execute_from_command_line(['manage.py', 'migrate', '--verbosity=1'])
                        print("🎉 MIDDLEWARE: Emergency migrations completed!")
                        
                        # Set flag to prevent re-running
                        os.environ['MIDDLEWARE_MIGRATIONS_RAN'] = '1'
                        
                    except Exception as migration_error:
                        print(f"💥 MIDDLEWARE: Emergency migration failed: {migration_error}")
                        return HttpResponse(
                            "Database initialization in progress. Please refresh in a moment.",
                            status=503
                        )
                else:
                    print(f"⚠️ MIDDLEWARE: Database error: {e}")
            
            self.migrations_checked = True
        
        # Continue with normal request processing
        response = self.get_response(request)
        return response