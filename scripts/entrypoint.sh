#!/usr/bin/env bash
set -o errexit
set -o pipefail

echo "🧭 Entrypoint started: ensuring DB is ready, running migrations, then starting Daphne"
echo "📅 Current time: $(date)"
echo "🏠 Current directory: $(pwd)"
echo "👤 Current user: $(whoami)"

# Ensure we're in the right directory (where manage.py exists)
if [ ! -f "manage.py" ]; then
    echo "⚠️ manage.py not found in current directory, looking for it..."
    if [ -f "/opt/render/project/src/manage.py" ]; then
        cd /opt/render/project/src
        echo "📁 Changed to /opt/render/project/src"
    else
        echo "❌ Cannot find manage.py! Current directory contents:"
        ls -la
        exit 1
    fi
fi

echo "📂 Working directory: $(pwd)"
echo "📄 Django management script: $(ls -la manage.py)"

# Ensure DJANGO_SETTINGS_MODULE is set
export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-config.settings}

# Show environment variables
echo "🌍 Key environment variables:"
echo "PORT: ${PORT:-'not set'}"
echo "DATABASE_URL: ${DATABASE_URL:0:50}..." 
echo "REDIS_URL: ${REDIS_URL:0:50}..."
echo "DJANGO_SETTINGS_MODULE: $DJANGO_SETTINGS_MODULE"

# Show database configuration for debugging
echo "🔍 Database configuration:"
python -c "
import os
import django
from django.conf import settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
print(f'Database engine: {settings.DATABASES[\"default\"][\"ENGINE\"]}')
print(f'Database name: {settings.DATABASES[\"default\"].get(\"NAME\", \"N/A\")}')
print(f'Database host: {settings.DATABASES[\"default\"].get(\"HOST\", \"N/A\")}')
print(f'Database user: {settings.DATABASES[\"default\"].get(\"USER\", \"N/A\")}')
print(f'DEBUG mode: {settings.DEBUG}')
print(f'INSTALLED_APPS: {list(settings.INSTALLED_APPS)}')
"

# Test database connection thoroughly  
echo "🔗 Testing database connection..."
python -c "
import os
import django
from django.conf import settings
from django.db import connection
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
try:
    with connection.cursor() as cursor:
        cursor.execute('SELECT version()')
        version = cursor.fetchone()
        print(f'✅ Database connection successful! PostgreSQL version: {version[0][:50]}...')
        
        # Check if any tables exist
        cursor.execute('''
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            LIMIT 10
        ''')
        tables = cursor.fetchall()
        if tables:
            print(f'📊 Found {len(tables)} existing tables: {[t[0] for t in tables]}')
        else:
            print('📊 No tables found in database - this is expected on first deployment')
            
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    import traceback
    traceback.print_exc()
    raise
" 2>/dev/null || echo "⚠️ Advanced DB connection test failed"

# Show current migration status
echo "📋 Current migration status:"
python manage.py showmigrations --verbosity=1

# Wait for DB to be available and run migrations with retries
MAX_RETRIES=15
COUNT=0
echo "🗃️ Running migrations..."

# First check what migrations are needed
echo "📋 Checking what migrations need to be applied:"
python manage.py showmigrations --plan | head -20

# Try migrations with detailed error handling
until python manage.py migrate --noinput --verbosity=2; do
  COUNT=$((COUNT+1))
  if [ "$COUNT" -ge "$MAX_RETRIES" ]; then
    echo "⚠️  Migrations failed after $MAX_RETRIES attempts"
    echo "🔍 Final migration status:"
    python manage.py showmigrations --verbosity=1
    echo "🔍 Checking database tables after failed migration:"
    python -c "
import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup()
from django.db import connection
try:
    with connection.cursor() as cursor:
        cursor.execute('SELECT table_name FROM information_schema.tables WHERE table_schema = \\'public\\' ORDER BY table_name')
        tables = cursor.fetchall()
        print(f'Database has {len(tables)} tables: {[t[0] for t in tables][:10]}')
except Exception as e:
    print(f'Error checking tables: {e}')
    " 2>/dev/null || echo "Could not check database tables"
    exit 1
  fi
  echo "🔁 Migration attempt $COUNT failed — retrying in 5s..."
  sleep 5
done

echo "✅ Migrations applied successfully"

# Show final migration status
echo "📋 Final migration status:"
python manage.py showmigrations --verbosity=1

# Verify critical tables exist
echo "🔍 Verifying critical Django tables exist:"
python -c "
import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup()
from django.db import connection
required_tables = ['auth_user', 'django_migrations', 'django_session', 'django_content_type']
try:
    with connection.cursor() as cursor:
        for table in required_tables:
            cursor.execute(f'SELECT COUNT(*) FROM {table}')
            count = cursor.fetchone()[0]
            print(f'✅ {table}: {count} records')
    print('🎉 All critical Django tables verified!')
except Exception as e:
    print(f'❌ Table verification failed: {e}')
    # Still continue - don't fail deployment for this
" 2>/dev/null || echo "⚠️ Could not verify tables"

# Collect static files (idempotent)
echo "📁 Collecting static files"
python manage.py collectstatic --noinput || echo "Collectstatic failed or skipped"

echo "🚀 Starting Daphne"
exec daphne -p $PORT -b 0.0.0.0 config.asgi:application
