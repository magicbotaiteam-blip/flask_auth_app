#!/usr/bin/env python3
"""
Simple Telegram Service Send
Simple script to send one message using telegram_service.send_message
"""

import sys
import os
import sqlite3
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

def main():
    """Send one message using TelegramBotService"""
    
    # Check arguments
    if len(sys.argv) < 2:
        print("Usage: python3 simple_telegram_service_send.py CHAT_ID [MESSAGE]")
        print("\nExample:")
        print("  python3 simple_telegram_service_send.py 8727217318")
        print("  python3 simple_telegram_service_send.py 8727217318 \"Hello from service!\"")
        return
    
    chat_id = sys.argv[1]
    message_text = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not message_text:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        message_text = f"Test via TelegramBotService at {timestamp}"
    
    print("=" * 60)
    print("SIMPLE TELEGRAM SERVICE SEND")
    print("=" * 60)
    
    # Step 1: Load main bot config
    if not os.path.exists('users.db'):
        print("❌ Database not found: users.db")
        return
    
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    
    bots = conn.execute("""
        SELECT token, name FROM bots 
        WHERE name = 'main' 
        AND token IS NOT NULL 
        LIMIT 1
    """).fetchall()
    
    conn.close()
    
    if not bots:
        print("❌ 'main' bot not found in database")
        return
    
    bot_config = dict(bots[0])
    print(f"✅ Bot: {bot_config['name']}")
    print(f"✅ Token: {bot_config['token'][:15]}...")
    
    # Step 2: Import and create service
    try:
        from bot_services import TelegramBotService
        service = TelegramBotService(bot_config)
        print("✅ TelegramBotService created")
    except ImportError as e:
        print(f"❌ Could not import TelegramBotService: {e}")
        return
    except Exception as e:
        print(f"❌ Error creating service: {e}")
        return
    
    # Step 3: Get bot info
    try:
        info_result = service.get_bot_info()
        if info_result.get('success'):
            bot_info = info_result['bot_info']
            print(f"✅ Bot username: @{bot_info['username']}")
        else:
            print(f"⚠️  Could not get bot info: {info_result.get('error')}")
    except:
        print("⚠️  Could not get bot info")
    
    # Step 4: Send message
    print(f"\n📤 Sending to chat ID: {chat_id}")
    print(f"   Message: \"{message_text}\"")
    
    try:
        result = service.send_message(message_text, chat_id)
        
        if result.get('success'):
            print(f"✅ Message sent successfully!")
            print(f"   Message ID: {result.get('message_id')}")
            
            # Show timestamp if available
            if result.get('timestamp'):
                ts = datetime.fromtimestamp(result['timestamp'])
                print(f"   Time: {ts.strftime('%H:%M:%S')}")
        else:
            print(f"❌ Failed: {result.get('error')}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()