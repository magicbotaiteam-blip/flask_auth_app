# Telegram Bots Management and Management API

## 📋 Overview

A complete REST API for creating, managing, and interacting with Telegram bots through your Magic Bot AI Flask application.

## 🚀 Quick Start

### 1. **Integrate with Your Flask App**

Add this to your `app.py` or `app_fixed.py`:

```python
# Import the API modules
from telegram_bot_api import create_telegram_bot_api
from telegram_bot_api_part2 import create_telegram_bot_api_part2

# Initialize the APIs
create_telegram_bot_api(app)
create_telegram_bot_api_part2(app)
```

### 2. **Authentication**

All API endpoints require authentication. Users must be logged in via:
- Google OAuth
- Local username/password

## 📊 API Endpoints

### **1. Create a Telegram Bot**

```
POST /api/telegram/bot/create
```

**Request Body:**
```json
{
  "name": "My Assistant Bot",
  "token": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
  "description": "Customer support bot",
  "webhook_url": "https://yourdomain.com/webhook/telegram",
  "commands": [
    {"command": "start", "description": "Start the bot"},
    {"command": "help", "description": "Get help"}
  ],
  "tags": ["customer-support", "telegram"],
  "settings": {
    "auto_reply": true,
    "welcome_message": "Hello! How can I help?"
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Telegram bot created successfully",
  "bot_id": 5,
  "bot_info": {
    "id": 123456789,
    "username": "myassistant_bot",
    "first_name": "My Assistant Bot"
  }
}
```

### **2. Get Bot Details**

```
GET /api/telegram/bot/{bot_id}
```

**Response:**
```json
{
  "success": true,
  "bot": {
    "id": 5,
    "name": "My Assistant Bot",
    "token": "123...xyz",
    "messaging": "telegram",
    "config": {...}
  },
  "telegram_info": {
    "success": true,
    "bot_info": {...}
  },
  "analytics": [
    {"event_type": "bot_created", "count": 1},
    {"event_type": "message_sent", "count": 15}
  ]
}
```

### **3. Test Bot Connection**

```
POST /api/telegram/bot/{bot_id}/test
```

**Request Body (optional):**
```json
{
  "chat_id": "123456789",
  "message": "Custom test message"
}
```

**Response:**
```json
{
  "success": true,
  "bot_info": {...},
  "test_results": {
    "token_validation": {"success": true, ...},
    "tests": [
      {"name": "get_commands", "success": true, ...},
      {"name": "send_message", "success": true, ...}
    ]
  }
}
```

### **4. Send Message via Bot**

```
POST /api/telegram/bot/{bot_id}/send
```

**Request Body:**
```json
{
  "chat_id": "123456789",
  "message": "Hello from Magic Bot AI!",
  "parse_mode": "HTML",
  "disable_web_page_preview": false,
  "disable_notification": false
}
```

**Response:**
```json
{
  "success": true,
  "message_id": 123,
  "chat_id": "123456789",
  "timestamp": 1672531200
}
```

### **5. Get Bot Updates**

```
GET /api/telegram/bot/{bot_id}/updates?offset=123&limit=50
```

**Query Parameters:**
- `offset`: Last update ID + 1 (for pagination)
- `limit`: Max updates to return (1-100)

**Response:**
```json
{
  "success": true,
  "updates": [
    {
      "update_id": 123,
      "message": {
        "message_id": 456,
        "from": {...},
        "chat": {...},
        "text": "Hello bot!"
      }
    }
  ],
  "next_offset": 124
}
```

### **6. Manage Webhook**

**Set Webhook:**
```
POST /api/telegram/bot/{bot_id}/webhook
```
```json
{"url": "https://yourdomain.com/webhook/telegram"}
```

**Remove Webhook:**
```
DELETE /api/telegram/bot/{bot_id}/webhook
```

### **7. Get Bot Analytics**

```
GET /api/telegram/bot/{bot_id}/analytics?days=30&event_type=message_sent
```

**Query Parameters:**
- `days`: Time period in days (default: 7)
- `event_type`: Filter by event type

**Response:**
```json
{
  "success": true,
  "summary": {
    "total_events": 156,
    "unique_event_types": 5,
    "first_event": "2024-01-01 10:00:00",
    "last_event": "2024-01-07 15:30:00"
  },
  "analytics": [...],
  "event_distribution": [...]
}
```

