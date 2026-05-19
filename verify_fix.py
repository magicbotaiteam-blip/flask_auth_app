#!/usr/bin/env python3
"""
Verify the Telegram API fix
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

print("Verifying Telegram API fix...")
print("=" * 60)

try:
    from bot_services import BotServiceFactory
    
    print("1. Creating Telegram service...")
    service = BotServiceFactory.create_service('telegram', {
        'token': '123:ABC',  # Invalid token for testing
        'name': 'TestBot'
    })
    
    print("2. Testing send_message method...")
    try:
        # This should fail with Telegram API error (invalid token)
        # NOT with "chat_id is not defined" error
        result = service.send_message(
            message="Test message",
            recipient="123456789"
        )
        
        print(f"   Result: {result}")
        
        if result.get('error', '').lower().find('chat_id') != -1:
            print("   ❌ STILL HAS 'chat_id' ERROR IN RESULT!")
        else:
            print("   ✅ No 'chat_id' error in result")
            
    except NameError as e:
        if 'chat_id' in str(e):
            print(f"   ❌ NAME ERROR: chat_id is not defined: {e}")
            print("   The fix didn't work!")
        else:
            print(f"   ❌ Different NameError: {e}")
    except Exception as e:
        print(f"   ✅ Different error (expected): {e}")
        
    print("\n3. Checking method implementation...")
    # Read the source code to check for chat_id references
    with open('bot_services.py', 'r') as f:
        content = f.read()
        
    # Find the TelegramBotService class
    import re
    telegram_class_match = re.search(r'class TelegramBotService.*?def send_message.*?\n.*?\n.*?\n', content, re.DOTALL)
    
    if telegram_class_match:
        method_text = telegram_class_match.group(0)
        
        # Check for undefined chat_id references
        lines = method_text.split('\n')
        for i, line in enumerate(lines, 1):
            if 'chat_id' in line and 'recipient' not in line and 'chat_id:' not in line:
                # Check if it's a variable reference (not a string or comment)
                if "'chat_id'" not in line and '"chat_id"' not in line and '# chat_id' not in line:
                    print(f"   ❌ Line {i} has potential chat_id reference: {line.strip()}")
    
    print("\n" + "=" * 60)
    print("If you see 'chat_id is not defined' error,")
    print("there are still references to chat_id variable")
    print("that need to be changed to recipient.")
    print("=" * 60)
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()