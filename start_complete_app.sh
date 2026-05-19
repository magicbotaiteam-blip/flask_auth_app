#!/bin/bash
# Start the Complete Magic Bot AI App with Teams

echo "================================================"
echo "Magic Bot AI - Complete Edition"
echo "================================================"
echo ""
echo "Features:"
echo "✅ User Authentication (Local + Google OAuth)"
echo "✅ Bots Management Dashboard"
echo "✅ Telegram Bots Management API (11 endpoints)"
echo "✅ Team Collaboration System"
echo "✅ Shared Bots & Templates"
echo "✅ Team Chat & Analytics"
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
python -c "
import flask
import sqlite3
import json
from datetime import datetime
print('✅ Flask, SQLite3, JSON, datetime available')
" || {
    echo "❌ Missing dependencies"
    echo "Install with: pip install flask"
    exit 1
}

# Test app import
echo "Testing app import..."
python test_complete_app.py

# Start the app
echo ""
echo "================================================"
echo "Starting Flask application..."
echo "================================================"
python app_complete_with_groups.py