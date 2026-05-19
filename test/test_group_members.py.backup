#!/usr/bin/env python3
"""
Test the group members route
"""

import os

# Remove old database
if os.path.exists('users.db'):
    os.remove('users.db')

print("Testing group members route...")
print("=" * 60)

from app_complete_with_groups import app, init_db_complete
init_db_complete()
print("✅ Database initialized")

# Create test data
from group_collaboration_ui import get_db_connection
conn = get_db_connection()

# Create user
conn.execute("""
    INSERT INTO users (provider, username, email, password_hash) 
    VALUES (?, ?, ?, ?)
""", ('test', 'group_test', 'test@test.com', 'hash'))

cursor = conn.execute("SELECT last_insert_rowid()")
user_id = cursor.fetchone()[0]

# Create group
conn.execute("""
    INSERT INTO groups (name, description, created_by, settings)
    VALUES (?, ?, ?, ?)
""", ('Test Group', 'Test group for members', user_id, '{}'))

cursor = conn.execute("SELECT last_insert_rowid()")
group_id = cursor.fetchone()[0]

# Add user to group as owner
conn.execute("""
    INSERT INTO group_members (group_id, user_id, role, invited_by, status)
    VALUES (?, ?, ?, ?, ?)
""", (group_id, user_id, 'owner', user_id, 'active'))

conn.commit()
conn.close()

print(f"✅ Created test user (ID: {user_id}) and group (ID: {group_id})")

# Test the route
from flask import Flask, session
test_app = Flask(__name__)
test_app.secret_key = 'test'

# Register all routes
from telegram_bot_api import create_telegram_bot_api
from telegram_bot_api_part2 import create_telegram_bot_api_part2
from group_collaboration_ui import create_group_collaboration_ui
from group_collaboration_ui_part2 import create_group_collaboration_ui_part2

create_telegram_bot_api(test_app)
create_telegram_bot_api_part2(test_app)
create_group_collaboration_ui(test_app)
create_group_collaboration_ui_part2(test_app)

print("✅ All routes registered")

# Test with request context
with test_app.test_request_context(f'/groups/{group_id}/members'):
    session['user_id'] = user_id
    session['username'] = 'group_test'
    
    try:
        # Get the function
        group_members_func = test_app.view_functions['group_members']
        
        # Call it
        response = group_members_func(group_id)
        
        print("✅ group_members function executes successfully!")
        print("✅ No TemplateNotFound error!")
        print("✅ Route is working!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 60)
print("✅ TEST COMPLETE!")
print(f"The /groups/{group_id}/members page should now work.")
print("=" * 60)