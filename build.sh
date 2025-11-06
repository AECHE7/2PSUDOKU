#!/usr/bin/env bash
set -o errexit  # Exit on error
set -o pipefail # Exit on pipe failure
set -o nounset  # Exit on undefined variable

# Print commands for debugging
set -x

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

# Print current migrations status
echo "📋 Current migration status:"
python manage.py showmigrations

# Run migrations - first attempt
echo "🗃️ Running migrations - primary attempt..."
python migrate_comprehensive.py

# Explicitly run game app migrations to ensure they're applied
echo "🎮 Running game-specific migrations..."
python manage.py migrate game --noinput

# Verify migrations
echo "🔍 Verifying migrations status:"
python manage.py showmigrations game

# Emergency schema fix - ensure critical columns exist
echo "🔧 Running emergency schema fixer..."
python ensure_db_schema.py

echo "✅ Build complete!"