#!/usr/bin/env python
"""
Comprehensive migration script that ensures all Django migrations run properly.
This handles both built-in Django migrations and our custom app migrations.
"""
import os
import sys
import django
from django.conf import settings
from django.core.management import execute_from_command_line
from django.db import connection
from django.db.utils import OperationalError

def setup_django():
    """Setup Django environment"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

def test_database_connection():
    """Test database connectivity"""
    print("🔗 Testing database connection...")
    try:
        with connection.cursor() as cursor:
            # Test connection with database-agnostic query
            cursor.execute('SELECT 1')
            result = cursor.fetchone()
            print("✅ Database connection successful!")
            
            # Check existing tables (database-agnostic approach)
            db_engine = connection.vendor
            print(f"📊 Database engine: {db_engine}")
            
            if db_engine == 'postgresql':
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    ORDER BY table_name
                """)
                tables = cursor.fetchall()
                table_names = [t[0] for t in tables]
            elif db_engine == 'sqlite':
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' 
                    ORDER BY name
                """)
                tables = cursor.fetchall()
                table_names = [t[0] for t in tables]
            else:
                print("⚠️ Unknown database engine, skipping table check")
                return []
            
            print(f"📊 Found {len(tables)} existing tables")
            if table_names:
                print(f"   Sample tables: {table_names[:5]}")
                
            return table_names
            
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)

def run_migrations():
    """Run Django migrations with proper error handling"""
    print("🗃️ Running Django migrations...")
    
    # Show migration status before
    print("📋 Migration status before:")
    try:
        execute_from_command_line(['manage.py', 'showmigrations', '--verbosity=1'])
    except Exception as e:
        print(f"⚠️ Could not show migrations: {e}")
    
    # Run migrations for built-in Django apps first
    django_apps = ['contenttypes', 'auth', 'admin', 'sessions']
    
    for app in django_apps:
        print(f"🔧 Migrating {app}...")
        try:
            execute_from_command_line(['manage.py', 'migrate', app, '--verbosity=2'])
            print(f"✅ {app} migrations completed")
        except Exception as e:
            print(f"❌ {app} migration failed: {e}")
            # Don't exit - try other apps
    
    # Now run all migrations
    print("🔧 Running all remaining migrations...")
    try:
        execute_from_command_line(['manage.py', 'migrate', '--verbosity=2'])
        print("✅ All migrations completed successfully!")
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False
    
    return True

def verify_critical_tables():
    """Verify that critical Django tables exist"""
    print("🔍 Verifying critical Django tables...")
    
    required_tables = [
        'auth_user', 'auth_group', 'auth_permission',
        'django_migrations', 'django_session', 'django_content_type'
    ]
    
    try:
        with connection.cursor() as cursor:
            for table in required_tables:
                cursor.execute(f'SELECT COUNT(*) FROM {table}')
                count = cursor.fetchone()[0]
                print(f"✅ {table}: {count} records")
                
        print("🎉 All critical Django tables verified!")
        return True
        
    except Exception as e:
        print(f"❌ Table verification failed: {e}")
        
        # Show what tables actually exist
        try:
            with connection.cursor() as cursor:
                if connection.vendor == 'postgresql':
                    cursor.execute("""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        ORDER BY table_name
                    """)
                elif connection.vendor == 'sqlite':
                    cursor.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' 
                        ORDER BY name
                    """)
                else:
                    print("⚠️ Cannot list tables for this database engine")
                    return False
                
                tables = cursor.fetchall()
                actual_tables = [t[0] for t in tables]
                print(f"📊 Actual tables in database: {actual_tables}")
        except Exception as table_error:
            print(f"⚠️ Could not list tables: {table_error}")
            
        return False

def main():
    """Main migration script"""
    print("🚀 Comprehensive Django Migration Script Started")
    print(f"📅 Time: {os.popen('date').read().strip()}")
    print(f"🏠 Working directory: {os.getcwd()}")
    print(f"🔍 Directory contents: {os.listdir('.')}")
    
    # Ensure we have manage.py
    if not os.path.exists('manage.py'):
        print("❌ manage.py not found! Current directory contents:")
        print(os.listdir('.'))
        sys.exit(1)
    
    # Setup Django
    setup_django()
    
    # Show configuration
    print("🔍 Django Configuration:")
    db_config = settings.DATABASES['default']
    print(f"   Engine: {db_config['ENGINE']}")
    print(f"   Name: {db_config.get('NAME', 'N/A')}")
    print(f"   Host: {db_config.get('HOST', 'N/A')}")
    print(f"   Installed Apps: {settings.INSTALLED_APPS}")
    
    # Test database
    existing_tables = test_database_connection()
    
    # Run migrations
    success = run_migrations()
    if not success:
        print("❌ Migration process failed!")
        sys.exit(1)
    
    # Verify results
    if verify_critical_tables():
        print("🎉 Migration script completed successfully!")
        print("   Django authentication system is ready!")
        sys.exit(0)
    else:
        print("❌ Migration verification failed!")
        sys.exit(1)

if __name__ == '__main__':
    main()