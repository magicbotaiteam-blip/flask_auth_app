#!/usr/bin/env python3
"""
Quick Bot Message Check
Checks if bot has received any user messages
"""

import os
import sqlite3
import requests
import json
from datetime import datetime

def check_bot_messages():
    print("=" * 60)
    print("QUICK BOT MESSAGE CHECK")
    print("Checks if bot received user messages (LEFT side)")
    print("=" * 60)
    
    # Load first bot
    if not os.path.exists('users.db'):
        print("❌ Database not found")
        return
    
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    
    bots = conn.execute("""
        SELECT token, name FROM bots 
        WHERE (messaging = 'telegram' OR messaging = 'Telegram')
        AND token IS NOT NULL LIMIT 1
    """).fetchall()
    
    conn.close()
    
    if not bots:
        print("❌ No bots found")
        return
    
    bot = dict(bots[0])
    print(f"✅ Checking bot: {bot['name']}")
    
    # Check getUpdates
    api_url = f'https://api.telegram.org/bot{bot["token"]}'
    
    try:
        resp = requests.get(f'{api_url}/getUpdates', timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('ok'):
                updates = data['result']
                
                if not updates:
                    print("\n📭 No messages received yet")
                    print("💡 To test:")
                    print("   1. Open Telegram")
                    print("   2. Message @nb_openclaw_ssy_bot")
                    print("   3. Run this script again")
                    print("   4. Should see your messages here")
                else:
                    print(f"\n✅ Bot has received {len(updates)} message(s)")
                    
                    user_messages = 0
                    bot_messages = 0
                    
                    for i, update in enumerate(updates):
                        if 'message' in update:
                            msg = update['message']
                            sender = msg.get('from', {})
                            is_bot = sender.get('is_bot', False)
                            text = msg.get('text', '[no text]')
                            timestamp = datetime.fromtimestamp(msg.get('date')).strftime('%H:%M:%S')
                            
                            if is_bot:
                                bot_messages += 1
                                print(f"   [{timestamp}] 🤖 {sender.get('first_name', 'Bot')}: {text[:50]}")
                            else:
                                user_messages += 1
                                print(f"   [{timestamp}] 👤 {sender.get('first_name', 'User')}: {text[:50]}")
                    
                    print(f"\n📊 Summary:")
                    print(f"   • User messages: {user_messages} (← LEFT side)")
                    print(f"   • Bot messages: {bot_messages} (→ RIGHT side)")
                    
                    if user_messages == 0:
                        print("\n⚠️  No user messages found")
                        print("   All messages are from bots")
                        print("   💡 Send a message FROM YOUR Telegram account TO the bot")
            else:
                print(f"❌ API error: {data.get('description')}")
        else:
            print(f"❌ HTTP error: {resp.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("MESSAGE DIRECTION REMINDER:")
    print("=" * 60)
    
    print("\n📱 In Telegram chat:")
    print("   ← LEFT: Messages YOU send TO bot")
    print("   → RIGHT: Messages bot sends TO YOU")
    
    print("\n🔧 What this script checks:")
    print("   • Messages on LEFT side (user → bot)")
    print("   • Shows if bot has received user messages")
    
    print("\n✅ To test properly:")
    print("   1. Open Telegram app (on your phone)")
    print("   2. Find @nb_openclaw_ssy_bot")
    print("   3. Send 'Hello' or 'Test'")
    print("   4. Run this script again")
    print("   5. Should see your message above")

if __name__ == "__main__":
    check_bot_messages()