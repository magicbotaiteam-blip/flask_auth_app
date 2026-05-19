"""
Group Collaboration UI Part 2 - Fixed invite_to_group function
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
from pathlib import Path
import json
from datetime import datetime, timedelta
import secrets
from functools import wraps
import time

DB_FILENAME = Path(__file__).parent / "users.db"

def get_db_connection_simple():
    """Simple database connection without PRAGMA statements that might cause locks"""
    import sqlite3
    conn = sqlite3.connect('users.db', timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def check_group_permission(user_id, group_id, required_role='member'):
    """Check if user has required permission in group"""
    conn = get_db_connection_simple()
    member = conn.execute("""
        SELECT role FROM group_members 
        WHERE user_id = ? AND group_id = ? AND status = 'active'
    """, (user_id, group_id)).fetchone()
    conn.close()
    
    if not member:
        return False
    
    # Role hierarchy: owner > admin > member > viewer
    role_hierarchy = {'owner': 4, 'admin': 3, 'member': 2, 'viewer': 1}
    user_role_level = role_hierarchy.get(member['role'], 0)
    required_role_level = role_hierarchy.get(required_role, 0)
    
    return user_role_level >= required_role_level

def log_group_activity(group_id, user_id, activity_type, activity_data=None, request=None):
    """Log group activity - simplified version"""
    try:
        conn = get_db_connection_simple()
        conn.execute("""
            INSERT INTO group_activity (group_id, user_id, activity_type, activity_data)
            VALUES (?, ?, ?, ?)
        """, (group_id, user_id, activity_type, json.dumps(activity_data) if activity_data else None))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DEBUG: Failed to log activity: {e}")

def group_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("landing"))
        
        group_id = kwargs.get('group_id')
        if group_id and not check_group_permission(session["user_id"], group_id, 'admin'):
            flash("Admin permission required for this action.", "error")
            return redirect(url_for("group_dashboard", group_id=group_id))
        
        return f(*args, **kwargs)
    return decorated_function

def create_group_collaboration_ui_part2_fixed(app):
    """
    Fixed version of group collaboration UI with working invite functionality
    """
    
    @app.route("/groups/<int:group_id>/invite", methods=["POST"])
    @group_admin_required
    def invite_to_group_fixed(group_id):
        """Invite someone to group - SIMPLIFIED WORKING VERSION"""
        print(f"DEBUG: invite_to_group_fixed called with group_id={group_id}")
        print(f"DEBUG: Form data: {dict(request.form)}")
        
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role", "member")
        
        if not email:
            flash("Email is required.", "error")
            return redirect(url_for("group_members", group_id=group_id))
        
        user_id = session["user_id"]
        
        # Validate role
        valid_roles = ['viewer', 'member', 'admin']
        if role not in valid_roles:
            role = 'member'
        
        # Try with retries
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            conn = None
            try:
                print(f"DEBUG: Attempt {attempt + 1}/{max_retries}")
                conn = get_db_connection_simple()
                
                # Check if user already exists
                existing_user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
                
                if existing_user:
                    # Check if already a member
                    existing_member = conn.execute("""
                        SELECT * FROM group_members 
                        WHERE group_id = ? AND user_id = ? AND status = 'active'
                    """, (group_id, existing_user['id'])).fetchone()
                    
                    if existing_member:
                        conn.close()
                        flash(f"{email} is already a group member.", "warning")
                        return redirect(url_for("group_members", group_id=group_id))
                
                # Generate invitation token
                token = secrets.token_urlsafe(32)
                
                # Set expiration (7 days from now)
                expires_at = datetime.now() + timedelta(days=7)
                
                # Create invitation
                conn.execute("""
                    INSERT INTO group_invitations (group_id, email, invited_by, token, role, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (group_id, email, user_id, token, role, expires_at))
                
                # Log activity
                log_group_activity(group_id, user_id, 'member_invited', {
                    'email': email,
                    'role': role,
                    'expires_at': expires_at.isoformat()
                }, request)
                
                conn.commit()
                conn.close()
                
                # Success!
                flash(f"Invitation sent to {email}.", "success")
                print(f"DEBUG: Invitation sent successfully to {email}")
                return redirect(url_for("group_members", group_id=group_id))
                
            except sqlite3.OperationalError as e:
                last_error = e
                error_msg = str(e).lower()
                print(f"DEBUG: SQLite error on attempt {attempt + 1}: {e}")
                
                if conn:
                    try:
                        conn.rollback()
                        conn.close()
                    except:
                        pass
                
                # Check if it's a lock/busy error
                if any(word in error_msg for word in ['locked', 'busy', 'timeout']):
                    if attempt < max_retries - 1:
                        # Wait before retrying
                        wait_time = 0.1 * (2 ** attempt)  # Exponential backoff
                        print(f"DEBUG: Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                        continue
                    else:
                        # Last attempt failed
                        flash("Database is busy. Please try again in a moment.", "error")
                        break
                else:
                    # Other SQLite error
                    flash(f"Database error: {e}", "error")
                    break
                    
            except Exception as e:
                last_error = e
                print(f"DEBUG: General error on attempt {attempt + 1}: {e}")
                
                if conn:
                    try:
                        conn.rollback()
                        conn.close()
                    except:
                        pass
                
                flash(f"Error sending invitation: {e}", "error")
                break
        
        print(f"DEBUG: Redirecting to group_members with group_id={group_id}")
        return redirect(url_for("group_members", group_id=group_id))