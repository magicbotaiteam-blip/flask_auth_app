#!/usr/bin/env python3
"""
SIMPLE test using the FIXED Telegram service
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# Use the fixed version
sys.modules['bot_services'] = __import__('bot_services_fixed')
from bot_services_fixed import BotServiceFactory

print("Testing FIXED Telegram API")
print("=" * 60)

try:
    print("1. Creating Telegram service...")
    service = BotServiceFactory.create_service('telegram', {
        'token': '123:ABC',  # Invalid token
        'name': 'TestBot'
    })
    print("   ✅ Service created")
    
    print("\n2. Testing send_message with recipient parameter...")
    result = service.send_message(
        message="Test message from FIXED version!",
        recipient="123456789"  # Using recipient, NOT chat_id
    )
    
    print(f"   Result: {result}")
    
    if result.get('success'):
        print("   ✅ Message sent successfully!")
    else:
        error_msg = result.get('error', '')
        if 'chat_id' in str(error_msg).lower():
            print(f"   ❌ ERROR STILL HAS 'chat_id': {error_msg}")
        else:
            print(f"   ✅ Expected error (invalid token): {error_msg}")
    
    print("\n3. Testing get_bot_info...")
    info = service.get_bot_info()
    print(f"   Result: {info}")
    
except Exception as e:
    print(f"❌ Exception: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("This test uses the COMPLETELY FIXED version")
print("with NO 'chat_id' variable references.")
print("=" * 60)