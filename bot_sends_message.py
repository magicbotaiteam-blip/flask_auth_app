#!/usr/bin/env python3
"""
Bot Sends Message (Right Side of Chat)
Makes the bot send a message to you (appears on right side of Telegram chat)
"""

import sys
import os
import sqlite3
import requests
import json
from datetime import datetime

def get_bot_token(bot_name='main'):
    """Get bot token from database"""
    if not os.path.exists('users.db'):
        print("❌ Database not found: users.db")
        return None
    
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
        return None
    
    bot = dict(bots[0])
    print(f"✅ Bot: {bot['name']}")
    print(f"✅ Token: {bot['token'][:15]}...")
    
    return bot['token']

def bot_sends_message(bot_token, chat_id, message_text=None):
    """
    Make the bot send a message to a user (appears on right side)
    
    Args:
        bot_token: Bot's Telegram token
        chat_id: User's chat ID (where bot sends message TO)
        message_text: Message text (defaults to timestamped message)
    """
    if not message_text:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        message_text = f"Message from bot at {timestamp}"
    
    api_url = f'https://api.telegram.org/bot{bot_token}'
    
    print(f"\n🤖 BOT sending message to user {chat_id}...")
    print(f"   Message: \"{message_text}\"")
    print(f"   (Will appear on RIGHT side of chat)")
    
    try:
        resp = requests.post(
            f'{api_url}/sendMessage',
            json={
                'chat_id': chat_id,
                'text': message_text,
                'parse_mode': 'HTML'
            },
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get('ok'):
                message_info = data['result']
                print(f"✅ Bot message sent successfully!")
                print(f"   Message ID: {message_info['message_id']}")
                print(f"   Chat: {message_info['chat']['id']}")
                print(f"   Date: {datetime.fromtimestamp(message_info['date']).strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"   From bot: {message_info['from']['first_name']}")
                return True
            else:
                print(f"❌ API error: {data.get('description')}")
        else:
            print(f"❌ HTTP error: {resp.status_code}")
            print(f"   Response: {resp.text[:200]}")
    except Exception as e:
        print(f"❌ Error sending message: {e}")
    
    return False

def test_both_directions(bot_token, chat_id):
    """Test both directions to show the difference"""
    print("\n" + "=" * 60)
    print("TESTING MESSAGE DIRECTIONS")
    print("=" * 60)
    
    # 1. User sends to bot (LEFT side)
    print("\n1️⃣ USER → BOT (Left side of chat):")
    print("   You send message to bot")
    print("   Appears on LEFT side")
    print("   Bot receives it")
    
    # 2. Bot sends to user (RIGHT side)  
    print("\n2️⃣ BOT → USER (Right side of chat):")
    print("   Bot sends message to you")
    print("   Appears on RIGHT side")
    print("   You receive it")
    
    # Actually send the bot message
    print("\n" + "=" * 60)
    print("ACTUALLY SENDING BOT MESSAGE...")
    print("=" * 60)
    
    success = bot_sends_message(bot_token, chat_id)
    
    return success

def main():
    """Main function"""
    print("=" * 60)
    print("BOT SENDS MESSAGE (Right Side of Chat)")
    print("=" * 60)
    
    # Get bot name from args or use default
    bot_name = 'main'
    if len(sys.argv) > 1:
        bot_name = sys.argv[1]
    
    # Get chat ID from args
    if len(sys.argv) > 2:
        chat_id = sys.argv[2]
    else:
        print("Usage: python3 bot_sends_message.py [bot_name] CHAT_ID [message]")
        print("\nExamples:")
        print("  python3 bot_sends_message.py main 8727217318")
        print("  python3 bot_sends_message.py chingtingshenbot 8727217318 \"Hello from bot!\"")
        print("\nAvailable bots from database:")
        
        # Show available bots
        if os.path.exists('users.db'):
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            cursor.execute("SELECT name, token FROM bots WHERE token IS NOT NULL")
            bots = cursor.fetchall()
            conn.close()
            
            for name, token in bots:
                print(f"  • {name} - Token: {token[:15]}...")
        return
    
    # Get message text if provided
    message_text = sys.argv[3] if len(sys.argv) > 3 else None
    
    # Get bot token
    bot_token = get_bot_token(bot_name)
    if not bot_token:
        return
    
    # Test both directions first
    test_both_directions(bot_token, chat_id)
    
    # Send actual message if custom text provided
    if message_text:
        print("\n" + "=" * 60)
        print("SENDING CUSTOM MESSAGE...")
        print("=" * 60)
        bot_sends_message(bot_token, chat_id, message_text)
    
    print("\n" + "=" * 60)
    print("✅ COMPLETE")
    print("=" * 60)
    
    print("\n📋 What happened:")
    print("   1. Bot sent a message TO your chat ID")
    print("   2. Message appears on RIGHT side of Telegram")
    print("   3. Looks like the bot is talking to you")
    
    print("\n🔧 Technical details:")
    print(f"   Bot: {bot_name}")
    print(f"   Your chat ID: {chat_id}")
    print(f"   Direction: Bot → User")
    print(f"   API: sendMessage (bot token used for authentication)")

if __name__ == "__main__":
    main()