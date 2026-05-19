#!/usr/bin/env python3
"""
Test User to Bot Message Flow
Helps test user messages (left side) being sent to bot
"""

import sys
import os
import sqlite3
import json
from datetime import datetime

print("=" * 60)
print("USER → BOT MESSAGE TESTING")
print("(Messages appear on LEFT side of chat)")
print("=" * 60)

def show_message_flow():
    """Show the message flow diagram"""
    print("\n📱 TELEGRAM CHAT LAYOUT:")
    print("   ┌─────────────────────────────────┐")
    print("   │                                 │")
    print("   │  YOU: Hello bot!          ←    │  (LEFT side)")
    print("   │                                 │")
    print("   │  Bot: Hi there!           →    │  (RIGHT side)")
    print("   │                                 │")
    print("   └─────────────────────────────────┘")
    
    print("\n🔀 MESSAGE DIRECTIONS:")
    print("   ← LEFT SIDE:  User → Bot (YOU send TO bot)")
    print("   → RIGHT SIDE: Bot → User (bot sends TO YOU)")

def check_bot_status():
    """Check if bot is ready to receive messages"""
    print("\n🔍 CHECKING BOT STATUS...")
    
    if not os.path.exists('users.db'):
        print("❌ Database not found: users.db")
        return None
    
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    
    # Get all Telegram bots
    bots = conn.execute("""
        SELECT name, token, webhook_url FROM bots 
        WHERE (messaging = 'telegram' OR messaging = 'Telegram')
        AND token IS NOT NULL
    """).fetchall()
    
    conn.close()
    
    if not bots:
        print("❌ No Telegram bots found in database")
        return None
    
    print(f"✅ Found {len(bots)} Telegram bot(s):")
    
    bot_info_list = []
    for i, bot in enumerate(bots):
        bot_dict = dict(bot)
        print(f"\n   {i+1}. {bot_dict['name']}")
        print(f"      Token: {bot_dict['token'][:15]}...")
        
        # Try to get bot username from Telegram API
        import requests
        api_url = f'https://api.telegram.org/bot{bot_dict["token"]}'
        try:
            resp = requests.get(f'{api_url}/getMe', timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('ok'):
                    username = data['result']['username']
                    print(f"      Username: @{username}")
                    bot_dict['username'] = username
                else:
                    print(f"      ❌ API error: {data.get('description')}")
            else:
                print(f"      ❌ HTTP error: {resp.status_code}")
        except:
            print(f"      ⚠️  Could not reach bot API")
        
        if bot_dict.get('webhook_url'):
            print(f"      Webhook: {bot_dict['webhook_url']}")
        
        bot_info_list.append(bot_dict)
    
    return bot_info_list

def test_methods():
    """Different methods to test user→bot messages"""
    print("\n" + "=" * 60)
    print("TEST METHODS FOR USER → BOT MESSAGES")
    print("=" * 60)
    
    methods = [
        {
            "name": "Manual Send (Recommended)",
            "steps": [
                "1. Open Telegram app",
                "2. Search for bot username",
                "3. Send message",
                "4. Check bot receives it"
            ],
            "pros": "Real user experience, 100% accurate",
            "cons": "Manual work"
        },
        {
            "name": "Bot API getUpdates Check",
            "steps": [
                "1. Send message manually",
                "2. Run script to check getUpdates",
                "3. Verify message appears in updates"
            ],
            "pros": "Automated verification",
            "cons": "Requires manual send first"
        },
        {
            "name": "Webhook Testing",
            "steps": [
                "1. Set up webhook endpoint",
                "2. Send message manually",
                "3. Check webhook receives POST"
            ],
            "pros": "Tests real integration",
            "cons": "Requires webhook setup"
        },
        {
            "name": "Simulated Testing",
            "steps": [
                "1. Create test message JSON",
                "2. POST to webhook endpoint",
                "3. Verify processing"
            ],
            "pros": "No Telegram API needed",
            "cons": "Not real Telegram message"
        }
    ]
    
    for i, method in enumerate(methods, 1):
        print(f"\n{i}. {method['name']}:")
        for step in method['steps']:
            print(f"   {step}")
        print(f"   ✅ Pros: {method['pros']}")
        print(f"   ❌ Cons: {method['cons']}")

def create_test_plan(bot_info):
    """Create a test plan for user→bot messages"""
    print("\n" + "=" * 60)
    print("CREATING TEST PLAN")
    print("=" * 60)
    
    test_plan = {
        "objective": "Test user messages (left side) to bot",
        "test_date": datetime.now().isoformat(),
        "bots": bot_info,
        "test_steps": [
            "1. Choose a bot from the list above",
            "2. Note its username (e.g., @nb_openclaw_ssy_bot)",
            "3. Open Telegram and message that bot",
            "4. Send test messages: 'Hello', 'Test', '/start'",
            "5. Check if bot receives messages (via logs/webhook)",
            "6. Check if bot replies (right side messages)"
        ],
        "test_messages": [
            "Hello bot!",
            "Test message 1",
            "Can you help me?",
            "/start",
            datetime.now().strftime("Test at %H:%M:%S")
        ],
        "verification_methods": [
            "Check OpenClaw agent console for received messages",
            "Check bot logs for incoming messages",
            "Check webhook endpoint logs",
            "Check database for stored messages"
        ],
        "expected_results": [
            "Bot receives user messages",
            "Messages appear in logs/database",
            "Bot processes messages (optional)",
            "Bot sends replies (if configured)"
        ]
    }
    
    filename = f"user_to_bot_test_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(test_plan, f, indent=2)
    
    print(f"✅ Test plan saved to: {filename}")
    
    return filename

def quick_test_script():
    """Create a quick test script to check if bot received messages"""
    script_content = '''#!/usr/bin/env python3
"""
Quick Bot Message Check
Checks if bot has received any user messages
"""

import os
import sqlite3
import requests
import json

def check_bot_messages():
    print("=" * 60)
    print("QUICK BOT MESSAGE CHECK")
    print("Checks if bot received user messages")
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
                    print("📭 No messages received yet")
                    print("💡 Message the bot to test!")
                else:
                    print(f"✅ Bot has received {len(updates)} message(s)")
                    
                    user_messages = 0
                    for update in updates:
                        if 'message' in update:
                            msg = update['message']
                            if not msg.get('from', {}).get('is_bot', False):
                                user_messages += 1
                                user = msg['from']
                                text = msg.get('text', '[no text]')[:50]
                                print(f"   👤 {user.get('first_name', 'User')}: {text}")
                    
                    if user_messages == 0:
                        print("⚠️  Messages found, but all from bots (not users)")
            else:
                print(f"❌ API error: {data.get('description')}")
        else:
            print(f"❌ HTTP error: {resp.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("INSTRUCTIONS:")
    print("1. Message the bot on Telegram")
    print("2. Run this script again")
    print("3. Should see your messages above")
    print("=" * 60)

if __name__ == "__main__":
    check_bot_messages()
'''
    
    filename = "check_bot_messages.py"
    with open(filename, 'w') as f:
        f.write(script_content)
    
    print(f"✅ Quick check script created: {filename}")
    print(f"   Run: python3 {filename}")
    
    return filename

def main():
    """Main function"""
    # Show message flow
    show_message_flow()
    
    # Check bot status
    bot_info = check_bot_status()
    if not bot_info:
        return
    
    # Show test methods
    test_methods()
    
    # Create test plan
    test_plan_file = create_test_plan(bot_info)
    
    # Create quick test script
    check_script = quick_test_script()
    
    print("\n" + "=" * 60)
    print("🎯 RECOMMENDED APPROACH")
    print("=" * 60)
    
    print("\n1. MANUAL TEST (Easiest):")
    print("   • Open Telegram")
    print("   • Message @nb_openclaw_ssy_bot")
    print("   • Check if bot receives it")
    
    print("\n2. VERIFY WITH SCRIPT:")
    print(f"   • Run: python3 {check_script}")
    print("   • Should show your messages")
    
    print("\n3. CHECK OPENCLAW:")
    print("   • Monitor OpenClaw agent console")
    print("   • Check for 'received message' logs")
    
    print(f"\n📋 Full test plan: {test_plan_file}")
    print(f"🔧 Quick check: python3 {check_script}")
    
    print("\n" + "=" * 60)
    print("READY TO TEST USER → BOT MESSAGES!")
    print("=" * 60)

if __name__ == "__main__":
    main()