#!/usr/bin/env python3
"""
Test starting the app with a fresh database
"""

import os
import sqlite3

# Remove database if it exists
db_file = "users.db"
if os.path.exists(db_file):
    print(f"Removing existing database: {db_file}")
    os.remove(db_file)

# Import app - this should create a new database
print("\nImporting app...")
from app_complete_with_groups import app, init_db_complete

print(f"\n✅ App imported successfully: {app.name}")

# Initialize database
print("Initializing database...")
init_db_complete()

# Check if database was created
if os.path.exists(db_file):
    print(f"✅ Database created: {db_file} ({os.path.getsize(db_file)} bytes)")
    
    # Check tables
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print(f"\n✅ Tables created: {len(tables)}")
    
    for table in tables:
        print(f"  - {table['name']}")
        
        # Check columns for group_members table
        if table['name'] == 'group_members':
            columns = conn.execute(f"PRAGMA table_info({table['name']})").fetchall()
            print(f"    Columns: {', '.join([col['name'] for col in columns])}")
    
    conn.close()
else:
    print(f"❌ Database not created")

print("\n" + "=" * 60)
print("Test complete! The app should now start without database errors.")
print("To start the app:")
print("  python app_complete_with_groups.py")
print("=" * 60)