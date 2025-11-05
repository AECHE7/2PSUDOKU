"""
Django signals for post-migration database verification
"""
from django.db import connection
from django.db.models.signals import post_migrate
from django.dispatch import receiver
import os


@receiver(post_migrate)
def verify_database_setup(sender, **kwargs):
    """
    Signal handler that runs after migrations complete.
    This is the proper place for database verification.
    """
    # Only run verification in production after all migrations
    if (os.environ.get('RENDER') and 
        sender.name == 'game' and  # Only run once when our app migrates
        not os.environ.get('DB_VERIFIED')):
        
        print("🔍 POST-MIGRATE: Verifying database setup after migrations...")
        
        try:
            # Verify critical tables exist
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('auth_user', 'game_gamesession')
                    ORDER BY table_name
                """)
                tables = cursor.fetchall()
                table_names = [t[0] for t in tables]
                
                if 'auth_user' in table_names and 'game_gamesession' in table_names:
                    print("✅ POST-MIGRATE: All critical tables verified!")
                    print(f"   Tables found: {table_names}")
                    
                    # Count records
                    cursor.execute('SELECT COUNT(*) FROM auth_user')
                    user_count = cursor.fetchone()[0]
                    cursor.execute('SELECT COUNT(*) FROM game_gamesession')
                    game_count = cursor.fetchone()[0]
                    
                    print(f"   Users: {user_count}, Games: {game_count}")
                    print("🎉 Database is ready for 2PSUDOKU gameplay!")
                else:
                    print(f"⚠️ POST-MIGRATE: Missing tables. Found: {table_names}")
                
                os.environ['DB_VERIFIED'] = '1'
                
        except Exception as e:
            print(f"❌ POST-MIGRATE verification failed: {e}")