### **8. Bot Templates**

**Get Templates:**
```
GET /api/telegram/bot/templates?public=true&category=customer-support
```

**Create Template:**
```
POST /api/telegram/bot/templates
```
```json
{
  "name": "Customer Support Bot",
  "description": "Template for customer support bots",
  "config": {
    "commands": [...],
    "settings": {...}
  },
  "category": "customer-support",
  "is_public": false,
  "tags": ["support", "telegram"]
}
```

## 🔧 Webhook Handler

### **Webhook Endpoint Example:**

```python
@app.route('/webhook/telegram/<token_hash>', methods=['POST'])
def telegram_webhook(token_hash):
    """Handle Telegram webhook updates"""
    
    # Find bot by token hash
    conn = get_db_connection()
    bot = conn.execute("""
        SELECT * FROM bots 
        WHERE token_hash = ? AND messaging = 'telegram'
    """, (token_hash,)).fetchone()
    conn.close()
    
    if not bot:
        return jsonify({"error": "Bot not found"}), 404
    
    update = request.json
    
    # Process different update types
    if 'message' in update:
        process_message(bot, update['message'])
    elif 'edited_message' in update:
        process_edited_message(bot, update['edited_message'])
    elif 'callback_query' in update:
        process_callback_query(bot, update['callback_query'])
    
    return jsonify({"status": "ok"}), 200

def process_message(bot, message):
    """Process incoming message"""
    chat_id = message['chat']['id']
    text = message.get('text', '')
    
    # Example: Echo bot
    if text:
        send_telegram_message(
            token=bot['token'],
            chat_id=chat_id,
            message=f"You said: {text}"
        )
    
    # Log analytics
    log_bot_event(bot['id'], 'message_received', {
        'chat_id': chat_id,
        'message_length': len(text),
        'has_entities': 'entities' in message
    })
```

## 📈 Analytics Events

The API automatically logs these events:

| Event Type | Description | Data |
|------------|-------------|------|
| `bot_created` | Bot created | `{bot_name, bot_username}` |
| `bot_updated` | Bot updated | `{updated_fields}` |
| `bot_tested` | Bot tested | `{tests_performed, success}` |
| `message_sent` | Message sent | `{chat_id, message_length, message_id}` |
| `message_received` | Message received | `{chat_id, message_length}` |
| `webhook_set` | Webhook set | `{webhook_url}` |
| `webhook_removed` | Webhook removed | `{}` |
| `updates_fetched` | Updates fetched | `{count, offset, limit}` |
| `chat_info_fetched` | Chat info fetched | `{chat_id}` |

## 🛡️ Security

### **Authentication:**
- All endpoints require user login
- Users can only access their own bots
- Token validation before bot creation

### **Token Security:**
- Bot tokens stored in database
- Never exposed in API responses
- Token validation via Telegram API

### **Rate Limiting:**
```python
from flask_limiter import Limiter

limiter = Limiter(app, key_func=lambda: session.get('user_id', 'anonymous'))

@app.route('/api/telegram/bot/<int:bot_id>/send', methods=['POST'])
@limiter.limit("10 per minute")
@login_required_api
def send_bot_message(bot_id):
    # ... implementation
```

## 🎯 Example Use Cases

### **1. Customer Support Bot**
```python
# Create support bot
response = requests.post('http://localhost:5000/api/telegram/bot/create', 
    json={
        "name": "Support Bot",
        "token": "YOUR_TOKEN",
        "commands": [
            {"command": "start", "description": "Start support"},
            {"command": "ticket", "description": "Create ticket"},
            {"command": "status", "description": "Check ticket status"}
        ],
        "settings": {
            "auto_reply": True,
            "business_hours": "9-5 Mon-Fri",
            "timezone": "America/New_York"
        }
    },
    headers={"Cookie": f"session={session_cookie}"}
)
```

### **2. Notification Bot**
```python
# Send notification
response = requests.post('http://localhost:5000/api/telegram/bot/5/send',
    json={
        "chat_id": "-1001234567890",  # Group chat ID
        "message": "🚨 *ALERT*: Server downtime scheduled\n\n*When*: Today 2-3 AM\n*Duration*: 1 hour\n*Impact*: Minimal",
        "parse_mode": "Markdown"
    },
    headers={"Cookie": f"session={session_cookie}"}
)
```

