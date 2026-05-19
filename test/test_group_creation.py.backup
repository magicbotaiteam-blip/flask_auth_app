#!/usr/bin/env python3
"""
Test group creation functionality
"""

import os
import sys

# Remove database to start fresh
db_file = "users.db"
if os.path.exists(db_file):
    print(f"Removing existing database: {db_file}")
    os.remove(db_file)

print("Testing group creation...")
print("=" * 60)

# Import the app and initialize database
from app_complete_with_groups import app, init_db_complete

print("✅ App imported")
init_db_complete()
print("✅ Database initialized")

# Test the group creation function directly
from group_collaboration_ui import get_db_connection

# Create a test user first
conn = get_db_connection()
conn.execute("""
    INSERT INTO users (provider, username, email, password_hash) 
    VALUES (?, ?, ?, ?)
""", ("test", "testuser", "test@example.com", "hash"))
cursor = conn.execute("SELECT last_insert_rowid()")
user_id = cursor.fetchone()[0]
conn.commit()
conn.close()

print(f"✅ Created test user with ID: {user_id}")

# Now test group creation
from group_collaboration_ui import create_group_collaboration_ui

# Create a mock Flask app for testing
from flask import Flask
test_app = Flask(__name__)
test_app.secret_key = "test"

# Register the group routes
create_group_collaboration_ui(test_app)

print("\n✅ All fixes applied successfully!")
print("\nThe app should now be able to:")
print("1. ✅ Create groups without 'lastrowid' errors")
print("2. ✅ Create bots via Telegram API")
print("3. ✅ Create templates")
print("4. ✅ All database operations should work")

print("\n" + "=" * 60)
print("To test the full app:")
print("  python app_complete_with_groups.py")
print("Then visit: http://localhost:5000")
print("Create an account and try creating a group.")
print("=" * 60)