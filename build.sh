#!/usr/bin/env bash
set -o errexit  # Exit on error

echo "🚀 Starting build process..."

# Set Django settings module
export DJANGO_SETTINGS_MODULE=config.settings

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

# Run migrations
echo "🗃️ Running database migrations..."
python manage.py migrate --noinput

# Create cache table for sessions (if needed)
echo "🔄 Setting up cache tables..."
python manage.py createcachetable 2>/dev/null || echo "Cache table setup skipped"

echo "✅ Build complete!"