### **3. Analytics Dashboard**
```python
# Get bot analytics for dashboard
response = requests.get('http://localhost:5000/api/telegram/bot/5/analytics?days=30',
    headers={"Cookie": f"session={session_cookie}"}
)

analytics = response.json()
# Display charts showing:
# - Messages sent/received over time
# - Most active chats
# - Peak usage hours
# - Event distribution
```

## 🔄 Integration with Existing Features

### **With Bots Management UI:**
```html
<!-- In your Flask templates -->
<script>
// Create bot via API
async function createTelegramBot() {
    const response = await fetch('/api/telegram/bot/create', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            name: document.getElementById('bot-name').value,
            token: document.getElementById('bot-token').value,
            description: document.getElementById('bot-description').value
        })
    });
    
    const result = await response.json();
    if (result.success) {
        alert('Bot created successfully!');
        window.location.href = `/my-bots`;
    }
}
</script>
```

### **With Analytics Module:**
```python
# Combine with existing analytics
from analytics import get_analytics

def get_comprehensive_analytics(user_id):
    """Get combined analytics for all user bots"""
    conn = get_db_connection()
    
    # Get all user bots
    bots = conn.execute("""
        SELECT * FROM bots WHERE user_id = ?
    """, (user_id,)).fetchall()
    
    analytics = []
    for bot in bots:
        if bot['messaging'] == 'telegram':
            # Use Telegram API analytics
            bot_analytics = get_telegram_bot_analytics(bot['id'])
        else:
            # Use general analytics
            bot_analytics = get_analytics().get_bot_analytics(bot['id'])
        
        analytics.append({
            'bot_id': bot['id'],
            'bot_name': bot['name'],
            'analytics': bot_analytics
        })
    
    conn.close()
    return analytics
```

## 🚨 Error Handling

### **Common Errors:**

| Error Code | Description | Solution |
|------------|-------------|----------|
| `400` | Invalid request data | Check required fields |
| `401` | Authentication required | Login first |
| `403` | Access denied | Check bot ownership |
| `404` | Bot not found | Check bot ID |
| `429` | Rate limit exceeded | Wait and retry |
| `500` | Server error | Check server logs |

### **Telegram API Errors:**
- `401`: Unauthorized (invalid token)
- `400`: Bad request (invalid parameters)
- `429`: Too many requests (rate limit)

## 📋 API Testing

### **Using curl:**
```bash
# Create bot
curl -X POST http://localhost:5000/api/telegram/bot/create \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -d '{"name":"Test Bot","token":"YOUR_TOKEN"}'

# Send message
curl -X POST http://localhost:5000/api/telegram/bot/1/send \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -d '{"chat_id":"123456789","message":"Hello!"}'
```

### **Using Python:**
```python
import requests

# Login first (get session cookie)
session = requests.Session()
login_response = session.post('http://localhost:5000/signin_local',
    data={'username': 'test', 'password': 'test'}
)

# Create bot
bot_response = session.post('http://localhost:5000/api/telegram/bot/create',
    json={'name': 'Test Bot', 'token': 'YOUR_TOKEN'}
)
```

## 🎉 Next Steps

1. **Add more Telegram API methods:**
   - `sendPhoto`, `sendDocument`, `sendVideo`
   - `editMessageText`, `deleteMessage`
   - `getChatAdministrators`, `getChatMembersCount`

2. **Enhanced analytics:**
   - Real-time dashboard
   - Export to CSV/JSON
   - Predictive analytics

3. **Bot marketplace:**
   - Share/public bot templates
   - Bot ratings and reviews
   - One-click bot deployment

4. **Advanced features:**
   - Bot scheduling (send messages at specific times)
   - Chat automation (auto-reply rules)
   - Multi-language support
   - Integration with other services (CRM, Helpdesk)

## 📞 Support

For issues or questions:
1. Check the [Telegram Bot API documentation](https://core.telegram.org/bots/api)
2. Review error logs in Flask application
3. Test with valid bot token from @BotFather

---

**Happy bot building!** 🤖🚀