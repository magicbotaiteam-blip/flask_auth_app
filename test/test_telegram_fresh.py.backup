#!/usr/bin/env python3
"""
FRESH Telegram test - no cache issues
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

print("FRESH Telegram API Test")
print("=" * 60)

try:
    from bot_services import BotServiceFactory
    
    print("1. Creating Telegram service...")
    # Use a test token (will fail but should fail with API error, not parameter error)
    service = BotServiceFactory.create_service('telegram', {
        'token': '123:ABC',
        'name': 'Test'
    })
    
    print("2. Checking method signature...")
    import inspect
    sig = inspect.signature(service.send_message)
    print(f"   Signature: {sig}")
    
    print("\n3. Testing with recipient parameter...")
    try:
        # This should fail with Telegram API error (invalid token)
        # NOT with parameter error
        result = service.send_message(
            message="Test message",
            recipient="123456789"  # Using recipient, not chat_id
        )
        print(f"   Result: {result}")
    except TypeError as e:
        if "recipient" in str(e):
            print(f"   ❌ STILL HAS PARAMETER ERROR: {e}")
            print("   The fix didn't apply!")
        elif "chat_id" in str(e):
            print(f"   ❌ OLD PARAMETER NAME: {e}")
            print("   Using cached/old version!")
        else:
            print(f"   ✅ Different error: {e}")
    except Exception as e:
        print(f"   ✅ Expected API error: {e}")
        
    print("\n4. Testing with chat_id parameter (should fail)...")
    try:
        # This should fail with parameter error
        result = service.send_message(
            message="Test message",
            chat_id="123456789"  # WRONG: using old parameter name
        )
        print(f"   ❌ UNEXPECTED: Worked with chat_id parameter")
    except TypeError as e:
        if "chat_id" in str(e):
            print(f"   ✅ CORRECT: Fails with chat_id parameter")
        else:
            print(f"   ❌ Different error: {e}")
    except Exception as e:
        print(f"   ❌ Different error: {e}")
        
except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 60)
print("If you see 'STILL HAS PARAMETER ERROR' or 'OLD PARAMETER NAME'")
print("then you're using cached/old files.")
print("=" * 60)