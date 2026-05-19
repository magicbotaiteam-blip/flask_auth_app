#!/usr/bin/env python3
"""
Run the complete Magic Bot AI app
"""

from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv(dotenv_path=Path('/Users/siyang/flask_cronjobs/.env'), override=True)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = 'true'

from app_complete_with_groups import app

if __name__ == "__main__":
    print("=" * 60)
    print("Magic Bot AI - Complete Edition")
    print("=" * 60)
    print("Features:")
    print("✅ User Authentication (Local + Google OAuth)")
    print("✅ Bots Management Dashboard")
    print("✅ Telegram Bots Management API (11 endpoints)")
    print("✅ Group Collaboration System")
    print("✅ Shared Bots & Templates")
    print("✅ Group Chat & Analytics")
    print("=" * 60)
    print("Starting server on http://localhost:5000")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)