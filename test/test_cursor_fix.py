#!/usr/bin/env python3
"""
Test that cursor is properly defined
"""

import os

# Remove database to start fresh
db_file = "users.db"
if os.path.exists(db_file):
    os.remove(db_file)

print("Testing cursor fix...")
print("=" * 60)

# Import and check the code
with open('group_collaboration_ui.py', 'r') as f:
    content = f.read()

# Check if cursor is properly defined in create_group function
if 'cursor = conn.execute(' in content:
    print("✅ cursor is properly defined in group_collaboration_ui.py")
else:
    print("❌ cursor is NOT properly defined in group_collaboration_ui.py")

# Check if cursor.lastrowid is used
if 'cursor.lastrowid' in content:
    print("✅ cursor.lastrowid is used correctly")
else:
    print("❌ cursor.lastrowid is NOT used")

# Test the actual import
try:
    from app_complete_with_groups import app, init_db_complete
    print("\n✅ App imports successfully")
    
    # Initialize database
    init_db_complete()
    print("✅ Database initialized")
    
    # Test creating a group directly
    from group_collaboration_ui import get_db_connection
    
    conn = get_db_connection()
    
    # Create a test user
    conn.execute("""
        INSERT INTO users (provider, username, email, password_hash) 
        VALUES (?, ?, ?, ?)
    """, ("test", "testuser", "test@example.com", "hash"))
    
    # Get user ID
    cursor = conn.execute("SELECT last_insert_rowid()")
    user_id = cursor.fetchone()[0]
    
    print(f"✅ Created test user with ID: {user_id}")
    
    # Now test group creation
    try:
        cursor = conn.execute("""
            INSERT INTO groups (name, description, created_by, settings)
            VALUES (?, ?, ?, ?)
        """, ("Test Group", "Test Description", user_id, '{}'))
        
        group_id = cursor.lastrowid
        print(f"✅ Created group with ID: {group_id}")
        print("✅ cursor.lastrowid works correctly!")
        
    except Exception as e:
        print(f"❌ Error creating group: {e}")
    
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 60)
print("Test complete!")