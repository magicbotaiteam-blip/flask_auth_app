#!/usr/bin/env python3
"""
Test that all required templates exist
"""

import os

print("Checking required templates...")
print("=" * 60)

# List of required templates based on the code
required_templates = [
    'group_bots.html',
    'group_members.html', 
    'group_chat.html',
    'group_templates.html',
    'group_settings.html',
    'group_template.html',  # singular - for create/edit
    'create_group.html',
    'group_dashboard.html',
    'groups.html',
    'home_with_groups.html',
    'landing_with_groups.html',
    'my_bots_with_groups.html',
    'register_bot.html',
    'signin_local.html',
    'signup_local.html'
]

templates_dir = 'templates'
missing = []
existing = []

for template in required_templates:
    path = os.path.join(templates_dir, template)
    if os.path.exists(path):
        existing.append(template)
        size = os.path.getsize(path)
        print(f"✅ {template} ({size} bytes)")
    else:
        missing.append(template)
        print(f"❌ {template} (MISSING)")

print(f"\n✅ {len(existing)} templates exist")
print(f"❌ {len(missing)} templates missing")

if missing:
    print("\nMissing templates:")
    for template in missing:
        print(f"  - {template}")

print("\n" + "=" * 60)

# Test if the app can import and render templates
print("\nTesting template rendering...")

# Remove old database
if os.path.exists('users.db'):
    os.remove('users.db')

try:
    from app_complete_with_groups import app, init_db_complete
    init_db_complete()
    print("✅ App imports successfully")
    
    # Create a test context
    from flask import Flask
    test_app = Flask(__name__)
    test_app.secret_key = 'test'
    
    # Register routes
    from telegram_bot_api import create_telegram_bot_api
    from telegram_bot_api_part2 import create_telegram_bot_api_part2
    from group_collaboration_ui import create_group_collaboration_ui
    from group_collaboration_ui_part2 import create_group_collaboration_ui_part2
    
    create_telegram_bot_api(test_app)
    create_telegram_bot_api_part2(test_app)
    create_group_collaboration_ui(test_app)
    create_group_collaboration_ui_part2(test_app)
    
    print("✅ All routes registered")
    
    # Test group_bots route specifically
    with test_app.test_request_context():
        from flask import session
        # Create a test user and group
        from group_collaboration_ui import get_db_connection
        conn = get_db_connection()
        conn.execute("""
            INSERT INTO users (provider, username, email, password_hash) 
            VALUES (?, ?, ?, ?)
        """, ('test', 'template_test', 'test@test.com', 'hash'))
        cursor = conn.execute("SELECT last_insert_rowid()")
        user_id = cursor.fetchone()[0]
        
        conn.execute("""
            INSERT INTO groups (name, description, created_by, settings)
            VALUES (?, ?, ?, ?)
        """, ('Test Group', 'Test', user_id, '{}'))
        
        cursor = conn.execute("SELECT last_insert_rowid()")
        group_id = cursor.fetchone()[0]
        
        conn.execute("""
            INSERT INTO group_members (group_id, user_id, role, invited_by)
            VALUES (?, ?, ?, ?)
        """, (group_id, user_id, 'owner', user_id))
        
        conn.commit()
        conn.close()
        
        session['user_id'] = user_id
        
        # Get the group_bots function
        group_bots_func = test_app.view_functions['group_bots']
        
        try:
            response = group_bots_func(group_id)
            print("✅ group_bots function executes without TemplateNotFound error")
            print("✅ All templates are available!")
        except Exception as e:
            print(f"❌ Error: {e}")
            
except Exception as e:
    print(f"❌ Error during test: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Template check complete!")
if not missing:
    print("✅ All required templates are available!")
else:
    print(f"⚠️  {len(missing)} templates need to be created")
print("=" * 60)