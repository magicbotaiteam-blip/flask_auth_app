#!/usr/bin/env python3
"""
Create a fixed version of the create_group function
"""

fixed_function = '''
    @app.route("/groups/create", methods=["GET", "POST"])
    @login_required
    def create_group():
        """Create a new group"""
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip()
            
            if not name:
                flash("Group name is required.", "error")
                return render_template("create_group.html", username=session.get("username"))
            
            user_id = session["user_id"]
            
            # Check if group name already exists for this user
            conn = get_db_connection()
            existing = conn.execute("""
                SELECT * FROM groups WHERE name = ? AND created_by = ?
            """, (name, user_id)).fetchone()
            conn.close()
            
            if existing:
                flash("You already have a group with this name.", "error")
                return render_template("create_group.html", username=session.get("username"))
            
            # Create group with transaction
            conn = None
            try:
                conn = get_db_connection()
                
                # Start explicit transaction
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
                conn = None
                
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
                # Clean up connection
                if conn:
                    try:
                        conn.rollback()
                        conn.close()
                    except:
                        pass
                
                flash(f"Error creating group: {e}", "error")
                return render_template("create_group.html", username=session.get("username"))
        
        # GET request - show form
        return render_template("create_group.html", username=session.get("username"))
'''

print("Fixed create_group function:")
print(fixed_function)