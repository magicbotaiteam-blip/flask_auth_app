"""
Telegram Bot API Part 2 - More endpoints
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

def login_required_api(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function

class TelegramBotManager:
    """Advanced Telegram bot management"""
    
    BASE_URL = "https://api.telegram.org/bot"
    
    @staticmethod
    def get_bot_updates(token: str, offset: Optional[int] = None, limit: int = 100) -> Dict[str, Any]:
        """Get recent updates for the bot"""
        try:
            params = {'limit': limit}
            if offset:
                params['offset'] = offset
            
            response = requests.get(
                f"{TelegramBotManager.BASE_URL}{token}/getUpdates",
                params=params,
                timeout=10
            )
            result = response.json()
            
            if result.get('ok'):
                return {
                    "success": True,
                    "updates": result['result'],
                    "next_offset": result['result'][-1]['update_id'] + 1 if result['result'] else offset
                }
            else:
                return {
                    "success": False,
                    "error": result.get('description', 'Failed to get updates')
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get updates: {str(e)}"
            }
    
    @staticmethod
    def send_message(token: str, chat_id: str, message: str, **kwargs) -> Dict[str, Any]:
        """Send message via Telegram bot"""
        try:
            payload = {
                "chat_id": chat_id,
                "text": message,
                **kwargs
            }
            
            response = requests.post(
                f"{TelegramBotManager.BASE_URL}{token}/sendMessage",
                json=payload,
                timeout=10
            )
            result = response.json()
            
            if result.get('ok'):
                return {
                    "success": True,
                    "message_id": result['result']['message_id'],
                    "chat_id": chat_id,
                    "timestamp": result['result']['date']
                }
            else:
                return {
                    "success": False,
                    "error": result.get('description', 'Failed to send message')
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to send message: {str(e)}"
            }
    
    @staticmethod
    def get_chat_info(token: str, chat_id: str) -> Dict[str, Any]:
        """Get chat information"""
        try:
            response = requests.get(
                f"{TelegramBotManager.BASE_URL}{token}/getChat",
                params={"chat_id": chat_id},
                timeout=10
            )
            result = response.json()
            
            if result.get('ok'):
                return {
                    "success": True,
                    "chat_info": result['result']
                }
            else:
                return {
                    "success": False,
                    "error": result.get('description', 'Failed to get chat info')
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get chat info: {str(e)}"
            }

def create_telegram_bot_api_part2(app):
    """
    More Telegram bot API endpoints
    """
    
    @app.route('/api/telegram/bot/<int:bot_id>/webhook', methods=['POST', 'DELETE'])
    @login_required_api
    def manage_telegram_webhook(bot_id):
        """Manage Telegram bot webhook"""
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
        
        if request.method == 'POST':
            # Set webhook
            webhook_url = data.get('url')
            if not webhook_url:
                conn.close()
                return jsonify({"error": "Webhook URL is required"}), 400
            
            try:
                response = requests.post(
                    f"{TelegramBotManager.BASE_URL}{token}/setWebhook",
                    json={"url": webhook_url},
                    timeout=10
                )
                result = response.json()
                
                if result.get('ok'):
                    # Update database
                    conn.execute("""
                        UPDATE bots 
                        SET webhook_url = ?, config = json_set(config, '$.webhook_url', ?)
                        WHERE id = ?
                    """, (webhook_url, webhook_url, bot_id))
                    
                    # Log analytics
                    conn.execute("""
                        INSERT INTO bot_analytics (bot_id, event_type, event_data)
                        VALUES (?, ?, ?)
                    """, (
                        bot_id,
                        'webhook_set',
                        json.dumps({'webhook_url': webhook_url})
                    ))
                    
                    conn.commit()
                    conn.close()
                    
                    return jsonify({
                        "success": True,
                        "message": "Webhook set successfully",
                        "webhook_url": webhook_url
                    })
                else:
                    conn.close()
                    return jsonify({
                        "success": False,
                        "error": result.get('description', 'Failed to set webhook')
                    }), 400
                    
            except Exception as e:
                conn.close()
                return jsonify({
                    "success": False,
                    "error": f"Failed to set webhook: {str(e)}"
                }), 500
        
        elif request.method == 'DELETE':
            # Delete webhook
            try:
                response = requests.post(
                    f"{TelegramBotManager.BASE_URL}{token}/deleteWebhook",
                    timeout=10
                )
                result = response.json()
                
                if result.get('ok'):
                    # Update database
                    conn.execute("""
                        UPDATE bots 
                        SET webhook_url = '', config = json_set(config, '$.webhook_url', '')
                        WHERE id = ?
                    """, (bot_id,))
                    
                    # Log analytics
                    conn.execute("""
                        INSERT INTO bot_analytics (bot_id, event_type, event_data)
                        VALUES (?, ?, ?)
                    """, (
                        bot_id,
                        'webhook_removed',
                        json.dumps({})
                    ))
                    
                    conn.commit()
                    conn.close()
                    
                    return jsonify({
                        "success": True,
                        "message": "Webhook removed successfully"
                    })
                else:
                    conn.close()
                    return jsonify({
                        "success": False,
                        "error": result.get('description', 'Failed to remove webhook')
                    }), 400
                    
            except Exception as e:
                conn.close()
                return jsonify({
                    "success": False,
                    "error": f"Failed to remove webhook: {str(e)}"
                }), 500
    
    @app.route('/api/telegram/bot/<int:bot_id>/updates', methods=['GET'])
    @login_required_api
    def get_bot_updates(bot_id):
        """Get recent updates for the bot"""
        user_id = session["user_id"]
        
        # Get query parameters
        offset = request.args.get('offset', type=int)
        limit = min(request.args.get('limit', 100, type=int), 100)
        
        conn = get_db_connection()
        bot = conn.execute("""
            SELECT * FROM bots 
            WHERE id = ? AND user_id = ? AND messaging = 'telegram'
        """, (bot_id, user_id)).fetchone()
        
        if not bot:
            conn.close()
            return jsonify({"error": "Bot not found"}), 404
        
        token = bot['token']
        
        # Get updates from Telegram API
        updates_result = TelegramBotManager.get_bot_updates(token, offset, limit)
        
        if updates_result.get('success'):
            # Log analytics
            conn.execute("""
                INSERT INTO bot_analytics (bot_id, event_type, event_data)
                VALUES (?, ?, ?)
            """, (
                bot_id,
                'updates_fetched',
                json.dumps({
                    'count': len(updates_result['updates']),
                    'offset': offset,
                    'limit': limit
                })
            ))
            
            conn.commit()
        
        conn.close()
        
        return jsonify(updates_result)
    
    @app.route('/api/telegram/bot/<int:bot_id>/send', methods=['POST'])
    @login_required_api
    def send_bot_message(bot_id):
        """Send message via Telegram bot"""
        user_id = session["user_id"]
        data = request.json
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        required_fields = ['chat_id', 'message']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        conn = get_db_connection()
        bot = conn.execute("""
            SELECT * FROM bots 
            WHERE id = ? AND user_id = ? AND messaging = 'telegram'
        """, (bot_id, user_id)).fetchone()
        
        if not bot:
            conn.close()
            return jsonify({"error": "Bot not found"}), 404
        
        token = bot['token']
        
        # Send message
        send_result = TelegramBotManager.send_message(
            token=token,
            chat_id=data['chat_id'],
            message=data['message'],
            parse_mode=data.get('parse_mode', 'HTML'),
            disable_web_page_preview=data.get('disable_web_page_preview', False),
            disable_notification=data.get('disable_notification', False)
        )
        
        if send_result.get('success'):
            # Log analytics
            conn.execute("""
                INSERT INTO bot_analytics (bot_id, event_type, event_data)
                VALUES (?, ?, ?)
            """, (
                bot_id,
                'message_sent',
                json.dumps({
                    'chat_id': data['chat_id'],
                    'message_length': len(data['message']),
                    'message_id': send_result.get('message_id')
                })
            ))
            
            # Update usage count
            conn.execute("""
                UPDATE bots 
                SET usage_count = usage_count + 1,
                    last_used = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (bot_id,))
            
            conn.commit()
        
        conn.close()
        
        return jsonify(send_result)
    
    @app.route('/api/telegram/bot/<int:bot_id>/chat/<chat_id>', methods=['GET'])
    @login_required_api
    def get_chat_info(bot_id, chat_id):
        """Get chat information"""
        user_id = session["user_id"]
        
        conn = get_db_connection()
        bot = conn.execute("""
            SELECT * FROM bots 
            WHERE id = ? AND user_id = ? AND messaging = 'telegram'
        """, (bot_id, user_id)).fetchone()
        
        if not bot:
            conn.close()
            return jsonify({"error": "Bot not found"}), 404
        
        token = bot['token']
        
        # Get chat info
        chat_result = TelegramBotManager.get_chat_info(token, chat_id)
        
        if chat_result.get('success'):
            # Log analytics
            conn.execute("""
                INSERT INTO bot_analytics (bot_id, event_type, event_data)
                VALUES (?, ?, ?)
            """, (
                bot_id,
                'chat_info_fetched',
                json.dumps({'chat_id': chat_id})
            ))
            
            conn.commit()
        
        conn.close()
        
        return jsonify(chat_result)
    
    @app.route('/api/telegram/bot/<int:bot_id>/analytics', methods=['GET'])
    @login_required_api
    def get_bot_analytics(bot_id):
        """Get bot analytics"""
        user_id = session["user_id"]
        
        # Get query parameters
        days = request.args.get('days', 7, type=int)
        event_type = request.args.get('event_type')
        
        conn = get_db_connection()
        
        # Check bot ownership
        bot = conn.execute("""
            SELECT * FROM bots 
            WHERE id = ? AND user_id = ? AND messaging = 'telegram'
        """, (bot_id, user_id)).fetchone()
        
        if not bot:
            conn.close()
            return jsonify({"error": "Bot not found"}), 404
        
        # Build query
        query = """
            SELECT 
                event_type,
                COUNT(*) as count,
                DATE(timestamp) as date,
                MIN(timestamp) as first_occurrence,
                MAX(timestamp) as last_occurrence
            FROM bot_analytics 
            WHERE bot_id = ?
        """
        params = [bot_id]
        
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        
        query += f" AND timestamp >= datetime('now', '-{days} days')"
        query += " GROUP BY event_type, DATE(timestamp) ORDER BY date DESC"
        
        analytics = conn.execute(query, params).fetchall()
        
        # Get summary statistics
        summary = conn.execute("""
            SELECT 
                COUNT(*) as total_events,
                COUNT(DISTINCT event_type) as unique_event_types,
                MIN(timestamp) as first_event,
                MAX(timestamp) as last_event
            FROM bot_analytics 
            WHERE bot_id = ?
        """, (bot_id,)).fetchone()
        
        # Get event type distribution
        event_distribution = conn.execute("""
            SELECT 
                event_type,
                COUNT(*) as count,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM bot_analytics WHERE bot_id = ?), 2) as percentage
            FROM bot_analytics 
            WHERE bot_id = ?
            GROUP BY event_type
            ORDER BY count DESC
        """, (bot_id, bot_id)).fetchall()
        
        conn.close()
        
        return jsonify({
            "success": True,
            "bot_id": bot_id,
            "summary": dict(summary),
            "analytics": [dict(a) for a in analytics],
            "event_distribution": [dict(e) for e in event_distribution],
            "time_period_days": days
        })
    
    @app.route('/api/telegram/bot/templates', methods=['GET', 'POST'])
    @login_required_api
    def manage_bot_templates():
        """Manage bot templates"""
        user_id = session["user_id"]
        
        conn = get_db_connection()
        
        if request.method == 'GET':
            # Get templates
            is_public = request.args.get('public', 'false').lower() == 'true'
            category = request.args.get('category')
            
            query = "SELECT * FROM bot_templates WHERE"
            params = []
            
            if is_public:
                query += " is_public = TRUE"
            else:
                query += " (created_by = ? OR is_public = TRUE)"
                params.append(user_id)
            
            if category:
                query += " AND category = ?"
                params.append(category)
            
            query += " ORDER BY created_at DESC"
            
            templates = conn.execute(query, params).fetchall()
            conn.close()
            
            return jsonify({
                "success": True,
                "templates": [dict(t) for t in templates]
            })
        
        elif request.method == 'POST':
            # Create template
            data = request.json
            
            if not data:
                return jsonify({"error": "No data provided"}), 400
            
            required_fields = ['name', 'config']
            for field in required_fields:
                if field not in data:
                    return jsonify({"error": f"Missing required field: {field}"}), 400
            
            try:
                cursor = conn.execute("""
                    INSERT INTO bot_templates (
                        name, description, config, category, 
                        is_public, created_by, tags
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    data['name'],
                    data.get('description', ''),
                    json.dumps(data['config']),
                    data.get('category'),
                    data.get('is_public', False),
                    user_id,
                    ','.join(data.get('tags', []))
                ))
                
                # Get the last insert ID from the cursor
                template_id = cursor.lastrowid
                conn.commit()
                conn.close()
                
                return jsonify({
                    "success": True,
                    "message": "Template created successfully",
                    "template_id": template_id
                }), 201
                
            except Exception as e:
                conn.rollback()
                conn.close()
                return jsonify({
                    "error": f"Failed to create template: {str(e)}"
                }), 500
    
    @app.route('/api/telegram/bot/templates/<int:template_id>', methods=['GET', 'PUT', 'DELETE'])
    @login_required_api
    def manage_bot_template(template_id):
        """Manage a specific bot template"""
        user_id = session["user_id"]
        
        conn = get_db_connection()
        template = conn.execute("""
            SELECT * FROM bot_templates WHERE id = ?
        """, (template_id,)).fetchone()
        
        if not template:
            conn.close()
            return jsonify({"error": "Template not found"}), 404
        
        # Check permissions (owner or public)
        if template['created_by'] != user_id and not template['is_public']:
            conn.close()
            return jsonify({"error": "Access denied"}), 403
        
        if request.method == 'GET':
            # Increment usage count
            conn.execute("""
                UPDATE bot_templates 
                SET usage_count = usage_count + 1
                WHERE id = ?
            """, (template_id,))
            conn.commit()
            
            conn.close()
            return jsonify({
                "success": True,
                "template": dict(template)
            })
        
        elif request.method == 'PUT':
            # Update template
            data = request.json
            
            if not data:
                conn.close()
                return jsonify({"error": "No data provided"}), 400
            
            try:
                update_fields = []
                update_values = []
                
                if 'name' in data:
                    update_fields.append("name = ?")
                    update_values.append(data['name'])
                
                if 'description' in data:
                    update_fields.append("description = ?")
                    update_values.append(data['description'])
                
                if 'config' in data:
                    update_fields.append("config = ?")
                    update_values.append(json.dumps(data['config']))
                
                if 'category' in data:
                    update_fields.append("category = ?")
                    update_values.append(data['category'])
                
                if 'is_public' in data:
                    update_fields.append("is_public = ?")
                    update_values.append(data['is_public'])
                
                if 'tags' in data:
                    update_fields.append("tags = ?")
                    update_values.append(','.join(data['tags']))
                
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                
                if update_fields:
                    update_values.append(template_id)
                    
                    query = f"""
                        UPDATE bot_templates 
                        SET {', '.join(update_fields)}
                        WHERE id = ?
                    """
                    
                    conn.execute(query, update_values)
                    conn.commit()
                
                conn.close()
                return jsonify({
                    "success": True,
                    "message": "Template updated successfully"
                })
                
            except Exception as e:
                conn.rollback()
                conn.close()
                return jsonify({
                    "error": f"Failed to update template: {str(e)}"
                }), 500
        
        elif request.method == 'DELETE':
            # Delete template
            try:
                conn.execute("DELETE FROM bot_templates WHERE id = ?", (template_id,))
                conn.commit()
                conn.close()
                
                return jsonify({
                    "success": True,
                    "message": "Template deleted successfully"
                })
                
            except Exception as e:
                conn.rollback()
                conn.close()
                return jsonify({
                    "error": f"Failed to delete template: {str(e)}"
                }), 500
    
    return app
