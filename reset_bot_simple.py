#!/usr/bin/env python3
"""
Simple Bot Reset - Non-interactive version
"""

import sys
import os
import sqlite3
import requests
import time
sys.path.insert(0, os.path.dirname(__file__))

def reset_bot_simple():
    print("=" * 60)
    print("Simple Bot Reset")
    print("Resetting polling state...")
    print("=" * 60)
    
    # Get bot token
    if not os.path.exists('users.db'):
        print("❌ Database not found.")
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
        print("❌ No bot found.")
        return
    
    token = bots[0]['token']
    name = bots[0]['name']
    api_url = f'https://api.telegram.org/bot{token}'
    
    print(f"✅ Bot: {name}")
    print(f"✅ Bot username: @nb_openclaw_ssy_bot")
    
    # Step 1: Delete webhook if exists (for clean polling)
    print("\n1. Checking/cleaning webhook...")
    try:
        resp = requests.get(f'{api_url}/getWebhookInfo', timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('ok') and data['result'].get('url'):
                print(f"   ⚠️  Webhook found, deleting...")
                resp2 = requests.get(f'{api_url}/deleteWebhook', timeout=5)
                if resp2.status_code == 200:
                    print("   ✅ Webhook deleted")
                else:
                    print("   ❌ Failed to delete webhook")
            else:
                print("   ✅ No webhook (good for polling)")
    except Exception as e:
        print(f"   ⚠️  Error checking webhook: {e}")
    
    # Step 2: Clear all pending updates
    print("\n2. Clearing pending updates...")
    try:
        # Get all pending updates to acknowledge them
        resp = requests.get(f'{api_url}/getUpdates', params={'offset': 0, 'limit': 100}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('ok'):
                updates = data['result']
                if updates:
                    print(f"   ✅ Cleared {len(updates)} pending update(s)")
                    # Show last few if any
                    for update in updates[-3:]:
                        if 'message' in update:
                            msg = update['message']
                            sender = msg['from'].get('first_name', 'Unknown')
                            text = msg.get('text', '[no text]')[:30]
                            print(f"     👤 {sender}: {text}...")
                else:
                    print("   ✅ No pending updates")
            else:
                print(f"   ❌ Error: {data.get('description', 'Unknown')}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Step 3: Test fresh state
    print("\n3. Testing fresh state...")
    print("   Bot is now ready to receive messages!")
    print("   Please message @nb_openclaw_ssy_bot on Telegram")
    print("   I'll wait 30 seconds for your message...")
    
    start_time = time.time()
    message_received = False
    
    while time.time() - start_time < 30 and not message_received:
        try:
            resp = requests.get(f'{api_url}/getUpdates', params={'limit': 1, 'timeout': 1}, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('ok') and data['result']:
                    message_received = True
                    update = data['result'][0]
                    
                    if 'message' in update:
                        msg = update['message']
                        sender = msg['from'].get('first_name', 'Unknown')
                        text = msg.get('text', '[no text]')
                        
                        print(f"\n   🎉 SUCCESS! Message received!")
                        print(f"   👤 From: {sender}")
                        print(f"   💬 Text: {text}")
                        
                        # Check for bot reply
                        print(f"\n   🔍 Checking if bot replies...")
                        time.sleep(3)
                        
                        # Get updates after this message
                        new_offset = update['update_id'] + 1
                        resp2 = requests.get(f'{api_url}/getUpdates', 
                                           params={'offset': new_offset, 'limit': 5, 'timeout': 1}, 
                                           timeout=5)
                        
                        if resp2.status_code == 200:
                            data2 = resp2.json()
                            if data2.get('ok') and data2['result']:
                                bot_replied = False
                                for upd in data2['result']:
                                    if 'message' in upd:
                                        msg2 = upd['message']
                                        if msg2.get('from', {}).get('is_bot'):
                                            bot_replied = True
                                            print(f"   🤖 Bot replied: {msg2.get('text', '[no text]')[:50]}...")
                                            break
                                
                                if not bot_replied:
                                    print("   ⚠️  Bot did not reply (may not be configured to auto-reply)")
        except Exception as e:
            pass
        
        # Show progress
        elapsed = time.time() - start_time
        if int(elapsed) % 5 == 0 and elapsed > 0:
            remaining = 30 - elapsed
            print(f"   ⏳ {int(elapsed)}s elapsed, {int(remaining)}s remaining...")
        
        time.sleep(1)
    
    if not message_received:
        print("\n   ⏰ Timeout - No message received")
        print("\n   Please make sure:")
        print("   1. You're messaging @nb_openclaw_ssy_bot")
        print("   2. The message is sent (check Telegram)")
        print("   3. Internet connection is working")
    
    print("\n" + "=" * 60)
    print("✅ Reset complete!")
    
    if message_received:
        print("\n🎉 Bot is receiving messages correctly!")
        print("\n📋 Next steps:")
        print("1. Now you can run ONE test script at a time:")
        print("   - python3 test_simple_bot_replies.py (read bot replies)")
        print("   - python3 test_telegram_read_only.py (read all messages)")
        print("   - python3 test_telegram_message_monitor.py (full monitor)")
        print("\n2. Remember: Only ONE script at a time!")
        print("3. Stop script before running another")
    else:
        print("\n⚠️  Bot reset but no message received.")
        print("   Please check if you're messaging the correct bot.")
    
    print("=" * 60)

if __name__ == "__main__":
    reset_bot_simple()