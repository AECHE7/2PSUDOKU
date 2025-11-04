#!/usr/bin/env bash
set -o errexit
set -o pipefail

echo "🧭 Entrypoint started: ensuring DB is ready, running migrations, then starting Daphne"

# Ensure DJANGO_SETTINGS_MODULE is set
export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-config.settings}

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
print(f'DEBUG mode: {settings.DEBUG}')
"

# Test database connection
echo "🔗 Testing database connection..."
python manage.py dbshell --command="\q" 2>/dev/null || echo "⚠️ Direct DB connection test failed"

# Show current migration status
echo "📋 Current migration status:"
python manage.py showmigrations --verbosity=1

# Wait for DB to be available and run migrations with retries
MAX_RETRIES=15
COUNT=0
echo "🗃️ Running migrations..."
until python manage.py migrate --noinput --verbosity=2; do
  COUNT=$((COUNT+1))
  if [ "$COUNT" -ge "$MAX_RETRIES" ]; then
    echo "⚠️  Migrations failed after $MAX_RETRIES attempts"
    echo "🔍 Final migration status:"
    python manage.py showmigrations --verbosity=1
    exit 1
  fi
  echo "🔁 Migration attempt $COUNT failed — retrying in 5s..."
  sleep 5
done

echo "✅ Migrations applied successfully"

# Show final migration status
echo "📋 Final migration status:"
python manage.py showmigrations --verbosity=1

# Collect static files (idempotent)
echo "📁 Collecting static files"
python manage.py collectstatic --noinput || echo "Collectstatic failed or skipped"

echo "🚀 Starting Daphne"
exec daphne -p $PORT -b 0.0.0.0 config.asgi:application
