#!/usr/bin/env python3
"""
Fix database schema issues — uses shared db.py.
Supports both SQLite and PostgreSQL.
"""

import os
import sys
from pathlib import Path

# Ensure we can import db.py from the project root
sys.path.insert(0, str(Path(__file__).parent))

from db import get_conn, is_postgres

DB_FILENAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.db")


def check_and_fix_tables():
    """Check if all tables exist and create missing ones"""
    conn = get_conn()
    
    print("Checking database tables...")
    print("=" * 60)
    
    # Get list of existing tables
    if is_postgres():
        tables = conn.execute("""
            SELECT table_name as name FROM information_schema.tables 
            WHERE table_schema = 'public'
        """).fetchall()
    else:
        tables = conn.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """).fetchall()
    
    existing_tables = [t['name'] for t in tables]
    
    print(f"Existing tables: {', '.join(existing_tables)}")
    
    # Tables that should exist
    required_tables = [
        'users', 'bots', 'groups', 'group_members', 'group_invitations',
        'shared_bots', 'group_activity', 'group_messages', 'group_templates',
        'bot_templates', 'bot_analytics'
    ]
    
    for table in required_tables:
        if table in existing_tables:
            print(f"✅ {table} exists")
        else:
            print(f"❌ {table} is missing - will create it")
    
    conn.close()
    
    # Create missing tables by importing the init functions
    from group_collaboration_ui import init_group_db
    from telegram_bot_api import init_db as init_telegram_db
    from analytics import BotAnalytics
    
    print("Recreating all tables...")
    
    init_telegram_db()
    init_group_db()
    BotAnalytics()
    
    print("✅ Database schema fixed!")
    
    # Verify
    conn = get_conn()
    if is_postgres():
        tables = conn.execute("""
            SELECT table_name as name FROM information_schema.tables 
            WHERE table_schema = 'public'
        """).fetchall()
    else:
        tables = conn.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """).fetchall()
    existing_tables = [t['name'] for t in tables]
    
    print(f"\nTables after fix: {', '.join(existing_tables)}")
    conn.close()


if __name__ == "__main__":
    if is_postgres():
        print("Using PostgreSQL — tables will be created on app startup.")
        check_and_fix_tables()
    elif os.path.exists(DB_FILENAME):
        print(f"Database file: {DB_FILENAME} ({os.path.getsize(DB_FILENAME)} bytes)")
        backup = f"{DB_FILENAME}.backup"
        print(f"Creating backup at: {backup}")
        import shutil
        shutil.copy2(DB_FILENAME, backup)
        
        check_and_fix_tables()
    else:
        print(f"Database file {DB_FILENAME} doesn't exist.")
        print("Tables will be created automatically when you start the app.")
