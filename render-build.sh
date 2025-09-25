#!/usr/bin/env bash
# Build script for Render deployment

set -o errexit

echo "📦 Installing dependencies..."
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

echo "🔧 Running database migrations..."
# Try to run migrations, but don't fail if they don't exist yet
alembic upgrade head 2>/dev/null || echo "⚠️ No migrations found or database not ready - will run on startup"

echo "✅ Build complete!"