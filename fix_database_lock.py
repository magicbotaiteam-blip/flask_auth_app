#!/usr/bin/env python3
"""
Fix database lock issues in create_group function
"""

import re

def fix_create_group():
    with open('group_collaboration_ui.py', 'r') as f:
        content = f.read()
    
    # Find the create_group function
    # Look for the pattern from "def create_group():" to the end of the function
    pattern = r'(def create_group\(\):.*?)(?=\n\s*def|\Z)'
    
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        print("Could not find create_group function")
        return
    
    func_text = match.group(1)
    
    # Check if it already has proper transaction handling
    if 'BEGIN IMMEDIATE' in func_text:
        print("Function already has transaction handling")
        return
    
    # Replace the try block with better transaction handling
    # Find the try block inside the function
    try_pattern = r'(try:\s*)(# Execute INSERT.*?)(except Exception as e:.*?)'
    
    func_fixed = re.sub(try_pattern, 
        r'''try:
                # Get a fresh connection for this transaction
                conn = get_db_connection()
                
                # Start explicit transaction with immediate lock
                conn.execute("BEGIN IMMEDIATE")
                
                # Execute INSERT and capture the cursor
                cursor = conn.execute("""
                    INSERT INTO groups (name, description, created_by, settings)
                    VALUES (?, ?, ?, ?)
                """, (name, description, user_id, json.dumps({
                    "allow_public_invites": False,
                    "default_role": "member",
                    "bot_sharing": True,
                    "message_history": 90  # days
                })))
                
                # Get the last insert ID from the cursor
                group_id = cursor.lastrowid
                
                # Add creator as owner
                conn.execute("""
                    INSERT INTO group_members (group_id, user_id, role, invited_by)
                    VALUES (?, ?, ?, ?)
                """, (group_id, user_id, 'owner', user_id))
                
                # Commit transaction
                conn.commit()
                conn.close()
                
                # Log activity (with a new connection to avoid locks)
                try:
                    log_group_activity(group_id, user_id, 'group_created', {
                        'group_name': name,
                        'description': description
                    }, request)
                except Exception as log_error:
                    print(f"Warning: Failed to log activity: {log_error}")
                    # Don't fail group creation if logging fails
                
                flash(f"Group '{name}' created successfully!", "success")
                return redirect(url_for("group_dashboard", group_id=group_id))
                
            except Exception as e:
                # Try to rollback and close connection
                try:
                    conn.rollback()
                    conn.close()
                except:
                    pass
                
                flash(f"Error creating group: {e}", "error")
                return render_template("create_group.html", username=session.get("username"))''',
        func_text, flags=re.DOTALL)
    
    if func_fixed != func_text:
        # Replace the function in the content
        new_content = content.replace(func_text, func_fixed)
        
        with open('group_collaboration_ui.py', 'w') as f:
            f.write(new_content)
        
        print("Fixed create_group function with proper transaction handling")
    else:
        print("No changes needed")

if __name__ == "__main__":
    fix_create_group()