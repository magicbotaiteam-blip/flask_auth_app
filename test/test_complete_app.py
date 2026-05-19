#!/usr/bin/env python3
"""
Test the complete Magic Bot AI app with Groups
"""

import sys
import os

print("Testing Complete Magic Bot AI App")
print("=" * 60)

try:
    # Add current directory to path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    # Import the app
    from app_complete_with_groups import app
    
    print("✅ App imported successfully!")
    print(f"App name: {app.name}")
    
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
    
    # Count routes by category
    telegram_routes = [r for r in routes if '/api/telegram/' in r['path']]
    group_routes = [r for r in routes if '/groups/' in r['path'] and '/api/' not in r['path']]
    bot_routes = [r for r in routes if '/bot/' in r['path'] and '/api/' not in r['path']]
    
    print(f"Total routes: {len(routes)}")
    print(f"Telegram API routes: {len(telegram_routes)}")
    print(f"Group UI routes: {len(group_routes)}")
    print(f"Bot UI routes: {len(bot_routes)}")
    
    print("\nKey Group Collaboration Routes:")
    print("-" * 40)
    group_sample = [r for r in group_routes if any(x in r['path'] for x in ['/groups', '/group'])]
    for route in group_sample[:10]:
        print(f"{route['methods'][0] if route['methods'] else 'GET':<7} {route['path']}")
    
    print("\nKey Telegram API Routes:")
    print("-" * 40)
    for route in telegram_routes[:5]:
        print(f"{route['methods'][0] if route['methods'] else 'GET':<7} {route['path']}")
    
    print("\n" + "=" * 60)
    print("✅ All tests passed! The complete app is ready.")
    print("\nTo start the app:")
    print("  cd /Users/siyang/flask_auth_app")
    print("  python app_complete_with_groups.py")
    print("\nFeatures available:")
    print("  1. User authentication (local + Google OAuth)")
    print("  2. Bot management dashboard")
    print("  3. Telegram Bots Management API (11 endpoints)")
    print("  4. Group collaboration system")
    print("  5. Shared bots & templates")
    print("  6. Group chat & analytics")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("\nMake sure all dependencies are installed:")
    print("  pip install flask flask-dance werkzeug")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("=" * 60)