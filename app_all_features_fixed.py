"""
Magic Bot AI - Fixed version of app_all_features.py
This fixes the incomplete file and makes it runnable
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from pathlib import Path
import os
import re
import json
from datetime import datetime, timedelta
from functools import wraps
import requests
from flask_dance.contrib.google import make_google_blueprint, google

# Allow insecure transport for development (HTTP on localhost)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = 'true'

app = Flask(__name__)
app.secret_key = "6ce26db79ba4b1ae2613a1dc4fa4177a75847d40f32347ac9388377a5a7b587b"

# OAuth setup for Google
google_bp = make_google_blueprint(
    client_id=os.environ.get("GOOGLE_CLIENT_ID", "your-google-client-id"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", "your-google-client-secret"),
    scope=[
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/userinfo.email",
        "openid"
    ],
    redirect_to="index"
)
app.register_blueprint(google_bp, url_prefix="/login")

DB_FILENAME = Path(__file__).parent / "users.db"

# ==================== Database Functions ====================

def get_db_connection():
    conn = sqlite3.connect(DB_FILENAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    
    # Create users table if it doesn't exist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL DEFAULT 'local',
            provider_id TEXT UNIQUE,
            username TEXT NOT NULL UNIQUE,
            email TEXT,  -- No UNIQUE constraint (allows duplicate emails)
            password_hash TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Enhanced bots table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            email TEXT,
            organization TEXT,
            messaging TEXT,
            token TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            llm TEXT,
            description TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            last_used TIMESTAMP,
            usage_count INTEGER DEFAULT 0,
            config TEXT,
            webhook_url TEXT,
            api_key TEXT,
            tags TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)
    
    # Create other tables
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
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS group_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            invited_by INTEGER,
            invited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            joined_at TIMESTAMP,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (bot_id) REFERENCES bots (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (invited_by) REFERENCES users (id) ON DELETE SET NULL
        )
    """)
    
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
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS export_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            bot_id INTEGER,
            export_type TEXT NOT NULL,
            file_path TEXT,
            file_size INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (bot_id) REFERENCES bots (id) ON DELETE CASCADE
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            query TEXT NOT NULL,
            results_count INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)
    
    # Create indexes (skip if columns don't exist yet)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bots_user_id ON bots(user_id)")
    
    # Check if tags column exists before creating index
    cursor = conn.execute("PRAGMA table_info(bots)")
    bot_columns = [row[1] for row in cursor.fetchall()]
    if 'tags' in bot_columns:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bots_tags ON bots(tags)")
    
    conn.execute("CREATE INDEX IF NOT EXISTS idx_group_members_bot_id ON group_members(bot_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_group_members_user_id ON group_members(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bot_templates_category ON bot_templates(category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bot_templates_is_public ON bot_templates(is_public)")
    
    # Check if tags column exists in bot_templates before creating index
    cursor = conn.execute("PRAGMA table_info(bot_templates)")
    template_columns = [row[1] for row in cursor.fetchall()]
    if 'tags' in template_columns:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bot_templates_tags ON bot_templates(tags)")
    
    conn.commit()
    conn.close()

init_db()

# ==================== Basic Routes ====================

@app.route("/")
def index():
    return "Magic Bot AI - Enhanced Application. Use app_working.py for full features."

@app.route("/landing")
def landing():
    return render_template("landing.html", google=google)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))

# ==================== Run Application ====================

if __name__ == "__main__":
    print("Magic Bot AI - Fixed version of app_all_features.py")
    print("Note: This is a minimal fix. Use app_working.py for full features.")
    app.run(debug=True, host='0.0.0.0', port=5001)