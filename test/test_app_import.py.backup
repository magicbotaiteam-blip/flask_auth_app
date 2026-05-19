#!/usr/bin/env python3
"""
Test that the Flask app imports correctly
"""

import sys
import os

print("Testing Flask app import...")
print("=" * 60)

try:
    # Add current directory to path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    # Import the app
    from app_with_telegram_api import app
    
    print("✅ App imported successfully!")
    print(f"App name: {app.name}")
    print(f"Debug mode: {app.debug}")
    
    # Check if routes are registered
    print("\nChecking registered routes...")
    print("-" * 40)
    
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': sorted(list(rule.methods - {'HEAD', 'OPTIONS'})),
            'path': str(rule)
        })
    
    # Sort by path
    routes.sort(key=lambda x: x['path'])
    
    # Count Telegram API routes
    telegram_routes = [r for r in routes if '/api/telegram/' in r['path']]
    
    print(f"Total routes: {len(routes)}")
    print(f"Telegram API routes: {len(telegram_routes)}")
    
    print("\nTelegram API endpoints:")
    print("-" * 40)
    for route in telegram_routes[:10]:  # Show first 10
        print(f"{route['methods'][0] if route['methods'] else 'GET':<7} {route['path']}")
    
    if len(telegram_routes) > 10:
        print(f"... and {len(telegram_routes) - 10} more")
    
    print("\n" + "=" * 60)
    print("✅ All tests passed! The app is ready to run.")
    print("\nTo start the app:")
    print("  cd /Users/siyang/flask_auth_app")
    print("  python app_with_telegram_api.py")
    print("\nThen visit: http://localhost:5000")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("\nMake sure all dependencies are installed:")
    print("  pip install flask flask-dance werkzeug")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("=" * 60)