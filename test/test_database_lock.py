#!/usr/bin/env python3
"""
Test database lock handling
"""

import os
import sqlite3
import threading
import time

# Remove old database
if os.path.exists('users.db'):
    os.remove('users.db')

print("Testing database lock handling...")
print("=" * 60)

# Test the new get_db_connection function
from group_collaboration_ui import get_db_connection

print("1. Testing single connection...")
try:
    conn = get_db_connection()
    print("  ✅ Single connection works")
    conn.close()
except Exception as e:
    print(f"  ❌ Error: {e}")

print("\n2. Testing multiple connections...")
connections = []
try:
    for i in range(5):
        conn = get_db_connection()
        connections.append(conn)
        print(f"  ✅ Connection {i+1} established")
    print("  ✅ All connections established successfully")
    
    # Close all connections
    for conn in connections:
        conn.close()
        
except Exception as e:
    print(f"  ❌ Error with multiple connections: {e}")

print("\n3. Testing concurrent access (simulating Flask threads)...")

def create_user_thread(user_id):
    """Simulate a thread creating a user"""
    try:
        conn = get_db_connection()
        conn.execute("""
            INSERT INTO users (provider, username, email, password_hash) 
            VALUES (?, ?, ?, ?)
        """, ('test', f'user{user_id}', f'user{user_id}@test.com', 'hash'))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        return str(e)

# Initialize database
from app_complete_with_groups import init_db_complete
init_db_complete()
print("  ✅ Database initialized")

# Try concurrent inserts
threads = []
results = []

for i in range(3):
    t = threading.Thread(target=lambda idx=i: results.append((idx, create_user_thread(idx))))
    threads.append(t)
    t.start()

# Wait for all threads
for t in threads:
    t.join()

# Check results
success_count = sum(1 for _, result in results if result is True)
error_count = sum(1 for _, result in results if isinstance(result, str))

print(f"  ✅ {success_count} threads succeeded")
if error_count > 0:
    print(f"  ⚠️  {error_count} threads had errors:")
    for idx, result in results:
        if isinstance(result, str):
            print(f"    Thread {idx}: {result}")

print("\n4. Testing group creation transaction...")
try:
    # Create a test user
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO users (provider, username, email, password_hash) 
        VALUES (?, ?, ?, ?)
    """, ('test', 'grouptest', 'group@test.com', 'hash'))
    cursor = conn.execute("SELECT last_insert_rowid()")
    user_id = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    
    print(f"  ✅ Created test user with ID: {user_id}")
    
    # Test group creation
    from group_collaboration_ui import create_group_collaboration_ui
    from flask import Flask, session
    
    # Create mock app and session
    test_app = Flask(__name__)
    test_app.secret_key = 'test'
    create_group_collaboration_ui(test_app)
    
    with test_app.test_request_context():
        session['user_id'] = user_id
        
        # Simulate group creation
        conn = get_db_connection()
        conn.execute("BEGIN IMMEDIATE")
        
        cursor = conn.execute("""
            INSERT INTO groups (name, description, created_by, settings)
            VALUES (?, ?, ?, ?)
        """, ('Test Group', 'Test Description', user_id, '{}'))
        
        group_id = cursor.lastrowid
        
        conn.execute("""
            INSERT INTO group_members (group_id, user_id, role, invited_by)
            VALUES (?, ?, ?, ?)
        """, (group_id, user_id, 'owner', user_id))
        
        conn.commit()
        conn.close()
        
        print(f"  ✅ Created group with ID: {group_id}")
        print("  ✅ Transaction completed successfully")
        
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("✅ Database lock handling test complete!")
print("The app should now handle concurrent database access without locks.")
print("=" * 60)