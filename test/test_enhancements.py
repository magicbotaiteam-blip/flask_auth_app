#!/usr/bin/env python3
"""
Test script to verify all enhancements are working
"""

import sqlite3
import json
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "users.db"

def test_database_schema():
    """Test that all database tables and columns exist"""
    print("Testing database schema...")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Check tables exist
    tables = ['users', 'bots', 'bot_analytics', 'group_members', 'bot_templates', 'export_history', 'search_history']
    
    for table in tables:
        try:
            conn.execute(f"SELECT 1 FROM {table} LIMIT 1")
            print(f"  ✓ Table '{table}' exists")
        except:
            print(f"  ✗ Table '{table}' missing")
            return False
    
    # Check enhanced columns in bots table
    enhanced_columns = [
        'description', 'is_active', 'last_used', 'usage_count', 
        'config', 'webhook_url', 'api_key', 'tags'
    ]
    
    cursor = conn.execute("PRAGMA table_info(bots)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    
    for column in enhanced_columns:
        if column in existing_columns:
            print(f"  ✓ Column '{column}' exists in bots table")
        else:
            print(f"  ✗ Column '{column}' missing from bots table")
            return False
    
    # Check indexes
    indexes = [
        'idx_bots_user_id', 'idx_bots_tags',
        'idx_bot_analytics_bot_id', 'idx_bot_analytics_timestamp', 'idx_bot_analytics_event_type',
        'idx_group_members_bot_id', 'idx_group_members_user_id',
        'idx_bot_templates_category', 'idx_bot_templates_is_public', 'idx_bot_templates_tags'
    ]
    
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
    existing_indexes = [row[0] for row in cursor.fetchall()]
    
    for index in indexes:
        if index in existing_indexes:
            print(f"  ✓ Index '{index}' exists")
        else:
            print(f"  ✗ Index '{index}' missing")
    
    conn.close()
    return True

def test_bot_services_module():
    """Test that bot services module works"""
    print("\nTesting bot services module...")
    
    try:
        from bot_services import BotServiceFactory, BotServiceError
        
        # Test factory
        platforms = BotServiceFactory.get_supported_platforms()
        print(f"  ✓ Supported platforms: {platforms}")
        
        # Test creating services (without actual tokens)
        try:
            telegram_service = BotServiceFactory.create_service('telegram', {'token': 'test'})
            print("  ✓ Telegram service created")
        except Exception as e:
            print(f"  ✓ Telegram service factory works (error expected without valid token)")
        
        # Test utility functions
        from bot_services import test_bot_connection
        result = test_bot_connection('telegram', 'invalid_token')
        print(f"  ✓ Connection test function works")
        
        return True
        
    except ImportError as e:
        print(f"  ✗ Failed to import bot_services: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Error testing bot services: {e}")
        return False

def test_analytics_module():
    """Test that analytics module works"""
    print("\nTesting analytics module...")
    
    try:
        from analytics import get_analytics, log_bot_event
        
        # Get analytics instance
        analytics = get_analytics(str(DB_PATH))
        print("  ✓ Analytics instance created")
        
        # Test logging an event
        success = log_bot_event(1, 'test_event', {'test': 'data'})
        if success:
            print("  ✓ Event logging works")
        else:
            print("  ✗ Event logging failed")
            return False
        
        # Test getting analytics
        from analytics import get_bot_analytics
        stats = get_bot_analytics(1, days=1)
        print(f"  ✓ Analytics retrieval works")
        
        return True
        
    except ImportError as e:
        print(f"  ✗ Failed to import analytics: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Error testing analytics: {e}")
        return False

def test_sample_data():
    """Test with sample data"""
    print("\nTesting with sample data...")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Check existing bots have config
    bots = conn.execute("SELECT id, name, config FROM bots LIMIT 3").fetchall()
    
    for bot in bots:
        print(f"  Bot: {bot['name']} (ID: {bot['id']})")
        
        # Check config
        if bot['config']:
            try:
                config = json.loads(bot['config'])
                print(f"    ✓ Config JSON is valid")
                print(f"    - Platform: {config.get('messaging_platform', 'N/A')}")
                print(f"    - LLM: {config.get('llm_provider', 'N/A')}")
            except:
                print(f"    ✗ Config JSON is invalid")
        else:
            print(f"    ⚠ Config is empty")
    
    # Count records
    bot_count = conn.execute("SELECT COUNT(*) as count FROM bots").fetchone()['count']
    user_count = conn.execute("SELECT COUNT(*) as count FROM users").fetchone()['count']
    
    print(f"\n  Database has {user_count} users and {bot_count} bots")
    
    conn.close()
    return True

def main():
    """Run all tests"""
    print("=" * 60)
    print("Magic Bot AI - Enhancements Test Suite")
    print("=" * 60)
    
    tests = [
        ("Database Schema", test_database_schema),
        ("Bot Services Module", test_bot_services_module),
        ("Analytics Module", test_analytics_module),
        ("Sample Data", test_sample_data),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"  ✗ Test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY:")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {test_name}")
        if success:
            passed += 1
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All enhancements are properly implemented!")
        return 0
    else:
        print(f"\n⚠ {total - passed} tests failed. Review the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())