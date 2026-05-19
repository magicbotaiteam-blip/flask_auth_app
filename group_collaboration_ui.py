"""
Group Collaboration UI Implementation
For Magic Bot AI Flask Application
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
from pathlib import Path
import json
from datetime import datetime
from functools import wraps

DB_FILENAME = Path(__file__).parent / "users.db"

# ==================== Database Functions ====================

def get_db_connection():
    """Get database connection with retry logic for locks"""
    max_retries = 3
    retry_delay = 0.1  # seconds
    
    for attempt in range(max_retries):
        try:
            # Add timeout to handle database locks
            conn = sqlite3.connect(DB_FILENAME, timeout=10)
            conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")
            # Set busy timeout
            conn.execute("PRAGMA busy_timeout = 5000")
            return conn
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < max_retries - 1:
                import time
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                continue
            raise
    # This should never be reached due to the raise above
    raise sqlite3.OperationalError("Failed to connect to database after retries")

def init_group_db():
    """Initialize database tables for group collaboration"""
    conn = get_db_connection()
    
    # Groups table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            settings TEXT DEFAULT '{}',
            FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE CASCADE
        )
    """)
    
    # Group members table with roles
    conn.execute("""
        CREATE TABLE IF NOT EXISTS group_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',  -- owner, admin, member, viewer
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            invited_by INTEGER,
            status TEXT DEFAULT 'active',  -- active, pending, suspended
            permissions TEXT DEFAULT '{}',
            FOREIGN KEY (group_id) REFERENCES groups (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (invited_by) REFERENCES users (id) ON DELETE SET NULL,
            UNIQUE(group_id, user_id)
        )
    """)
    
    # Group invitations table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS group_invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            email TEXT NOT NULL,
            invited_by INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            role TEXT DEFAULT 'member',
            status TEXT DEFAULT 'pending',  -- pending, accepted, expired, revoked
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES groups (id) ON DELETE CASCADE,
            FOREIGN KEY (invited_by) REFERENCES users (id) ON DELETE CASCADE
        )
    """)
    
    # Shared bots table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shared_bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id INTEGER NOT NULL,
            group_id INTEGER NOT NULL,
            shared_by INTEGER NOT NULL,
            shared_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            permissions TEXT DEFAULT '{}',
            is_active BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (bot_id) REFERENCES bots (id) ON DELETE CASCADE,
            FOREIGN KEY (group_id) REFERENCES groups (id) ON DELETE CASCADE,
            FOREIGN KEY (shared_by) REFERENCES users (id) ON DELETE CASCADE,
            UNIQUE(bot_id, group_id)
        )
    """)
    
    # Group activity log
    conn.execute("""
        CREATE TABLE IF NOT EXISTS group_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL,
            activity_data TEXT,
            ip_address TEXT,
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES groups (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)
    
    # Group messages/chat
    conn.execute("""
        CREATE TABLE IF NOT EXISTS group_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            message_type TEXT DEFAULT 'text',  -- text, file, bot_update, system
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_pinned BOOLEAN DEFAULT FALSE,
            reply_to INTEGER,
            FOREIGN KEY (group_id) REFERENCES groups (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (reply_to) REFERENCES group_messages (id) ON DELETE SET NULL
        )
    """)
    
    # Group templates
    conn.execute("""
        CREATE TABLE IF NOT EXISTS group_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            config TEXT NOT NULL,
            category TEXT,
            created_by INTEGER NOT NULL,
            is_public BOOLEAN DEFAULT FALSE,
            usage_count INTEGER DEFAULT 0,
            tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES groups (id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()

init_group_db()

# ==================== Helper Functions ====================

def get_user_groups(user_id):
    """Get all groups a user belongs to"""
    conn = get_db_connection()
    groups = conn.execute("""
        SELECT t.*, tm.role, tm.joined_at,
               (SELECT COUNT(*) FROM group_members WHERE group_id = t.id AND status = 'active') as member_count
        FROM groups t
        JOIN group_members tm ON t.id = tm.group_id
        WHERE tm.user_id = ? AND tm.status = 'active' AND t.is_active = TRUE
        ORDER BY t.created_at DESC
    """, (user_id,)).fetchall()
    conn.close()
    return groups

def get_group_members(group_id):
    """Get all members of a group"""
    conn = get_db_connection()
    members = conn.execute("""
        SELECT u.id, u.username, u.email, tm.role, tm.joined_at, tm.status
        FROM group_members tm
        JOIN users u ON tm.user_id = u.id
        WHERE tm.group_id = ? AND tm.status = 'active'
        ORDER BY 
            CASE tm.role 
                WHEN 'owner' THEN 1
                WHEN 'admin' THEN 2
                WHEN 'member' THEN 3
                ELSE 4
            END,
            tm.joined_at
    """, (group_id,)).fetchall()
    conn.close()
    return members

def check_group_permission(group_id, user_id, required_role='member'):
    """Check if user has required permission for a group"""
    conn = get_db_connection()
    member = conn.execute("""
        SELECT role FROM group_members 
        WHERE group_id = ? AND user_id = ? AND status = 'active'
    """, (group_id, user_id)).fetchone()
    conn.close()
    
    if not member:
        return False
    
    role_hierarchy = {'owner': 3, 'admin': 2, 'member': 1, 'viewer': 0}
    user_role_level = role_hierarchy.get(member['role'], 0)
    required_role_level = role_hierarchy.get(required_role, 0)
    
    return user_role_level >= required_role_level

def log_group_activity(group_id, user_id, activity_type, activity_data=None, request=None):
    """Log group activity"""
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO group_activity (group_id, user_id, activity_type, activity_data, ip_address, user_agent)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        group_id,
        user_id,
        activity_type,
        json.dumps(activity_data) if activity_data else None,
        request.remote_addr if request else None,
        request.user_agent.string if request and request.user_agent else None
    ))
    conn.commit()
    conn.close()

