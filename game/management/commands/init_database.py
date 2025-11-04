from django.core.management.base import BaseCommand
from django.core.management import execute_from_command_line
from django.db import connection
from django.conf import settings
import sys


class Command(BaseCommand):
    help = 'Force database initialization and migrations for production deployment'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force migration even if database appears initialized',
        )

    def handle(self, *args, **options):
        self.stdout.write("🚀 Force Database Initialization Started")
        
        # Show current database config
        self.stdout.write("🔍 Database Configuration:")
        db_config = settings.DATABASES['default']
        self.stdout.write(f"  Engine: {db_config['ENGINE']}")
        self.stdout.write(f"  Name: {db_config.get('NAME', 'N/A')}")
        self.stdout.write(f"  Host: {db_config.get('HOST', 'N/A')}")
        self.stdout.write(f"  User: {db_config.get('USER', 'N/A')}")
        
        # Test database connection
        self.stdout.write("🔗 Testing database connection...")
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT version()')
                version = cursor.fetchone()
                self.stdout.write(f"✅ Connected! PostgreSQL: {version[0][:60]}...")
                
                # Check existing tables
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    ORDER BY table_name
                """)
                tables = cursor.fetchall()
                table_names = [t[0] for t in tables]
                
                if tables:
                    self.stdout.write(f"📊 Found {len(tables)} existing tables:")
                    for table in table_names[:10]:  # Show first 10
                        self.stdout.write(f"  - {table}")
                    if len(tables) > 10:
                        self.stdout.write(f"  ... and {len(tables) - 10} more")
                else:
                    self.stdout.write("📊 No tables found - database is empty")
                
                # Check if Django is already initialized
                django_initialized = 'django_migrations' in table_names
                auth_tables_exist = 'auth_user' in table_names
                
                if django_initialized and auth_tables_exist and not options['force']:
                    self.stdout.write("✅ Django appears already initialized")
                    self.stdout.write("   Use --force to run migrations anyway")
                    return
                    
        except Exception as e:
            self.stdout.write(f"❌ Database connection failed: {e}")
            sys.exit(1)
        
        # Show migration status before
        self.stdout.write("📋 Migration status before:")
        try:
            execute_from_command_line(['manage.py', 'showmigrations', '--verbosity=1'])
        except Exception as e:
            self.stdout.write(f"⚠️ Could not show migrations: {e}")
        
        # Run migrations
        self.stdout.write("🗃️ Applying migrations...")
        try:
            execute_from_command_line(['manage.py', 'migrate', '--verbosity=2'])
            self.stdout.write("✅ Migrations completed successfully!")
        except Exception as e:
            self.stdout.write(f"❌ Migration failed: {e}")
            sys.exit(1)
        
        # Verify critical tables now exist
        self.stdout.write("🔍 Verifying critical Django tables:")
        required_tables = ['auth_user', 'django_migrations', 'django_session', 'auth_group']
        
        try:
            with connection.cursor() as cursor:
                for table in required_tables:
                    cursor.execute(f'SELECT COUNT(*) FROM {table}')
                    count = cursor.fetchone()[0]
                    self.stdout.write(f"✅ {table}: {count} records")
                    
            self.stdout.write("🎉 Database initialization completed successfully!")
            self.stdout.write("   Users can now register and log in.")
            
        except Exception as e:
            self.stdout.write(f"❌ Table verification failed: {e}")
            self.stdout.write("   Migration completed but tables may not be accessible")
            sys.exit(1)