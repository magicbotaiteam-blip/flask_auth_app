"""
Telegram Bot API Implementation
Refactored to use shared db.py (SQLite local, PostgreSQL production).
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from db import get_conn
from pathlib import Path
import json
from datetime import datetime
from functools import wraps

def get_db_connection():
    """Get database connection via shared db.py"""
    return get_conn()

def init_db():
    """Initialize Telegram bot tables"""
    conn = get_db_connection()
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bot_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            bot_type TEXT NOT NULL DEFAULT 'telegram',
            name TEXT NOT NULL,
            token TEXT NOT NULL,
            config TEXT DEFAULT '{}',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)
    
    # Bot webhooks table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bot_webhooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id INTEGER NOT NULL,
            webhook_url TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_called TIMESTAMP,
            failure_count INTEGER DEFAULT 0,
            FOREIGN KEY (bot_id) REFERENCES bot_configs (id) ON DELETE CASCADE
        )
    """)
    
    # Bot logs table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bot_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            event_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (bot_id) REFERENCES bot_configs (id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()


def create_telegram_bot_api(app):
    """Add Telegram bot API routes to Flask app"""
    
    @app.route("/telegram_bot")
    def telegram_bot():
        """Telegram bot dashboard"""
        conn = get_db_connection()
        
        # Get configs for the current user or all if admin
        if session.get('role') == 'admin':
            bot_configs = conn.execute("""
                SELECT bc.*, u.username as user_name,
                    (SELECT COUNT(*) FROM bot_logs WHERE bot_id = bc.id) as log_count
                FROM bot_configs bc
                JOIN users u ON bc.user_id = u.id
                WHERE bc.is_active = TRUE
                ORDER BY bc.updated_at DESC
            """).fetchall()
        elif 'user_id' in session:
            bot_configs = conn.execute("""
                SELECT bc.*, u.username as user_name,
                    (SELECT COUNT(*) FROM bot_logs WHERE bot_id = bc.id) as log_count
                FROM bot_configs bc
                JOIN users u ON bc.user_id = u.id
                WHERE bc.user_id = ? AND bc.is_active = TRUE
                ORDER BY bc.updated_at DESC
            """, (session["user_id"],)).fetchall()
        else:
            bot_configs = []
        
        conn.close()
        
        return render_template("telegram_bot.html",
                             bot_configs=bot_configs,
                             username=session.get("username"),
                             role=session.get("role", "customer"))
    
    @app.route("/telegram_bot/create", methods=["GET", "POST"])
    def create_telegram_bot():
        """Create a new Telegram bot configuration"""
        if 'user_id' not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("signin_local"))
        
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            token = request.form.get("token", "").strip()
            bot_type = request.form.get("bot_type", "telegram")
            config = request.form.get("config", "{}")
            
            if not name or not token:
                flash("Name and token are required.", "error")
                return render_template("create_telegram_bot.html")
            
            # Validate JSON config
            try:
                json.loads(config)
            except json.JSONDecodeError:
                flash("Invalid JSON configuration.", "error")
                return render_template("create_telegram_bot.html")
            
            conn = get_db_connection()
            
            try:
                conn.execute("""
                    INSERT INTO bot_configs (user_id, bot_type, name, token, config)
                    VALUES (?, ?, ?, ?, ?)
                """, (session["user_id"], bot_type, name, token, config))
                
                conn.commit()
                conn.close()
                
                flash(f"Telegram bot '{name}' created successfully!", "success")
                return redirect(url_for("telegram_bot"))
            except Exception as e:
                conn.close()
                flash(f"Error creating bot: {e}", "error")
                return render_template("create_telegram_bot.html")
        
        return render_template("create_telegram_bot.html")
    
    @app.route("/telegram_bot/<int:bot_id>")
    def telegram_bot_detail(bot_id):
        """View Telegram bot details"""
        if 'user_id' not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("signin_local"))
        
        conn = get_db_connection()
        bot = conn.execute("SELECT * FROM bot_configs WHERE id = ?", (bot_id,)).fetchone()
        
        if not bot:
            conn.close()
            flash("Bot not found.", "error")
            return redirect(url_for("telegram_bot"))
        
        # Get bot logs
        logs = conn.execute("""
            SELECT * FROM bot_logs WHERE bot_id = ?
            ORDER BY created_at DESC LIMIT 100
        """, (bot_id,)).fetchall()
        
        # Get webhooks
        webhooks = conn.execute("""
            SELECT * FROM bot_webhooks WHERE bot_id = ?
            ORDER BY created_at DESC
        """, (bot_id,)).fetchall()
        
        conn.close()
        
        return render_template("telegram_bot_detail.html",
                             bot=bot,
                             logs=logs,
                             webhooks=webhooks,
                             username=session.get("username"))
    
    @app.route("/telegram_bot/<int:bot_id>/edit", methods=["GET", "POST"])
    def edit_telegram_bot(bot_id):
        """Edit a Telegram bot configuration"""
        if 'user_id' not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("signin_local"))
        
        conn = get_db_connection()
        bot = conn.execute("SELECT * FROM bot_configs WHERE id = ?", (bot_id,)).fetchone()
        conn.close()
        
        if not bot:
            flash("Bot not found.", "error")
            return redirect(url_for("telegram_bot"))
        
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            token = request.form.get("token", "").strip()
            config = request.form.get("config", "{}")
            
            if not name or not token:
                flash("Name and token are required.", "error")
                return render_template("edit_telegram_bot.html", bot=bot)
            
            try:
                json.loads(config)
            except json.JSONDecodeError:
                flash("Invalid JSON configuration.", "error")
                return render_template("edit_telegram_bot.html", bot=bot)
            
            conn = get_db_connection()
            try:
                conn.execute("""
                    UPDATE bot_configs
                    SET name = ?, token = ?, config = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (name, token, config, bot_id))
                conn.commit()
                conn.close()
                
                flash("Bot updated successfully!", "success")
                return redirect(url_for("telegram_bot_detail", bot_id=bot_id))
            except Exception as e:
                conn.close()
                flash(f"Error updating bot: {e}", "error")
                return render_template("edit_telegram_bot.html", bot=bot)
        
        return render_template("edit_telegram_bot.html", bot=bot)
    
    @app.route("/telegram_bot/<int:bot_id>/delete", methods=["POST"])
    def delete_telegram_bot(bot_id):
        """Delete a Telegram bot configuration"""
        if 'user_id' not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("signin_local"))
        
        conn = get_db_connection()
        try:
            conn.execute("DELETE FROM bot_logs WHERE bot_id = ?", (bot_id,))
            conn.execute("DELETE FROM bot_webhooks WHERE bot_id = ?", (bot_id,))
            conn.execute("DELETE FROM bot_configs WHERE id = ?", (bot_id,))
            conn.commit()
            flash("Bot deleted successfully.", "success")
        except Exception as e:
            conn.close()
            flash(f"Error deleting bot: {e}", "error")
            return redirect(url_for("telegram_bot"))
        
        conn.close()
        return redirect(url_for("telegram_bot"))
    
    @app.route("/telegram_bot/<int:bot_id>/log", methods=["POST"])
    def log_telegram_event(bot_id):
        """Log an event for a bot"""
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request"}), 400
        
        event_type = data.get("event_type", "unknown")
        event_data = json.dumps(data.get("event_data", {}))
        
        conn = get_db_connection()
        conn.execute("""
            INSERT INTO bot_logs (bot_id, event_type, event_data)
            VALUES (?, ?, ?)
        """, (bot_id, event_type, event_data))
        conn.commit()
        conn.close()
        
        return jsonify({"status": "ok"})
    
    return app
