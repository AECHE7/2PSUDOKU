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

# Test Django configuration
echo "🔧 Testing Django configuration..."
python manage.py check

# Try to run migrations during build (may fail if DB not available, that's OK)
echo "🗃️ Attempting migrations during build (fallback)..."
python migrate_comprehensive.py || echo "⚠️ Build-time migrations failed (expected if DB not available yet)"

echo "✅ Build complete!"