#!/usr/bin/env python3
"""
Reset Bot Polling State
Clears the update offset so bot can receive messages again
"""

import sys
import os
import sqlite3
import requests
sys.path.insert(0, os.path.dirname(__file__))

def reset_bot_state():
    print("=" * 60)
    print("Reset Bot Polling State")
    print("Clears update offset to receive all messages again")
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
    print(f"✅ Token: {token[:10]}...")
    
    # Step 1: Get current webhook info
    print("\n1. Checking webhook status...")
    try:
        resp = requests.get(f'{api_url}/getWebhookInfo', timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('ok'):
                info = data['result']
                if info.get('url'):
                    print(f"   ⚠️  Webhook is SET to: {info['url']}")
                    print("   This could interfere with polling.")
                    
                    # Ask about deleting webhook
                    print("\n   Delete webhook for polling? (y/n): ", end="")
                    choice = input().strip().lower()
                    if choice == 'y':
                        resp2 = requests.get(f'{api_url}/deleteWebhook', timeout=5)
                        if resp2.status_code == 200:
                            data2 = resp2.json()
                            if data2.get('ok'):
                                print("   ✅ Webhook deleted")
                            else:
                                print(f"   ❌ Error: {data2.get('description')}")
                        else:
                            print(f"   ❌ HTTP error: {resp2.status_code}")
                else:
                    print("   ✅ No webhook set (good for polling)")
            else:
                print(f"   ❌ Error: {data.get('description')}")
        else:
            print(f"   ❌ HTTP error: {resp.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Step 2: Get current updates (to see offset)
    print("\n2. Checking current updates state...")
    try:
        resp = requests.get(f'{api_url}/getUpdates', params={'limit': 1}, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('ok'):
                updates = data['result']
                if updates:
                    print(f"   📍 Current update ID: {updates[0]['update_id']}")
                    print("   (Bot will receive messages AFTER this ID)")
                else:
                    print("   ℹ️  No recent updates")
                    print("   (Bot will receive ALL messages)")
            else:
                print(f"   ❌ Error: {data.get('description')}")
        else:
            print(f"   ❌ HTTP error: {resp.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Step 3: Reset by getting updates with offset=0
    print("\n3. Resetting polling state...")
    print("   Getting updates with offset=0 to acknowledge all...")
    
    try:
        # Get ALL pending updates to clear them
        resp = requests.get(f'{api_url}/getUpdates', params={'offset': 0, 'limit': 100}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('ok'):
                updates = data['result']
                print(f"   ✅ Acknowledged {len(updates)} pending update(s)")
                
                if updates:
                    print("   Cleared messages:")
                    for update in updates:
                        if 'message' in update:
                            msg = update['message']
                            sender = msg['from'].get('first_name', 'Unknown')
                            text = msg.get('text', '[no text]')[:40]
                            print(f"     👤 {sender}: {text}...")
            else:
                print(f"   ❌ Error: {data.get('description')}")
        else:
            print(f"   ❌ HTTP error: {resp.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Step 4: Test fresh state
    print("\n4. Testing fresh state...")
    print("   Please message your bot NOW (@nb_openclaw_ssy_bot)")
    print("   I'll check if it's received...")
    
    import time
    start_time = time.time()
    message_received = False
    
    while time.time() - start_time < 20 and not message_received:
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
                        
                        print(f"\n   🎉 SUCCESS! Message received:")
                        print(f"   👤 From: {sender}")
                        print(f"   💬 Text: {text}")
                        print(f"   📍 Update ID: {update['update_id']}")
        except:
            pass
        
        time.sleep(1)
    
    if not message_received:
        print("\n   ⏰ Timeout - No message received")
        print("\n   Please make sure:")
        print("   1. You're messaging @nb_openclaw_ssy_bot")
        print("   2. The bot is active (not banned/disabled)")
        print("   3. You have internet connection")
    
    print("\n" + "=" * 60)
    print("✅ Reset complete!")
    print("\n📋 Next steps:")
    print("1. Message your bot to test")
    print("2. Run ONLY ONE test script at a time")
    print("3. If bot doesn't reply, check its auto-reply configuration")
    print("=" * 60)

if __name__ == "__main__":
    reset_bot_state()