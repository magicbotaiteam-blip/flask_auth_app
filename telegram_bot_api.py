"""
Complete Telegram Bots Management and Management API
For Magic Bot AI Flask Application
"""

from flask import Flask, request, jsonify, session
from functools import wraps
import sqlite3
from pathlib import Path
import os
import requests
import json
from typing import Dict, Any, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_FILENAME = Path(__file__).parent / "users.db"

# ==================== Database Functions ====================

def get_db_connection():
    """Get database connection with retry logic for locks"""
    import sqlite3
    max_retries = 3
    retry_delay = 0.1  # seconds
    
    for attempt in range(max_retries):
        try:
            # Add timeout to handle database locks
            conn = sqlite3.connect('users.db', timeout=10)
            conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")
            # Set busy timeout
            conn.execute("PRAGMA busy_timeout = 5000")
            return conn
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < max_retries - 1:
                import time
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                continue
            raise
    # This should never be reached due to the raise above
    raise sqlite3.OperationalError("Failed to connect to database after retries")

def init_db():
    """Initialize database tables for bot management"""
    conn = get_db_connection()
    
    # Create bot_templates table if it doesn't exist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bot_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            config TEXT NOT NULL,
            category TEXT,
            is_public BOOLEAN DEFAULT FALSE,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            usage_count INTEGER DEFAULT 0,
            tags TEXT,
            FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE SET NULL
        )
    """)
    
    # Create bot_analytics table if it doesn't exist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bot_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            event_data TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (bot_id) REFERENCES bots (id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()

init_db()

# ==================== Authentication Decorator ====================

def login_required_api(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function

# ==================== Telegram Bot API Helper Functions ====================

class TelegramBotAPI:
    """Helper class for Telegram Bot API operations"""
    
    BASE_URL = "https://api.telegram.org/bot"
    
    @staticmethod
    def create_bot_via_botfather(token: str) -> Dict[str, Any]:
        """
        Note: BotFather API is not publicly available.
        Users must create bots manually via @BotFather.
        This function provides instructions instead.
        """
        return {
            "success": True,
            "message": "To create a Telegram bot, follow these steps:",
            "instructions": [
                "1. Open Telegram and search for @BotFather",
                "2. Send /newbot command",
                "3. Choose a name for your bot",
                "4. Choose a username (must end with 'bot')",
                "5. Save the bot token provided by BotFather",
                "6. Use the token in the /api/bot/create endpoint"
            ],
            "note": "Bot creation must be done manually via @BotFather"
        }
    
    @staticmethod
    def validate_bot_token(token: str) -> Dict[str, Any]:
        """Validate a Telegram bot token by calling getMe API"""
        try:
            response = requests.get(
                f"{TelegramBotAPI.BASE_URL}{token}/getMe",
                timeout=10
            )
            result = response.json()
            
            if result.get('ok'):
                return {
                    "success": True,
                    "bot_info": result['result'],
                    "message": "Bot token is valid"
                }
            else:
                return {
                    "success": False,
                    "error": result.get('description', 'Invalid token'),
                    "error_code": result.get('error_code')
                }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Network error: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Validation error: {str(e)}"
            }
    
    @staticmethod
    def set_bot_commands(token: str, commands: list) -> Dict[str, Any]:
        """Set bot commands via Telegram API"""
        try:
            response = requests.post(
                f"{TelegramBotAPI.BASE_URL}{token}/setMyCommands",
                json={"commands": commands},
                timeout=10
            )
            result = response.json()
            
            if result.get('ok'):
                return {
                    "success": True,
                    "message": "Bot commands set successfully"
                }
            else:
                return {
                    "success": False,
                    "error": result.get('description', 'Failed to set commands')
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to set commands: {str(e)}"
            }
    
    @staticmethod
    def set_webhook(token: str, webhook_url: str) -> Dict[str, Any]:
        """Set webhook for Telegram bot"""
        try:
            response = requests.post(
                f"{TelegramBotAPI.BASE_URL}{token}/setWebhook",
                json={"url": webhook_url},
                timeout=10
            )
            result = response.json()
            
            if result.get('ok'):
                return {
                    "success": True,
                    "message": "Webhook set successfully"
                }
            else:
                return {
                    "success": False,
                    "error": result.get('description', 'Failed to set webhook')
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to set webhook: {str(e)}"
            }
    
    @staticmethod
    def get_bot_commands(token: str) -> Dict[str, Any]:
        """Get current bot commands"""
        try:
            response = requests.get(
                f"{TelegramBotAPI.BASE_URL}{token}/getMyCommands",
                timeout=10
            )
            result = response.json()
            
            if result.get('ok'):
                return {
                    "success": True,
                    "commands": result.get('result', [])
                }
            else:
                return {
                    "success": False,
                    "error": result.get('description', 'Failed to get commands')
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get commands: {str(e)}"
            }

# ==================== Flask API Endpoints ====================

def create_telegram_bot_api(app):
    """
    Create and register Telegram bot API endpoints with Flask app
    """
    
    @app.route('/api/telegram/bot/create', methods=['POST'])
    @login_required_api
    def create_telegram_bot():
        """
        Create a new Telegram bot entry in database
        Requires manual bot creation via @BotFather first
        """
        user_id = session["user_id"]
        data = request.json
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Required fields
        required_fields = ['name', 'token']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Validate bot token
        validation_result = TelegramBotAPI.validate_bot_token(data['token'])
        if not validation_result.get('success'):
            return jsonify({
                "error": "Invalid bot token",
                "details": validation_result.get('error')
            }), 400
        
        bot_info = validation_result['bot_info']
        
        # Prepare bot configuration
        bot_config = {
            "name": data['name'],
            "token": data['token'],
            "username": bot_info.get('username'),
            "bot_id": bot_info.get('id'),
            "can_join_groups": bot_info.get('can_join_groups', False),
            "can_read_all_group_messages": bot_info.get('can_read_all_group_messages', False),
            "supports_inline_queries": bot_info.get('supports_inline_queries', False),
            "description": data.get('description', ''),
            "webhook_url": data.get('webhook_url', ''),
            "commands": data.get('commands', []),
            "tags": data.get('tags', []),
            "settings": data.get('settings', {})
        }
        
        conn = get_db_connection()
        
        try:
            # Insert into bots table and capture cursor
            cursor = conn.execute("""
                INSERT INTO bots (
                    user_id, name, email, organization, messaging, token, llm,
                    description, webhook_url, api_key, config, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                data['name'],
                data.get('email', ''),
                data.get('organization', ''),
                'telegram',
                data['token'],
                data.get('llm', ''),
                data.get('description', ''),
                data.get('webhook_url', ''),
                '',  # api_key (not used for Telegram)
                json.dumps(bot_config),
                ','.join(data.get('tags', []))
            ))
            
            # Get the last insert ID from the cursor
            bot_id = cursor.lastrowid
            
            # Set default bot commands if provided
            if data.get('commands'):
                TelegramBotAPI.set_bot_commands(data['token'], data['commands'])
            
            # Set webhook if provided
            if data.get('webhook_url'):
                TelegramBotAPI.set_webhook(data['token'], data['webhook_url'])
            
            conn.commit()
            
            # Log analytics event
            conn.execute("""
                INSERT INTO bot_analytics (bot_id, event_type, event_data)
                VALUES (?, ?, ?)
            """, (
                bot_id,
                'bot_created',
                json.dumps({
                    'platform': 'telegram',
                    'bot_name': data['name'],
                    'bot_username': bot_info.get('username')
                })
            ))
            
            conn.commit()
            
            return jsonify({
                "success": True,
                "message": "Telegram bot created successfully",
                "bot_id": bot_id,
                "bot_info": bot_info,
                "config": bot_config
            }), 201
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error creating bot: {e}")
            return jsonify({
                "error": f"Failed to create bot: {str(e)}"
            }), 500
        finally:
            conn.close()
    
    @app.route('/api/telegram/bot/<int:bot_id>', methods=['GET'])
    @login_required_api
    def get_telegram_bot(bot_id):
        """Get Telegram bot details"""
        user_id = session["user_id"]
        
        conn = get_db_connection()
        bot = conn.execute("""
            SELECT * FROM bots 
            WHERE id = ? AND user_id = ? AND messaging = 'telegram'
        """, (bot_id, user_id)).fetchone()
        
        if not bot:
            conn.close()
            return jsonify({"error": "Bot not found"}), 404
        
        # Get bot info from Telegram API
        token = bot['token']
        bot_info = TelegramBotAPI.validate_bot_token(token)
        
        # Get analytics
        analytics = conn.execute("""
            SELECT event_type, COUNT(*) as count 
            FROM bot_analytics 
            WHERE bot_id = ? 
            GROUP BY event_type
        """, (bot_id,)).fetchall()
        
        conn.close()
        
        return jsonify({
            "success": True,
            "bot": dict(bot),
            "telegram_info": bot_info,
            "analytics": [dict(a) for a in analytics]
        })
    
    @app.route('/api/telegram/bot/<int:bot_id>/update', methods=['PUT'])
    @login_required_api
    def update_telegram_bot(bot_id):
        """Update Telegram bot settings"""
        user_id = session["user_id"]
        data = request.json
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        conn = get_db_connection()
        
        # Check bot ownership
        bot = conn.execute("""
            SELECT * FROM bots 
            WHERE id = ? AND user_id = ? AND messaging = 'telegram'
        """, (bot_id, user_id)).fetchone()
        
        if not bot:
            conn.close()
            return jsonify({"error": "Bot not found"}), 404
        
        # Parse existing config
        existing_config = json.loads(bot['config']) if bot['config'] else {}
        
        # Update config with new values
        updated_config = {**existing_config, **data.get('config', {})}
        
        # Update bot commands if provided
        if 'commands' in data:
            TelegramBotAPI.set_bot_commands(bot['token'], data['commands'])
            updated_config['commands'] = data['commands']
        
        # Update webhook if provided
        if 'webhook_url' in data:
            TelegramBotAPI.set_webhook(bot['token'], data['webhook_url'])
            updated_config['webhook_url'] = data['webhook_url']
        
        try:
            # Update database
            update_fields = []
            update_values = []
            
            if 'name' in data:
                update_fields.append("name = ?")
                update_values.append(data['name'])
            
            if 'description' in data:
                update_fields.append("description = ?")
                update_values.append(data['description'])
            
            if 'webhook_url' in data:
                update_fields.append("webhook_url = ?")
                update_values.append(data['webhook_url'])
            
            update_fields.append("config = ?")
            update_values.append(json.dumps(updated_config))
            
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            
            if update_fields:
                update_values.extend([bot_id, user_id])
                
                query = f"""
                    UPDATE bots 
                    SET {', '.join(update_fields)}
                    WHERE id = ? AND user_id = ?
                """
                
                conn.execute(query, update_values)
                
                # Log analytics event
                conn.execute("""
                    INSERT INTO bot_analytics (bot_id, event_type, event_data)
                    VALUES (?, ?, ?)
                """, (
                    bot_id,
                    'bot_updated',
                    json.dumps({
                        'updated_fields': list(data.keys()),
                        'platform': 'telegram'
                    })
                ))
                
                conn.commit()
            
            conn.close()
            
            return jsonify({
                "success": True,
                "message": "Bot updated successfully",
                "config": updated_config
            })
            
        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"Error updating bot: {e}")
            return jsonify({
                "error": f"Failed to update bot: {str(e)}"
            }), 500
    
    @app.route('/api/telegram/bot/<int:bot_id>/test', methods=['POST'])
    @login_required_api
    def test_telegram_bot(bot_id):
        """Test Telegram bot connection and send test message"""
        user_id = session["user_id"]
        data = request.json or {}
        
        conn = get_db_connection()
        bot = conn.execute("""
            SELECT * FROM bots 
            WHERE id = ? AND user_id = ? AND messaging = 'telegram'
        """, (bot_id, user_id)).fetchone()
        
        if not bot:
            conn.close()
            return jsonify({"error": "Bot not found"}), 404
        
        token = bot['token']
        
        # Test 1: Validate token
        validation_result = TelegramBotAPI.validate_bot_token(token)
        
        if not validation_result.get('success'):
            conn.close()
            return jsonify({
                "success": False,
                "error": "Bot token validation failed",
                "details": validation_result.get('error')
            }), 400
        
        results = {
            "token_validation": validation_result,
            "tests": []
        }
        
        # Test 2: Get bot commands
        commands_result = TelegramBotAPI.get_bot_commands(token)
        results["tests"].append({
            "name": "get_commands",
            "success": commands_result.get('success', False),
            "result": commands_result
        })
        
        # Test 3: Send test message (if chat_id provided)
        if 'chat_id' in data:
            try:
                response = requests.post(
                    f"{TelegramBotAPI.BASE_URL}{token}/sendMessage",
                    json={
                        "chat_id": data['chat_id'],
                        "text": data.get('message', '✅ Bot is working! Test message from Magic Bot AI.'),
                        "parse_mode": "HTML"
                    },
                    timeout=10
                )
                
                message_result = response.json()
                results["tests"].append({
                    "name": "send_message",
                    "success": message_result.get('ok', False),
                    "result": message_result
                })
            except Exception as e:
                results["tests"].append({
                    "name": "send_message",
                    "success": False,
                    "error": str(e)
                })
        
        # Log analytics event
        conn.execute("""
            INSERT INTO bot_analytics (bot_id, event_type, event_data)
            VALUES (?, ?, ?)
        """, (
            bot_id,
            'bot_tested',
            json.dumps({
                'tests_performed': [t['name'] for t in results['tests']],
                'success': all(t.get('success', False) for t in results['tests'])
            })
        ))
        
        conn.commit()
        conn.close()
        
        # Determine overall success
        all_success = all(t.get('success', False) for t in results['tests'])
        all_success = all_success and validation_result.get('success', False)
        
        return jsonify({
            "success": all_success,
            "bot_info": validation_result.get('bot_info'),
            "test_results": results
        })
    
    return app
