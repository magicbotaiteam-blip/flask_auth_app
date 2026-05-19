#!/usr/bin/env python3
"""
Test Telegram Service Send Message
Uses telegram_service.send_message to send one message at a time to the 'main' bot
"""

import sys
import os
import sqlite3
import json
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

def load_main_bot_config():
    """Load the 'main' bot configuration from database"""
    if not os.path.exists('users.db'):
        print("❌ Database not found: users.db")
        return None
    
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    
    bots = conn.execute("""
        SELECT token, name, webhook_url FROM bots 
        WHERE name = 'main' 
        AND token IS NOT NULL 
        LIMIT 1
    """).fetchall()
    
    conn.close()
    
    if not bots:
        print("❌ 'main' bot not found in database")
        return None
    
    bot = dict(bots[0])
    print(f"✅ Bot: {bot['name']}")
    print(f"✅ Token: {bot['token'][:15]}...")
    
    if bot.get('webhook_url'):
        print(f"✅ Webhook URL: {bot['webhook_url']}")
    else:
        print("⚠️  No webhook URL configured")
    
    return bot

def create_telegram_service(bot_config):
    """Create a TelegramBotService instance"""
    try:
        # Import the TelegramBotService class
        from bot_services import TelegramBotService
        
        # Create service instance
        service = TelegramBotService(bot_config)
        print("✅ TelegramBotService created successfully")
        return service
    except ImportError as e:
        print(f"❌ Could not import TelegramBotService: {e}")
        print("   Make sure bot_services.py is in the current directory")
        return None
    except Exception as e:
        print(f"❌ Error creating TelegramBotService: {e}")
        return None

def test_bot_info(service):
    """Test getting bot information"""
    print("\n🔍 Testing bot info...")
    
    try:
        result = service.get_bot_info()
        
        if result.get('success'):
            bot_info = result['bot_info']
            print(f"✅ Bot username: @{bot_info['username']}")
            print(f"✅ Bot ID: {bot_info['id']}")
            print(f"✅ Bot name: {bot_info['first_name']}")
            return bot_info
        else:
            print(f"❌ Failed to get bot info: {result.get('error')}")
            return None
    except Exception as e:
        print(f"❌ Error getting bot info: {e}")
        return None

def send_single_message(service, chat_id, message_text=None):
    """
    Send a single message using telegram_service.send_message
    
    Args:
        service: TelegramBotService instance
        chat_id: Telegram chat ID to send to
        message_text: Optional message text (defaults to timestamped test message)
    """
    if not message_text:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        message_text = f"Test message via TelegramBotService at {timestamp}"
    
    print(f"\n📤 Sending message to chat ID {chat_id}...")
    print(f"   Message: \"{message_text}\"")
    
    try:
        # Use the send_message method
        result = service.send_message(message_text, str(chat_id))
        
        if result.get('success'):
            print(f"✅ Message sent successfully!")
            print(f"   Message ID: {result.get('message_id')}")
            print(f"   Chat ID: {result.get('chat_id')}")
            if result.get('timestamp'):
                ts = datetime.fromtimestamp(result['timestamp'])
                print(f"   Timestamp: {ts.strftime('%Y-%m-%d %H:%M:%S')}")
            return result
        else:
            print(f"❌ Failed to send message: {result.get('error')}")
            return result
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return {'success': False, 'error': str(e)}

def test_webhook_status(service):
    """Test webhook status"""
    print("\n🔍 Checking webhook status...")
    
    try:
        # Check if service has get_webhook_info method
        if hasattr(service, 'get_webhook_info'):
            result = service.get_webhook_info()
            if result.get('success'):
                info = result.get('webhook_info', {})
                print(f"✅ Webhook URL: {info.get('url', 'Not set')}")
                print(f"✅ Pending updates: {info.get('pending_update_count', 0)}")
            else:
                print(f"⚠️  Could not get webhook info: {result.get('error')}")
        else:
            print("⚠️  Service doesn't have get_webhook_info method")
    except Exception as e:
        print(f"⚠️  Error checking webhook: {e}")

