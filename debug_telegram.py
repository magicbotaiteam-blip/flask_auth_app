#!/usr/bin/env python3
"""
Debug script to find where 'chat_id' error is coming from
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

print("DEBUG: Finding 'chat_id is not defined' error")
print("=" * 60)

# Monkey-patch the TelegramBotService to add debugging
import bot_services

original_send_message = None

def debug_send_message(self, message, recipient, **kwargs):
    print(f"DEBUG: send_message called with recipient={recipient}")
    print(f"DEBUG: Checking for chat_id references in this method...")
    
    # Get the source code of this method
    import inspect
    source = inspect.getsource(self.send_message)
    
    # Check for chat_id variable references (not in strings or comments)
    lines = source.split('\n')
    for i, line in enumerate(lines, 1):
        if 'chat_id' in line:
            # Check if it's a variable reference
            if not ("'chat_id'" in line or '"chat_id"' in line or '# chat_id' in line):
                print(f"DEBUG: Line {i} has chat_id variable: {line.strip()}")
    
    # Call original method
    return original_send_message(self, message, recipient, **kwargs)

# Replace the method
for attr_name in dir(bot_services):
    attr = getattr(bot_services, attr_name)
    if hasattr(attr, '__name__') and attr.__name__ == 'TelegramBotService':
        original_send_message = attr.send_message
        attr.send_message = debug_send_message
        print(f"DEBUG: Patched TelegramBotService.send_message")
        break

# Now run a test
from bot_services import BotServiceFactory

print("\n" + "=" * 60)
print("Running test...")
print("=" * 60)

try:
    service = BotServiceFactory.create_service('telegram', {
        'token': 'test',
        'name': 'Test'
    })
    
    result = service.send_message('test', '123')
    print(f"Result: {result}")
    
except Exception as e:
    print(f"Exception: {e}")
    import traceback
    print("\nFull traceback:")
    traceback.print_exc()

print("\n" + "=" * 60)
print("DEBUG complete")
print("=" * 60)