#!/usr/bin/env python3
"""
Fix the create_group function
"""

import re

with open('group_collaboration_ui.py', 'r') as f:
    content = f.read()

# Find and fix the create_group function
# Look for the specific pattern
pattern = r'(\s+# Create group\n\s+try:\n\s+)conn\.execute\(""".*?VALUES.*?""",.*?\)\)\n\s+# Get the last insert ID from the cursor\n\s+group_id = cursor\.lastrowid'

# Replace with fixed version
fixed_pattern = r'\1# Insert group and capture the cursor\n                cursor = conn.execute("""\n                    INSERT INTO groups (name, description, created_by, settings)\n                    VALUES (?, ?, ?, ?)\n                """, (name, description, user_id, json.dumps({\n                    "allow_public_invites": False,\n                    "default_role": "member",\n                    "bot_sharing": True,\n                    "message_history": 90  # days\n                })))\n                \n                # Get the last insert ID from the cursor\n                group_id = cursor.lastrowid'

new_content = re.sub(pattern, fixed_pattern, content, flags=re.DOTALL)

if new_content != content:
    with open('group_collaboration_ui.py', 'w') as f:
        f.write(new_content)
    print("✅ Fixed create_group function in group_collaboration_ui.py")
else:
    print("⚠️  Could not find pattern to fix")