#!/usr/bin/env python3
"""
Simple test to check for common errors
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def test_imports():
    print("1. Testing imports...")
    try:
        from app_working import app
        print("  ✅ app_working imports successfully")
        return True
    except Exception as e:
        print(f"  ❌ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_templates():
    print("\n2. Checking templates...")
    templates_needed = ['home.html', 'landing.html', 'my_bots.html', 'register_bot.html']
    missing = []
    
    for template in templates_needed:
        path = os.path.join('templates', template)
        if os.path.exists(path):
            print(f"  ✅ {template} exists")
        else:
            print(f"  ❌ {template} missing")
            missing.append(template)
    
    return len(missing) == 0

def test_database():
    print("\n3. Testing database...")
    import sqlite3
    try:
        conn = sqlite3.connect('users.db')
        
        # Check if enhanced columns exist
        cursor = conn.execute("PRAGMA table_info(bots)")
        columns = [row[1] for row in cursor.fetchall()]
        enhanced_cols = ['description', 'config', 'tags', 'webhook_url']
        
        for col in enhanced_cols:
            if col in columns:
                print(f"  ✅ Column '{col}' exists in bots table")
            else:
                print(f"  ❌ Column '{col}' missing from bots table")
        
        conn.close()
        return True
    except Exception as e:
        print(f"  ❌ Database error: {e}")
        return False

def main():
    print("=" * 60)
    print("Magic Bot AI - Error Diagnostics")
    print("=" * 60)
    
    tests = [
        ("Imports", test_imports),
        ("Templates", test_templates),
        ("Database", test_database),
    ]
    
    all_passed = True
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        if not test_func():
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ All basic tests passed!")
        print("\nCommon issues to check:")
        print("1. Make sure you're in the right directory:")
        print("   cd /Users/siyang/flask_auth_app")
        print("2. Activate virtual environment:")
        print("   source venv/bin/activate")
        print("3. Run the application:")
        print("   python app_working.py")
        print("4. If you get a specific error, please share it.")
    else:
        print("❌ Some tests failed. Please share the exact error message.")
    
    print("=" * 60)

if __name__ == "__main__":
    main()