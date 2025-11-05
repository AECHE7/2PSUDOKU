#!/usr/bin/env bash
set -o errexit
set -o pipefail

echo "🚀 Starting production server with migrations..."
echo "📅 Time: $(date)"

# Validate environment variables first
echo "🔍 Validating environment..."
python validate_env.py

if [ $? -ne 0 ]; then
    echo "❌ Environment validation failed!"
    exit 1
fi

# Run comprehensive race-mode migrations first
echo "🗃️ Running comprehensive race-mode migrations..."
python migrate_race_mode.py

if [ $? -eq 0 ]; then
    echo "✅ Migrations completed successfully!"
else
    echo "❌ Migrations failed!"
    exit 1
fi

# Collect static files
echo "📦 Collecting static files..."
python manage.py collectstatic --noinput --clear

if [ $? -eq 0 ]; then
    echo "✅ Static files collected successfully!"
else
    echo "⚠️ Static files collection failed, continuing anyway..."
fi

# Start the web server
echo "🌐 Starting Daphne ASGI server..."
exec daphne -p $PORT -b 0.0.0.0 config.asgi:application
