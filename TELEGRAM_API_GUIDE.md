# Telegram Bot API Guide for Magic Bot AI

## 📋 Table of Contents
1. [Telegram Bot API Overview](#telegram-bot-api-overview)
2. [Available Methods in Your Implementation](#available-methods-in-your-implementation)
3. [How to Use the API](#how-to-use-the-api)
4. [API Endpoints in Your Flask App](#api-endpoints-in-your-flask-app)
5. [Examples & Code Snippets](#examples--code-snippets)
6. [Webhook Setup](#webhook-setup)
7. [Testing Your Bot](#testing-your-bot)

## Telegram Bot API Overview

Telegram Bot API allows you to create and manage bots that can:
- Send and receive messages
- Manage groups and channels
- Send files, photos, videos
- Create inline keyboards and buttons
- Set up webhooks for real-time updates

**Base URL:** `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/`

## Available Methods in Your Implementation

Your `bot_services.py` file implements these Telegram Bot API methods:

### 1. **Core Methods**
- `send_message()` - Send text messages to users/groups
- `get_bot_info()` - Get bot information (username, ID, etc.)
- `get_updates()` - Get recent messages/updates
- `set_webhook()` - Configure webhook for real-time updates
- `delete_webhook()` - Remove webhook configuration
- `get_webhook_info()` - Get current webhook status

### 2. **Message Methods**
- `send_message()` - Send text with optional formatting
- `edit_message_text()` - Edit sent messages
- `delete_message()` - Delete messages
- `forward_message()` - Forward messages between chats

### 3. **Chat Methods**
- `get_chat()` - Get chat information
- `get_chat_administrators()` - Get chat admins
- `get_chat_members_count()` - Get member count
- `leave_chat()` - Bot leaves a chat

### 4. **File Methods**
- `send_photo()` - Send photos
- `send_document()` - Send documents
- `send_video()` - Send videos
- `send_audio()` - Send audio files
- `send_voice()` - Send voice messages

## How to Use the API

### 1. **Import and Initialize**

```python
from bot_services import BotServiceFactory

# Create Telegram bot service
bot_config = {
    'token': 'YOUR_BOT_TOKEN_HERE',
    'name': 'MyBot',
    'platform': 'telegram'
}

telegram_service = BotServiceFactory.create_service('telegram', bot_config)
```

### 2. **Basic Operations**

```python
# Test connection
result = telegram_service.test_connection()
print(f"Connection test: {result}")

# Get bot info
bot_info = telegram_service.get_bot_info()
print(f"Bot username: {bot_info['bot_info']['username']}")

# Send a message
message_result = telegram_service.send_message(
    message="Hello from Magic Bot AI!",
    recipient="CHAT_ID_OR_USERNAME"
)
```

### 3. **Using the Factory Pattern**

```python
from bot_services import BotServiceFactory, test_bot_connection, send_bot_message

# Test any bot connection
test_result = test_bot_connection('telegram', 'YOUR_BOT_TOKEN')
print(test_result)

# Send message directly
send_result = send_bot_message(
    platform='telegram',
    token='YOUR_BOT_TOKEN',
    message='Test message',
    recipient='CHAT_ID'
)
```

## API Endpoints in Your Flask App

Your enhanced Flask application (`app_fixed.py`, `app_complete_final.py`) provides these API endpoints:

### 1. **Test Bot Connection**
```
GET /api/bot/<bot_id>/test
```
**Response:**
```json
{
  "success": true,
  "bot_info": {
    "id": 123456789,
    "username": "MyBot",
    "first_name": "My Bot"
  },
  "platform": "telegram"
}
```

### 2. **Get Bot Analytics** (if analytics module is available)
```
GET /api/bot/<bot_id>/analytics
```

### 3. **Log Bot Event** (if analytics module is available)
```
POST /api/bot/<bot_id>/log-event
```
**Payload:**
```json
{
  "event_type": "message_sent",
  "event_data": {"recipient": "12345", "message_length": 50}
}
```

## Examples & Code Snippets

### Example 1: Complete Telegram Bot Integration

```python
import json
from bot_services import TelegramBotService

class MyTelegramBot:
    def __init__(self, token):
        self.service = TelegramBotService({
            'token': token,
            'name': 'MyAssistantBot'
        })
    
    def handle_updates(self):
        """Poll for new messages"""
        updates = self.service.get_updates()
        if updates['success']:
            for update in updates['updates']:
                self.process_update(update)
    
    def process_update(self, update):
        """Process incoming message"""
        if 'message' in update:
            message = update['message']
            chat_id = message['chat']['id']
            text = message.get('text', '')
            
            # Echo back the message
            if text:
                self.service.send_message(
                    message=f"You said: {text}",
                    recipient=chat_id
                )
    
    def broadcast_message(self, message, chat_ids):
        """Send message to multiple chats"""
        results = []
        for chat_id in chat_ids:
            result = self.service.send_message(message, chat_id)
            results.append(result)
        return results
```

### Example 2: Webhook Handler for Flask

```python
from flask import Flask, request, jsonify

app = Flask(__name__)
telegram_service = None  # Initialize with your bot token

@app.route('/webhook/telegram/<bot_token>', methods=['POST'])
def telegram_webhook(bot_token):
    """Handle Telegram webhook updates"""
    update = request.json
    
    if 'message' in update:
        message = update['message']
        chat_id = message['chat']['id']
        text = message.get('text', '')
        
        # Process commands
        if text.startswith('/'):
            command = text.split()[0]
            
            if command == '/start':
                response = "Welcome to Magic Bot AI Bot! 🤖"
            elif command == '/help':
                response = "Available commands: /start, /help, /status"
            elif command == '/status':
                bot_info = telegram_service.get_bot_info()
                response = f"Bot status: {bot_info['bot_info']['username']} is online!"
            else:
                response = "Unknown command. Try /help"
            
            # Send response
            telegram_service.send_message(response, chat_id)
    
    return jsonify({'status': 'ok'}), 200
```

### Example 3: Advanced Message Features

```python
# Send message with Markdown formatting
telegram_service.send_message(
    message="*Bold text* and _italic text_",
    recipient="CHAT_ID",
    parse_mode="Markdown"
)

# Send message with HTML formatting
telegram_service.send_message(
    message="<b>Bold</b> and <i>italic</i> text",
    recipient="CHAT_ID",
    parse_mode="HTML"
)

# Send message with reply keyboard
telegram_service.send_message(
    message="Choose an option:",
    recipient="CHAT_ID",
    reply_markup={
        'keyboard': [
            ['Option 1', 'Option 2'],
            ['Option 3', 'Cancel']
        ],
        'resize_keyboard': True,
        'one_time_keyboard': True
    }
)

# Send photo
telegram_service.send_photo(
    photo_url="https://example.com/image.jpg",
    caption="Here's an image!",
    recipient="CHAT_ID"
)
```

## Webhook Setup

### 1. **Set Up Webhook with Your Bot**

```python
# In your Flask app initialization
WEBHOOK_URL = "https://yourdomain.com/webhook/telegram/YOUR_BOT_TOKEN"

# Set webhook
result = telegram_service.set_webhook(WEBHOOK_URL)
if result['success']:
    print("Webhook set successfully!")
else:
    print(f"Failed to set webhook: {result['error']}")
```

### 2. **Webhook Handler Implementation**

```python
@app.route('/webhook/telegram/<bot_token>', methods=['POST'])
def handle_telegram_webhook(bot_token):
    # Verify bot token matches
    if bot_token != EXPECTED_TOKEN:
        return jsonify({'error': 'Invalid token'}), 403
    
    update = request.json
    
    # Process the update
    process_telegram_update(update)
    
    return jsonify({'status': 'ok'}), 200

def process_telegram_update(update):
    """Process Telegram webhook update"""
    # Your logic here
    pass
```

### 3. **Webhook Security**

```python
import hashlib
import hmac

def verify_telegram_webhook(request, bot_token):
    """Verify Telegram webhook signature"""
    # Telegram sends updates with secret token verification
    # You can add additional security checks here
    return True  # Implement proper verification
```

## Testing Your Bot

### 1. **Quick Test Script**

Create `test_telegram_bot.py`:

```python
#!/usr/bin/env python3
"""Test Telegram bot integration"""

import sys
sys.path.insert(0, '.')

from bot_services import test_bot_connection, send_bot_message

# Your bot token (get from @BotFather)
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
TEST_CHAT_ID = "YOUR_CHAT_ID"  # Get your chat ID from @userinfobot

print("Testing Telegram Bot API...")
print("=" * 60)

# Test connection
print("1. Testing connection...")
result = test_bot_connection('telegram', BOT_TOKEN)
print(f"   Result: {result}")

# Send test message
print("\n2. Sending test message...")
if result.get('success'):
    send_result = send_bot_message(
        platform='telegram',
        token=BOT_TOKEN,
        message='🚀 Magic Bot AI Bot is working!',
        recipient=TEST_CHAT_ID
    )
    print(f"   Send result: {send_result}")
else:
    print("   Cannot send message - connection failed")

print("\n" + "=" * 60)
print("Done!")
```

### 2. **Using Your Flask App's API**

```bash
# Test via your Flask app API
curl "http://localhost:5000/api/bot/1/test"
```

### 3. **Direct API Testing with curl**

```bash
# Get bot info directly from Telegram API
curl "https://api.telegram.org/botYOUR_BOT_TOKEN/getMe"

# Send message via Telegram API
curl -X POST "https://api.telegram.org/botYOUR_BOT_TOKEN/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": "YOUR_CHAT_ID",
    "text": "Hello from curl!",
    "parse_mode": "Markdown"
  }'
```

## Common Bot Token Formats

Telegram bot tokens look like:
- `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`
- Always starts with numbers, then colon, then 35-character string

## Getting Started with a New Bot

1. **Create a new bot:**
   - Message @BotFather on Telegram
   - Send `/newbot` command
   - Choose a name and username
   - Save the bot token

2. **Get your chat ID:**
   - Message @userinfobot on Telegram
   - It will reply with your chat ID

3. **Test your bot:**
   - Send `/start` to your bot
   - Use the test scripts above

## Troubleshooting

### Common Issues:

1. **"Bot token is invalid"**
   - Check token format
   - Regenerate token from @BotFather

2. **"Chat not found"**
   - Make sure bot has messaged the chat first
   - Check chat ID format

3. **"Message is too long"**
   - Telegram limits: 4096 characters per message
   - Split long messages

4. **"Too many requests"**
   - Telegram rate limit: ~30 messages/second
   - Add delays between messages

### Debug Tips:

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Check API response details
response = telegram_service.get_bot_info()
print(f"Full response: {json.dumps(response, indent=2)}")
```

## Next Steps

1. **Integrate with your Flask app** - Use the existing API endpoints
2. **Add more features** - Implement more Telegram API methods
3. **Create a dashboard** - Monitor bot activity and analytics
4. **Set up webhooks** - For real-time message processing
5. **Add authentication** - Secure your bot endpoints

## Resources

- [Official Telegram Bot API Documentation](https://core.telegram.org/bots/api)
- [BotFather (@BotFather)](https://t.me/botfather) - Create/manage bots
- [User Info Bot (@userinfobot)](https://t.me/userinfobot) - Get your chat ID
- [Magic Bot AI Documentation](../README_ENHANCED.md)

---

**Need help?** Check your `bot_services.py` for the complete implementation or run the test scripts to verify everything works! 🚀