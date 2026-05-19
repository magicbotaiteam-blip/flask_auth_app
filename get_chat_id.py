#!/usr/bin/env python3
"""
Get Chat ID for Telegram Bot
Helps you find your chat ID to send test messages
"""

import os
import sqlite3
import requests
import json

def get_bot_token():
    """Get bot token from database"""
    if not os.path.exists('users.db'):
        print("❌ Database not found: users.db")
        return None
    
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    
    bots = conn.execute("""
        SELECT token, name FROM bots 
        WHERE (messaging = 'telegram' OR messaging = 'Telegram')
        AND name='main' 
        AND token IS NOT NULL LIMIT 1
    """).fetchall()
    
    conn.close()
    
    if not bots:
        print("❌ No Telegram bots found in database")
        return None
    
    bot = dict(bots[0])
    print(f"✅ Bot: {bot['name']}")
    print(f"✅ Token: {bot['token'][:15]}...")
    
    return bot['token']

def method_1_get_updates(bot_token):
    """Method 1: Get updates to find chat IDs"""
    print("\n🔍 METHOD 1: Checking for recent messages...")
    
    api_url = f'https://api.telegram.org/bot{bot_token}'
    
    try:
        resp = requests.get(f'{api_url}/getUpdates', timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('ok'):
                updates = data['result']
                
                if not updates:
                    print("   📭 No messages received yet")
                    print("   💡 Message the bot (@nb_openclaw_ssy_bot) first!")
                    return None
                
                print(f"   ✅ Found {len(updates)} message(s)")
                
                for i, update in enumerate(updates):
                    if 'message' in update:
                        msg = update['message']
                        chat = msg['chat']
                        user = msg['from']
                        
                        print(f"\n   📨 Message {i+1}:")
                        print(f"      Chat ID: {chat['id']}")
                        print(f"      Chat type: {chat['type']}")
                        print(f"      From: {user.get('first_name', 'Unknown')}")
                        if user.get('username'):
                            print(f"      Username: @{user['username']}")
                        if msg.get('text'):
                            print(f"      Text: {msg['text'][:50]}...")
                        
                        # Return first user chat ID
                        if not user.get('is_bot', False):
                            return chat['id']
                
                print("\n   ⚠️  No user messages found (only bot messages)")
                return None
            else:
                print(f"   ❌ API error: {data.get('description')}")
        else:
            print(f"   ❌ HTTP error: {resp.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    return None

def method_2_manual_chat_id():
    """Method 2: Manual chat ID entry"""
    print("\n🔍 METHOD 2: Manual chat ID")
    print("   To find your chat ID:")
    print("   1. Message @userinfobot on Telegram")
    print("   2. It will reply with your chat ID")
    print("   3. Or message your bot and check logs")
    
    chat_id = input("\n   Enter chat ID (or press Enter to skip): ").strip()
    if chat_id and chat_id.isdigit() or (chat_id.startswith('-') and chat_id[1:].isdigit()):
        return int(chat_id)
    
    return None

def method_3_test_send(bot_token, test_chat_id=None):
    """Method 3: Test sending to a chat ID"""
    print("\n🔍 METHOD 3: Test sending")
    
    if not test_chat_id:
        print("   No chat ID to test")
        return None
    
    api_url = f'https://api.telegram.org/bot{bot_token}'
    
    print(f"   Testing chat ID: {test_chat_id}")
    
    try:
        resp = requests.post(
            f'{api_url}/sendMessage',
            json={
                'chat_id': test_chat_id,
                'text': 'Test message to verify chat ID',
                'parse_mode': 'HTML'
            },
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get('ok'):
                print(f"   ✅ Message sent successfully!")
                print(f"   ✅ Chat ID {test_chat_id} is valid")
                return test_chat_id
            else:
                print(f"   ❌ API error: {data.get('description')}")
        else:
            print(f"   ❌ HTTP error: {resp.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    return None

def main():
    """Main function"""
    print("=" * 60)
    print("GET TELEGRAM CHAT ID")
    print("=" * 60)
    
    # Get bot token
    bot_token = get_bot_token()
    if not bot_token:
        return
    
    # Method 1: Get updates
    chat_id = method_1_get_updates(bot_token)
    
    # Method 2: Manual entry if needed
    if not chat_id:
        chat_id = method_2_manual_chat_id()
    
    # Method 3: Test the chat ID
    if chat_id:
        valid = method_3_test_send(bot_token, chat_id)
        if valid:
            print(f"\n✅ Your chat ID is: {chat_id}")
            print(f"\n📋 Use this in send_one_message.py:")
            print(f"   python3 send_one_message.py {chat_id}")
            
            # Save to file
            with open('telegram_chat_id.txt', 'w') as f:
                f.write(str(chat_id))
            print(f"   📄 Saved to: telegram_chat_id.txt")
        else:
            print(f"\n❌ Chat ID {chat_id} is not valid")
    else:
        print("\n❌ Could not find a valid chat ID")
        print("\n📋 Next steps:")
        print("   1. Message @nb_openclaw_ssy_bot on Telegram")
        print("   2. Run this script again")
        print("   3. Or message @userinfobot to get your chat ID")
    
    print("\n" + "=" * 60)
    print("CHAT ID FINDER COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
