#!/usr/bin/env bash
set -o errexit
set -o pipefail

echo "🧭 Entrypoint started: ensuring DB is ready, running migrations, then starting Daphne"

# Ensure DJANGO_SETTINGS_MODULE is set
export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-config.settings}

# Wait for DB to be available and run migrations with retries
MAX_RETRIES=10
COUNT=0
until python manage.py migrate --noinput; do
  COUNT=$((COUNT+1))
  if [ "$COUNT" -ge "$MAX_RETRIES" ]; then
    echo "⚠️  Migrations failed after $MAX_RETRIES attempts, exiting"
    exit 1
  fi
  echo "🔁 Migration attempt $COUNT failed — retrying in 3s..."
  sleep 3
done

echo "✅ Migrations applied successfully"

# Collect static files (idempotent)
echo "📁 Collecting static files"
python manage.py collectstatic --noinput || echo "Collectstatic failed or skipped"

echo "🚀 Starting Daphne"
exec daphne -p $PORT -b 0.0.0.0 config.asgi:application
