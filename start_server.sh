#!/usr/bin/env bash
set -o errexit
set -o pipefail

echo "🚀 Starting production server with migrations..."
echo "📅 Time: $(date)"

# Run comprehensive migrations first
echo "🗃️ Running comprehensive migrations..."
python migrate_comprehensive.py

if [ $? -eq 0 ]; then
    echo "✅ Migrations completed successfully!"
else
    echo "❌ Migrations failed!"
    exit 1
fi

# Start the web server
echo "🌐 Starting Daphne ASGI server..."
exec daphne -p $PORT -b 0.0.0.0 config.asgi:application