# ==================== Decorators ====================

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for("signin_local"))
        return f(*args, **kwargs)
    return decorated_function

def group_required(f):
    """Decorator to require group membership"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for("signin_local"))
        
        group_id = kwargs.get('group_id')
        if not group_id:
            flash("Group not specified.", "error")
            return redirect(url_for("groups"))
        
        if not check_group_permission(group_id, session["user_id"], 'viewer'):
            flash("You don't have permission to access this group.", "error")
            return redirect(url_for("groups"))
        
        return f(*args, **kwargs)
    return decorated_function

def group_admin_required(f):
    """Decorator to require group admin permissions"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for("signin_local"))
        
        group_id = kwargs.get('group_id')
        if not group_id:
            flash("Group not specified.", "error")
            return redirect(url_for("groups"))
        
        if not check_group_permission(group_id, session["user_id"], 'admin'):
            flash("You need admin permissions for this action.", "error")
            return redirect(url_for("group_dashboard", group_id=group_id))
        
        return f(*args, **kwargs)
    return decorated_function

# ==================== Group Collaboration UI Routes ====================

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated_function

def create_group_collaboration_ui(app):
    """
    Add group collaboration UI routes to Flask app
    """
    
    @app.route("/groups")
    @login_required
    def groups():
        """List user's groups and invitations"""
        user_id = session["user_id"]
        
        conn = get_db_connection()
        
        # Get all user's groups via membership
        user_groups = get_user_groups(user_id)
        
        # Get pending invitations
        invitations = conn.execute("""
            SELECT ti.*, t.name as group_name, u.username as inviter_name
            FROM group_invitations ti
            JOIN groups t ON ti.group_id = t.id
            JOIN users u ON ti.invited_by = u.id
            WHERE ti.email = (
                SELECT email FROM users WHERE id = ?
            ) AND ti.status = 'pending' AND ti.expires_at > CURRENT_TIMESTAMP
        """, (user_id,)).fetchall()
        conn.close()
        
        return render_template("groups.html", 
                             groups=user_groups, 
                             invitations=invitations,
                             active_page='groups',
                             username=session.get("username"))
    
    @app.route("/groups/create", methods=["GET", "POST"])
    @login_required
    def create_group():
        """Create a new group - FIXED VERSION WITH PROPER TRANSACTION HANDLING"""
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
    
    @app.route("/groups/<int:group_id>")
    @group_required
    def group_dashboard(group_id):
        """Group dashboard"""
        conn = get_db_connection()
        
        # Get group info
        group = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
        
        # Get group members
        members = get_group_members(group_id)
        
        # Get group bots
        bots = conn.execute("""
            SELECT b.*, sb.shared_at, sb.permissions as share_permissions,
                   u.username as shared_by_name
            FROM shared_bots sb
            JOIN bots b ON sb.bot_id = b.id
            JOIN users u ON sb.shared_by = u.id
            WHERE sb.group_id = ?
            ORDER BY sb.shared_at DESC
        """, (group_id,)).fetchall()
        
        # Get recent activity
        activity = conn.execute("""
            SELECT ta.*, u.username
            FROM group_activity ta
            JOIN users u ON ta.user_id = u.id
            WHERE ta.group_id = ?
            ORDER BY ta.created_at DESC
            LIMIT 20
        """, (group_id,)).fetchall()
        
        # Get recent messages
        recent_messages = conn.execute("""
            SELECT tm.*, u.username
            FROM group_messages tm
            JOIN users u ON tm.user_id = u.id
            WHERE tm.group_id = ? AND tm.message_type = 'text'
            ORDER BY tm.created_at DESC
            LIMIT 10
        """, (group_id,)).fetchall()
        
        conn.close()
        
        # Get user's role in this group
        c2 = get_db_connection()
        user_role = c2.execute("""
            SELECT role FROM group_members
            WHERE group_id = ? AND user_id = ?
        """, (group_id, session["user_id"])).fetchone()
        c2.close()
        
        return render_template("group_dashboard.html",
                             group=group,
                             members=members,
                             bots=bots,
                             shared_bots=bots,
                             activity=activity,
                             messages=recent_messages,
                             username=session.get("username"),
                             user_role=user_role["role"] if user_role else None,
                             is_admin=(session.get("role") == "admin"),
                             active_page='groups')
    
    # Note: The rest of the functions are in group_collaboration_ui_part2.py