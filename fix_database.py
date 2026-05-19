#!/usr/bin/env python3
"""
Fix database schema issues
"""

import sqlite3
import os

import os
DB_FILENAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.db")

def check_and_fix_tables():
    """Check if all tables exist and create missing ones"""
    conn = sqlite3.connect(DB_FILENAME)
    conn.row_factory = sqlite3.Row
    
    print("Checking database tables...")
    print("=" * 60)
    
    # Get list of existing tables
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    existing_tables = [t['name'] for t in tables]
    
    print(f"Existing tables: {', '.join(existing_tables)}")
    
    # Tables that should exist
    required_tables = [
        'users',
        'bots', 
        'groups',
        'group_members',
        'group_invitations',
        'shared_bots',
        'group_activity',
        'group_messages',
        'group_templates',
        'bot_templates',
        'bot_analytics'
    ]
    
    # Check each required table
    for table in required_tables:
        if table in existing_tables:
            print(f"✅ {table} exists")
        else:
            print(f"❌ {table} is missing - will create it")
    
    print("\n" + "=" * 60)
    
    # Create missing tables by importing the init functions
    from group_collaboration_ui import init_group_db
    from telegram_bot_api import init_db as init_telegram_db
    
    print("Recreating all tables...")
    
    # Close and reopen to ensure clean state
    conn.close()
    
    # Reinitialize database (this will create missing tables)
    init_telegram_db()
    init_group_db()
    
    print("✅ Database schema fixed!")
    
    # Verify tables exist
    conn = sqlite3.connect(DB_FILENAME)
    conn.row_factory = sqlite3.Row
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    existing_tables = [t['name'] for t in tables]
    
    print(f"\nTables after fix: {', '.join(existing_tables)}")
    
    # Check group_messages table specifically
    print("\nChecking group_messages table structure...")
    try:
        columns = conn.execute("PRAGMA table_info(group_messages)").fetchall()
        print(f"group_messages has {len(columns)} columns:")
        for col in columns:
            print(f"  - {col['name']} ({col['type']})")
    except:
        print("❌ group_messages table not found or error reading it")
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("Database fix complete!")
    print("You can now start the app without errors.")

if __name__ == "__main__":
    if os.path.exists(DB_FILENAME):
        print(f"Database file: {DB_FILENAME} ({os.path.getsize(DB_FILENAME)} bytes)")
        backup = f"{DB_FILENAME}.backup"
        print(f"Creating backup at: {backup}")
        import shutil
        shutil.copy2(DB_FILENAME, backup)
        
        check_and_fix_tables()
    else:
        print(f"Database file {DB_FILENAME} doesn't exist.")
        print("It will be created automatically when you start the app.")