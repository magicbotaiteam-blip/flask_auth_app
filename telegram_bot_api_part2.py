"""
Telegram Bot API Part 2 - More Telegram bot routes
Refactored to use shared db.py (SQLite local, PostgreSQL production).
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from db import get_conn
from pathlib import Path
import json
from datetime import datetime, timedelta
from functools import wraps

def get_db_connection():
    """Get database connection via shared db.py"""
    return get_conn()


def create_telegram_bot_api_part2(app):
    """Add more Telegram bot API routes to Flask app"""
    
    @app.route("/api/bot/<int:bot_id>/webhook", methods=["POST"])
    def register_bot_webhook(bot_id):
        """Register a webhook for a bot"""
        if 'user_id' not in session:
            return jsonify({"error": "Authentication required"}), 401
        
        data = request.get_json()
        if not data or 'webhook_url' not in data:
            return jsonify({"error": "Webhook URL is required"}), 400
        
        webhook_url = data['webhook_url'].strip()
        
        conn = get_db_connection()
        
        # Verify bot exists and user owns it
        bot = conn.execute("""
            SELECT * FROM bot_configs WHERE id = ? AND user_id = ?
        """, (bot_id, session["user_id"])).fetchone()
        
        if not bot:
            conn.close()
            return jsonify({"error": "Bot not found or access denied"}), 404
        
        # Deactivate existing webhooks
        conn.execute("""
            UPDATE bot_webhooks SET is_active = FALSE WHERE bot_id = ?
        """, (bot_id,))
        
        # Create new webhook
        conn.execute("""
            INSERT INTO bot_webhooks (bot_id, webhook_url, is_active)
            VALUES (?, ?, TRUE)
        """, (bot_id, webhook_url))
        
        conn.commit()
        conn.close()
        
        return jsonify({"status": "ok", "webhook_url": webhook_url})
    
    @app.route("/api/bot/<int:bot_id>/webhook", methods=["GET"])
    def get_bot_webhook(bot_id):
        """Get active webhook for a bot"""
        if 'user_id' not in session:
            return jsonify({"error": "Authentication required"}), 401
        
        conn = get_db_connection()
        
        webhook = conn.execute("""
            SELECT * FROM bot_webhooks
            WHERE bot_id = ? AND is_active = TRUE
            ORDER BY created_at DESC
            LIMIT 1
        """, (bot_id,)).fetchone()
        
        conn.close()
        
        if not webhook:
            return jsonify({"webhook_url": None})
        
        return jsonify({
            "webhook_url": webhook['webhook_url'],
            "created_at": webhook['created_at'],
            "last_called": webhook['last_called']
        })
    
    @app.route("/api/bot/<int:bot_id>/test", methods=["POST"])
    def test_bot_connection(bot_id):
        """Test bot connection"""
        if 'user_id' not in session:
            return jsonify({"error": "Authentication required"}), 401
        
        conn = get_db_connection()
        
        bot = conn.execute("""
            SELECT * FROM bot_configs WHERE id = ? AND user_id = ?
        """, (bot_id, session["user_id"])).fetchone()
        
        conn.close()
        
        if not bot:
            return jsonify({"error": "Bot not found or access denied"}), 404
        
        # Test connection by sending a request to Telegram API
        import requests
        
        try:
            response = requests.get(
                f"https://api.telegram.org/bot{bot['token']}/getMe",
                timeout=10
            )
            
            if response.status_code == 200:
                bot_info = response.json()
                return jsonify({
                    "status": "ok",
                    "bot_info": bot_info.get('result', {})
                })
            else:
                return jsonify({
                    "status": "error",
                    "message": f"Telegram API returned {response.status_code}: {response.text}"
                })
        except requests.exceptions.RequestException as e:
            return jsonify({
                "status": "error",
                "message": f"Connection failed: {str(e)}"
            })
    
    @app.route("/api/bot/<int:bot_id>/commands", methods=["POST"])
    def set_bot_commands(bot_id):
        """Set bot commands"""
        if 'user_id' not in session:
            return jsonify({"error": "Authentication required"}), 401
        
        data = request.get_json()
        if not data or 'commands' not in data:
            return jsonify({"error": "Commands list is required"}), 400
        
        conn = get_db_connection()
        
        bot = conn.execute("""
            SELECT * FROM bot_configs WHERE id = ? AND user_id = ?
        """, (bot_id, session["user_id"])).fetchone()
        
        conn.close()
        
        if not bot:
            return jsonify({"error": "Bot not found or access denied"}), 404
        
        import requests
        
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{bot['token']}/setMyCommands",
                json={"commands": data['commands']},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    # Log the command update
                    conn = get_db_connection()
                    conn.execute("""
                        INSERT INTO bot_logs (bot_id, event_type, event_data)
                        VALUES (?, 'commands_updated', ?)
                    """, (bot_id, json.dumps(data['commands'])))
                    conn.commit()
                    conn.close()
                    
                    return jsonify({"status": "ok", "result": result.get('result')})
            
            return jsonify({
                "status": "error",
                "message": f"Failed to set commands: {response.text}"
            })
        except requests.exceptions.RequestException as e:
            return jsonify({
                "status": "error",
                "message": f"Request failed: {str(e)}"
            })
    
    @app.route("/api/bot/<int:bot_id>/commands", methods=["GET"])
    def get_bot_commands(bot_id):
        """Get bot commands"""
        if 'user_id' not in session:
            return jsonify({"error": "Authentication required"}), 401
        
        conn = get_db_connection()
        
        bot = conn.execute("""
            SELECT * FROM bot_configs WHERE id = ? AND user_id = ?
        """, (bot_id, session["user_id"])).fetchone()
        
        conn.close()
        
        if not bot:
            return jsonify({"error": "Bot not found or access denied"}), 404
        
        import requests
        
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{bot['token']}/getMyCommands",
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                return jsonify({
                    "status": "ok",
                    "commands": result.get('result', [])
                })
            
            return jsonify({
                "status": "error",
                "message": f"Failed to get commands: {response.text}"
            })
        except requests.exceptions.RequestException as e:
            return jsonify({
                "status": "error",
                "message": f"Request failed: {str(e)}"
            })
    
    @app.route("/api/bot/<int:bot_id>/config", methods=["PUT"])
    def update_bot_config(bot_id):
        """Update bot configuration"""
        if 'user_id' not in session:
            return jsonify({"error": "Authentication required"}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request data"}), 400
        
        conn = get_db_connection()
        
        bot = conn.execute("""
            SELECT * FROM bot_configs WHERE id = ? AND user_id = ?
        """, (bot_id, session["user_id"])).fetchone() or \
            conn.execute("""
                SELECT bc.* FROM bot_configs bc
                JOIN user_roles ur ON ur.user_id = ?
                JOIN roles r ON ur.role_id = r.id
                WHERE bc.id = ? AND r.name = 'admin'
            """, (session["user_id"], bot_id)).fetchone()
        
        if not bot:
            conn.close()
            return jsonify({"error": "Bot not found or access denied"}), 404
        
        # Update allowed fields
        allowed_fields = ['config', 'name', 'token']
        update_fields = []
        update_values = []
        
        for field in allowed_fields:
            if field in data:
                update_fields.append(f"{field} = ?")
                update_values.append(data[field])
        
        if not update_fields:
            conn.close()
            return jsonify({"error": "No valid fields to update"}), 400
        
        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        update_values.append(bot_id)
        
        try:
            conn.execute(f"""
                UPDATE bot_configs
                SET {', '.join(update_fields)}
                WHERE id = ?
            """, update_values)
            conn.commit()
            conn.close()
            
            return jsonify({"status": "ok", "updated_fields": list(data.keys())})
        except Exception as e:
            conn.close()
            return jsonify({"error": f"Update failed: {str(e)}"}), 500
    
    @app.route("/api/bot/<int:bot_id>/stats", methods=["GET"])
    def get_bot_stats(bot_id):
        """Get bot statistics"""
        if 'user_id' not in session:
            return jsonify({"error": "Authentication required"}), 401
        
        conn = get_db_connection()
        
        bot = conn.execute("""
            SELECT * FROM bot_configs WHERE id = ? AND user_id = ?
        """, (bot_id, session["user_id"])).fetchone()
        
        if not bot:
            # Check admin access
            bot = conn.execute("""
                SELECT bc.* FROM bot_configs bc
                JOIN user_roles ur ON ur.user_id = ?
                JOIN roles r ON ur.role_id = r.id
                WHERE bc.id = ? AND r.name = 'admin'
            """, (session["user_id"], bot_id)).fetchone()
        
        if not bot:
            conn.close()
            return jsonify({"error": "Bot not found or access denied"}), 404
        
        # Get stats
        stats = {}
        
        # Total events
        cursor = conn.execute("""
            SELECT COUNT(*) as total FROM bot_logs WHERE bot_id = ?
        """, (bot_id,))
        stats['total_events'] = cursor.fetchone()['total']
        
        # Events by type
        cursor = conn.execute("""
            SELECT event_type, COUNT(*) as count
            FROM bot_logs WHERE bot_id = ?
            GROUP BY event_type ORDER BY count DESC
        """, (bot_id,))
        stats['events_by_type'] = {row['event_type']: row['count'] for row in cursor.fetchall()}
        
        # Events in last 24h
        cursor = conn.execute("""
            SELECT COUNT(*) as count FROM bot_logs
            WHERE bot_id = ? AND created_at > CURRENT_TIMESTAMP - INTERVAL '24 hours'
        """, (bot_id,))
        stats['events_24h'] = cursor.fetchone()['count'] if is_postgres() else cursor.fetchone()['count']
        
        # Total webhooks
        cursor = conn.execute("""
            SELECT COUNT(*) as count FROM bot_webhooks WHERE bot_id = ?
        """, (bot_id,))
        stats['total_webhooks'] = cursor.fetchone()['count']
        
        conn.close()
        
        return jsonify(stats)
    
    @app.route("/api/bot/<int:bot_id>/logs", methods=["GET"])
    def get_bot_logs(bot_id):
        """Get bot logs"""
        if 'user_id' not in session:
            return jsonify({"error": "Authentication required"}), 401
        
        limit = request.args.get('limit', 100, type=int)
        
        conn = get_db_connection()
        
        bot = conn.execute("""
            SELECT * FROM bot_configs WHERE id = ? AND user_id = ?
        """, (bot_id, session["user_id"])).fetchone() or \
            conn.execute("""
                SELECT bc.* FROM bot_configs bc
                JOIN user_roles ur ON ur.user_id = ?
                JOIN roles r ON ur.role_id = r.id
                WHERE bc.id = ? AND r.name = 'admin'
            """, (session["user_id"], bot_id)).fetchone()
        
        if not bot:
            conn.close()
            return jsonify({"error": "Bot not found or access denied"}), 404
        
        logs = conn.execute("""
            SELECT * FROM bot_logs WHERE bot_id = ?
            ORDER BY created_at DESC LIMIT ?
        """, (bot_id, limit)).fetchall()
        
        conn.close()
        
        return jsonify({
            "logs": [dict(log) for log in logs]
        })
    
    return app
