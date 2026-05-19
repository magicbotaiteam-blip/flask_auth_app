#!/usr/bin/env python3
"""
Bot Sends Message via Service (Right Side)
Uses TelegramBotService to make bot send message (appears on right side)
"""

import sys
import os
import sqlite3
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

def main():
    """Bot sends message using TelegramBotService"""
    
    # Check arguments
    if len(sys.argv) < 3:
        print("Usage: python3 bot_sends_via_service.py BOT_NAME CHAT_ID [MESSAGE]")
        print("\nExamples:")
        print("  python3 bot_sends_via_service.py main 8727217318")
        print("  python3 bot_sends_via_service.py chingtingshenbot 8727217318 \"Hello!\"")
        print("\nThis makes the BOT send a message to YOU (right side of chat)")
        return
    
    bot_name = sys.argv[1]
    chat_id = sys.argv[2]
    message_text = sys.argv[3] if len(sys.argv) > 3 else None
    
    if not message_text:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        message_text = f"Message from {bot_name} bot at {timestamp}"
    
    print("=" * 60)
    print(f"BOT SENDS MESSAGE (Right Side)")
    print(f"Bot: {bot_name} → User: {chat_id}")
    print("=" * 60)
    
    # Step 1: Load bot config
    if not os.path.exists('users.db'):
        print("❌ Database not found: users.db")
        return
    
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    
    bots = conn.execute("""
        SELECT token, name FROM bots 
        WHERE name = ? 
        AND token IS NOT NULL 
        LIMIT 1
    """, (bot_name,)).fetchall()
    
    conn.close()
    
    if not bots:
        print(f"❌ Bot '{bot_name}' not found in database")
        
        # Show available bots
        print("\nAvailable bots:")
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM bots WHERE token IS NOT NULL")
        available = cursor.fetchall()
        conn.close()
        
        for (name,) in available:
            print(f"  • {name}")
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
            print(f"✅ Bot will appear as: {bot_info['first_name']}")
        else:
            print(f"⚠️  Could not get bot info: {info_result.get('error')}")
    except:
        print("⚠️  Could not get bot info")
    
    # Step 4: Send message FROM bot TO user
    print(f"\n🤖 BOT sending to user {chat_id}...")
    print(f"   Message: \"{message_text}\"")
    print(f"   (Will appear on RIGHT side of Telegram chat)")
    
    try:
        result = service.send_message(message_text, chat_id)
        
        if result.get('success'):
            print(f"✅ Bot message sent successfully!")
            print(f"   Message ID: {result.get('message_id')}")
            print(f"   Direction: Bot → User")
            print(f"   Position: Right side of chat box")
            
            # Show timestamp if available
            if result.get('timestamp'):
                ts = datetime.fromtimestamp(result['timestamp'])
                print(f"   Time: {ts.strftime('%H:%M:%S')}")
        else:
            print(f"❌ Failed: {result.get('error')}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("MESSAGE DIRECTION EXPLANATION")
    print("=" * 60)
    
    print("\n📱 In Telegram chat with bot:")
    print("   LEFT SIDE (←): Messages YOU send TO bot")
    print("   RIGHT SIDE (→): Messages bot sends TO YOU")
    
    print("\n🔧 What just happened:")
    print(f"   1. {bot_name} bot authenticated with its token")
    print(f"   2. Bot sent message TO your chat ID ({chat_id})")
    print(f"   3. Message appears on RIGHT side (from bot)")
    print(f"   4. You receive it as if bot is talking to you")
    
    print("\n✅ COMPLETE - Check your Telegram!")

if __name__ == "__main__":
    main()