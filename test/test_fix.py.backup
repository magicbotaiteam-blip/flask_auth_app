#!/usr/bin/env python3
"""
Test to verify the Telegram API fix
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

print("Testing Telegram API parameter fix...")
print("=" * 60)

# First, let's check what's in the test_telegram_simple.py file
with open("test_telegram_simple.py", "r") as f:
    content = f.read()
    
if "chat_id=TEST_CHAT_ID" in content:
    print("❌ test_telegram_simple.py still has 'chat_id='")
    print("   It should use 'recipient=' instead")
else:
    print("✅ test_telegram_simple.py uses correct parameter name")

if "recipient=TEST_CHAT_ID" in content:
    print("✅ test_telegram_simple.py has 'recipient=' parameter")
else:
    print("❌ test_telegram_simple.py missing 'recipient=' parameter")

# Now test the actual bot_services.py
try:
    from bot_services import BotServiceFactory
    
    print("\nTesting BotServiceFactory...")
    service = BotServiceFactory.create_service('telegram', {
        'token': 'test_token',
        'name': 'TestBot'
    })
    
    # Check the method signature
    import inspect
    sig = inspect.signature(service.send_message)
    
    print(f"\nTelegramBotService.send_message signature:")
    print(f"  {sig}")
    
    # Check parameters
    params = list(sig.parameters.keys())
    if 'recipient' in params:
        print("✅ Has 'recipient' parameter")
    else:
        print("❌ Missing 'recipient' parameter")
        
    if 'chat_id' in params:
        print("❌ Still has 'chat_id' parameter (should be removed)")
    else:
        print("✅ No 'chat_id' parameter (correct)")
    
    # Try to call it
    print("\nTrying to call send_message...")
    try:
        # This will fail due to invalid token, but shouldn't be parameter error
        result = service.send_message(
            message="Test",
            recipient="123456789"  # Using recipient
        )
        print(f"✅ Method called successfully (result: {result})")
    except TypeError as e:
        if "recipient" in str(e):
            print(f"❌ TypeError about recipient: {e}")
        elif "chat_id" in str(e):
            print(f"❌ Still has chat_id issue: {e}")
        else:
            print(f"✅ Different error (expected): {e}")
    except Exception as e:
        print(f"✅ Expected API error: {e}")
        
except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Summary:")
print("1. bot_services.py should use 'recipient' parameter")
print("2. test_telegram_simple.py should use 'recipient' parameter")
print("3. All calls should use recipient= not chat_id=")
print("=" * 60)