def interactive_send_mode(service, default_chat_id=None):
    """Interactive mode for sending multiple messages"""
    print("\n" + "=" * 60)
    print("INTERACTIVE SEND MODE")
    print("=" * 60)
    
    chat_id = default_chat_id
    
    if not chat_id:
        chat_id_input = input("Enter chat ID (or press Enter to skip): ").strip()
        if chat_id_input:
            try:
                chat_id = int(chat_id_input)
                print(f"✅ Using chat ID: {chat_id}")
            except ValueError:
                print("⚠️  Invalid chat ID, skipping interactive mode")
                return
    
    if not chat_id:
        print("⚠️  No chat ID provided, skipping interactive mode")
        return
    
    message_count = 0
    
    while True:
        print(f"\n--- Message {message_count + 1} ---")
        print("Options:")
        print("  1. Send default test message")
        print("  2. Enter custom message")
        print("  3. Exit")
        
        choice = input("\nSelect option (1-3): ").strip()
        
        if choice == '1':
            # Send default test message
            send_single_message(service, chat_id)
            message_count += 1
            
        elif choice == '2':
            # Send custom message
            custom_msg = input("Enter message: ").strip()
            if custom_msg:
                send_single_message(service, chat_id, custom_msg)
                message_count += 1
            else:
                print("⚠️  Message cannot be empty")
                
        elif choice == '3':
            print(f"\n📊 Sent {message_count} message(s)")
            break
            
        else:
            print("⚠️  Invalid choice, please enter 1, 2, or 3")

def main():
    """Main function"""
    print("=" * 60)
    print("TELEGRAM SERVICE SEND MESSAGE TEST")
    print("Uses telegram_service.send_message for 'main' bot")
    print("=" * 60)
    
    # Step 1: Load main bot config
    bot_config = load_main_bot_config()
    if not bot_config:
        return
    
    # Step 2: Create Telegram service
    service = create_telegram_service(bot_config)
    if not service:
        return
    
    # Step 3: Test bot info
    bot_info = test_bot_info(service)
    if not bot_info:
        print("⚠️  Could not get bot info, but continuing...")
    
    # Step 4: Check webhook status
    test_webhook_status(service)
    
    # Step 5: Check for chat ID argument
    chat_id = None
    if len(sys.argv) > 1:
        try:
            chat_id = int(sys.argv[1])
            print(f"\n✅ Using provided chat ID: {chat_id}")
            
            # Send a test message
            result = send_single_message(service, chat_id)
            
            # Save result
            if result:
                filename = f"telegram_service_sent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(filename, 'w') as f:
                    json.dump(result, f, indent=2)
                print(f"📄 Result saved to: {filename}")
                
        except ValueError:
            print(f"⚠️  Invalid chat ID: {sys.argv[1]}")
    
    # Step 6: Offer interactive mode
    print("\n" + "=" * 60)
    if chat_id:
        use_interactive = input("Enter interactive mode? (y/n): ").strip().lower()
        if use_interactive == 'y':
            interactive_send_mode(service, chat_id)
    else:
        print("No chat ID provided. You can:")
        print("  1. Run with chat ID: python3 test_telegram_service_send.py CHAT_ID")
        print("  2. Use interactive mode without sending")
        use_interactive = input("\nEnter interactive mode? (y/n): ").strip().lower()
        if use_interactive == 'y':
            interactive_send_mode(service)
    
    print("\n" + "=" * 60)
    print("✅ TELEGRAM SERVICE TEST COMPLETE")
    print("=" * 60)
    
    print("\n📋 Summary:")
    print(f"   Bot: {bot_config['name']}")
    print(f"   Bot username: @{bot_info['username'] if bot_info else 'Unknown'}")
    print(f"   Service: TelegramBotService")
    print(f"   Method used: service.send_message()")
    
    print("\n🔧 For production use:")
    print("   1. Import TelegramBotService from bot_services")
    print("   2. Create service with bot config")
    print("   3. Call service.send_message(text, chat_id)")

if __name__ == "__main__":
    main()