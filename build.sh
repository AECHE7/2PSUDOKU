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

# Test Django setup
echo "� Testing Django configuration..."
python manage.py check --deploy

echo "✅ Build complete!"