#!/bin/bash
# Start the Flask app with Telegram Bot API

echo "================================================"
echo "Starting Magic Bot AI with Telegram Bot API"
echo "================================================"
echo ""
echo "Features:"
echo "✅ User authentication (Google OAuth + Local)"
echo "✅ Bot management dashboard"
echo "✅ Telegram Bots Management API (11 endpoints)"
echo "✅ Analytics and templates"
echo ""
echo "Note: Google OAuth requires Flask-Dance"
echo "Install with: pip install flask-dance"
echo ""
echo "Starting server on http://localhost:5000"
echo "Press Ctrl+C to stop"
echo "================================================"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Check dependencies
echo "Checking dependencies..."
python -c "import flask; import sqlite3; print('✅ Flask and SQLite3 available')" || {
    echo "❌ Missing dependencies"
    echo "Install with: pip install flask"
    exit 1
}

# Start the app
python app_with_telegram_api.py