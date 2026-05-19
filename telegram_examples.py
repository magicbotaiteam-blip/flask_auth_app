#!/usr/bin/env python3
"""
Practical Telegram Bot API Examples for Magic Bot AI
Shows how to use the API with your actual bot data
"""

import sys
import os
import sqlite3
sys.path.insert(0, os.path.dirname(__file__))

from bot_services import BotServiceFactory, test_bot_connection, send_bot_message

def get_bots_from_database():
    """Get all Telegram bots from your database"""
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    
    bots = conn.execute("""
        SELECT id, name, token, messaging, description 
        FROM bots 
        WHERE (messaging = 'telegram' OR messaging = 'Telegram') AND name = 'main' AND token IS NOT NULL AND token != ''
    """).fetchall()
    
    conn.close()
    return bots


def example_2_send_messages():
    """Example 2: Sending Different Types of Messages"""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Sending Messages")
    print("=" * 60)
    
    bots = get_bots_from_database()
    if not bots:
        return
    
    bot = bots[0]
    telegram_service = BotServiceFactory.create_service('telegram', {
        'token': bot['token'],
        'name': bot['name']
    })
    
    # Note: To send messages, you need a valid chat_id
    # Get this from recent updates or hardcode for testing
    TEST_CHAT_ID = None  # Replace with actual chat ID
    
    if not TEST_CHAT_ID:
        print("⚠️  No TEST_CHAT_ID set. Getting from recent updates...")
        updates = telegram_service.get_updates(limit=1, timeout=1)
        if updates.get('success') and updates['updates']:
            TEST_CHAT_ID = updates['updates'][0]['message']['chat']['id']
            print(f"   Using chat ID: {TEST_CHAT_ID}")
        else:
            print("   ❌ No recent messages found. Cannot send test message.")
            print("   Message your bot first, then run this example again.")
            return
    
    print(f"\nSending test messages to chat ID: {TEST_CHAT_ID}")
    
    # 1. Send simple text message
    print("\n1. Sending simple text message...")
    result = telegram_service.send_message(
        message="Hello from Magic Bot AI! 👋",
        recipient=TEST_CHAT_ID
    )
    print(f"   Result: {'✅ Success' if result.get('success') else '❌ Failed'}")
    if not result.get('success'):
        print(f"   Error: {result.get('error')}")
    
    # 2. Send message with Markdown formatting
    print("\n2. Sending Markdown formatted message...")
    result = telegram_service.send_message(
        message="*Bold text* and _italic text_\n`code format`",
        recipient=TEST_CHAT_ID,
        parse_mode="Markdown"
    )
    print(f"   Result: {'✅ Success' if result.get('success') else '❌ Failed'}")
    
    # 3. Send message with HTML formatting
    print("\n3. Sending HTML formatted message...")
    result = telegram_service.send_message(
        message="<b>Bold</b> and <i>italic</i> text\n<code>code format</code>",
        recipient=TEST_CHAT_ID,
        parse_mode="HTML"
    )
    print(f"   Result: {'✅ Success' if result.get('success') else '❌ Failed'}")
    
    print("\n" + "=" * 60)

def main():
    """Run all examples"""
    print("Telegram Bot API Examples for Magic Bot AI")
    print("=" * 60)
    
    # Check if bot_services module is available
    try:
        from bot_services import BotServiceFactory
        print("✅ bot_services module loaded successfully")
    except ImportError as e:
        print(f"❌ Error: {e}")
        print("Make sure bot_services.py is in the same directory")
        return
    
    # Check database
    if not os.path.exists('users.db'):
        print("❌ Database not found: users.db")
        print("Run your Flask app first to create the database")
        return
    
    # Run examples
    example_2_send_messages()
    
    print("\n🎉 Examples completed!")
    print("\nNext steps:")
    print("1. Add a Telegram bot via your Flask web interface")
    print("2. Message your bot to get a chat ID")
    print("3. Run the examples again to test sending messages")
    print("4. Check the TELEGRAM_API_GUIDE.md for complete documentation")

if __name__ == "__main__":
    main()
