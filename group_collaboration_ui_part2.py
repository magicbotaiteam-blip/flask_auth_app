"""
Group Collaboration UI Part 2 - More routes and templates
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
from pathlib import Path
import json
from datetime import datetime, timedelta
import secrets
from functools import wraps

DB_FILENAME = Path(__file__).parent / "users.db"

def get_db_connection():
    """Get database connection with retry logic for locks"""
    import sqlite3
    import time

    max_retries = 5
    base_delay = 0.1  # seconds

    for attempt in range(max_retries):
        try:
            # Add timeout to handle database locks
            conn = sqlite3.connect(str(DB_FILENAME), timeout=30)  # Increased timeout
            conn.row_factory = sqlite3.Row

            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")

            # Set busy timeout (5 seconds)
            conn.execute("PRAGMA busy_timeout = 5000")

            # Set synchronous mode to NORMAL for better performance
            # (still safe with WAL mode)
            conn.execute("PRAGMA synchronous = NORMAL")

            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON")

            return conn

        except sqlite3.OperationalError as e:
            error_msg = str(e).lower()

            # Check for lock-related errors
            if any(lock_word in error_msg for lock_word in ['locked', 'busy', 'timeout']) \
               and attempt < max_retries - 1:

                # Exponential backoff with jitter
                delay = base_delay * (2 ** attempt) + (0.01 * attempt)
                time.sleep(delay)
                continue

            # Re-raise if not a lock error or out of retries
            raise

        except Exception as e:
            # Re-raise other exceptions
            raise
            raise
    # This should never be reached due to the raise above
    raise sqlite3.OperationalError("Failed to connect to database after retries")

def check_group_permission(user_id, group_id, required_role='member'):
    """Check if user has required permission in group"""
    conn = get_db_connection()
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
    """Log group activity - SIMPLIFIED VERSION"""
    import sqlite3
    from pathlib import Path
    
    try:
        # Simple database connection
        db_path = Path(__file__).parent / 'users.db'
        conn = sqlite3.connect(str(db_path), timeout=5)
        conn.row_factory = sqlite3.Row
        
        ip_address = request.remote_addr if request else None
        user_agent = request.user_agent.string if request else None

        conn.execute("""
            INSERT INTO group_activity (group_id, user_id, activity_type, activity_data, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (group_id, user_id, activity_type,
              json.dumps(activity_data) if activity_data else None,
              ip_address, user_agent))

        conn.commit()
        conn.close()
    except Exception as e:
        # Silently fail - activity logging is non-critical
        pass

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

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("landing"))
        return f(*args, **kwargs)
    return decorated_function

def group_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("landing"))

        group_id = kwargs.get('group_id')
        if group_id and not check_group_permission(session["user_id"], group_id, 'viewer'):
            flash("You don't have access to this group.", "error")
            return redirect(url_for("groups"))

        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role', 'customer') != 'admin':
            flash("You do not have permission to access group features.", "error")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function

def create_group_collaboration_ui_part2(app):
    """
    More group collaboration UI routes
    """

    @app.route("/groups/<int:group_id>/invite", methods=["POST"])
    @group_admin_required
    def invite_to_group(group_id):
        """Invite someone to group - SIMPLIFIED VERSION TO AVOID DATABASE LOCKS"""
        import sqlite3
        from pathlib import Path
        print(f"DEBUG: invite_to_group called with group_id={group_id}")
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

        # Simple approach - try once with minimal database operations
        conn = None
        try:
            print(f"DEBUG: Starting invite process for {email}")

            # Get connection with minimal configuration
            db_path = Path(__file__).parent / 'users.db'
            print(f"DEBUG: Connecting to database at: {db_path}")
            conn = sqlite3.connect(str(db_path), timeout=10)
            conn.row_factory = sqlite3.Row

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
            
            # Get group name and inviter username for email
            group_info = conn.execute("SELECT name FROM groups WHERE id = ?", (group_id,)).fetchone()
            inviter_info = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
            
            conn.commit()
            conn.close()

            # Send invitation email
            try:
                from email_utils import send_group_invitation_email
                
                invitation_data = {
                    'email': email,
                    'group_name': group_info['name'] if group_info else 'Unknown Group',
                    'inviter_name': inviter_info['username'] if inviter_info else 'Unknown User',
                    'token': token,
                    'role': role
                }
                
                # Get app URL from request or use default
                app_url = request.host_url.rstrip('/')
                
                email_sent = send_group_invitation_email(invitation_data, app_url)
                
                # Always show the invitation link so user can copy it if needed
                invitation_link = f"{app_url}/groups/invite/accept/{token}"
                
                if email_sent:
                    flash(f"Invitation email sent to {email}. You can also share this link: {invitation_link}", "success")
                    print(f"DEBUG: Invitation email sent successfully to {email}")
                else:
                    flash(f"Invitation created for {email}. Email not configured - share this link manually: {invitation_link}", "warning")
                    print(f"DEBUG: Email not sent (not configured). Invitation link: {invitation_link}")
                    
            except ImportError:
                flash(f"Invitation created for {email}. Email system not available - share this link manually: {request.host_url.rstrip('/')}/groups/invite/accept/{token}", "warning")
                print(f"DEBUG: Email utils not available. Invitation link: {request.host_url.rstrip('/')}/groups/invite/accept/{token}")
            except Exception as email_error:
                flash(f"Invitation created for {email} but email failed to send: {str(email_error)}. Share this link manually: {request.host_url.rstrip('/')}/groups/invite/accept/{token}", "warning")
                print(f"DEBUG: Email sending error: {email_error}. Invitation link: {request.host_url.rstrip('/')}/groups/invite/accept/{token}")
            
            # Log activity (skip if it fails)
            try:
                log_group_activity(group_id, user_id, 'member_invited', {
                    'email': email,
                    'role': role,
                    'expires_at': expires_at.isoformat(),
                    'email_sent': 'email_sent' in locals()
                }, request)
            except Exception as log_error:
                print(f"DEBUG: Failed to log activity (non-critical): {log_error}")

        except sqlite3.OperationalError as e:
            error_msg = str(e).lower()
            print(f"DEBUG: SQLite operational error: {e}")
            
            if conn:
                try:
                    conn.rollback()
                    conn.close()
                except:
                    pass
            
            if any(word in error_msg for word in ['locked', 'busy', 'timeout']):
                flash("Database is busy. Please try again in a moment.", "error")
            else:
                flash(f"Database error: {e}", "error")
                
        except Exception as e:
            print(f"DEBUG: General error: {e}")
            
            if conn:
                try:
                    conn.rollback()
                    conn.close()
                except:
                    pass
            
            flash(f"Error sending invitation: {e}", "error")
        
        print(f"DEBUG: Redirecting to group_members with group_id={group_id}")
        return redirect(url_for("group_members", group_id=group_id))

    @app.route("/groups/invite/accept/<token>")
    def accept_group_invitation(token):
        """Accept group invitation - handles both logged in and new users"""
        import sqlite3
        from pathlib import Path
        
        print(f"DEBUG: accept_group_invitation called with token={token}")
        
        conn = None
        try:
            # Simple database connection
            db_path = Path(__file__).parent / 'users.db'
            print(f"DEBUG: Connecting to database at: {db_path}")
            conn = sqlite3.connect(str(db_path), timeout=10)
            conn.row_factory = sqlite3.Row
            
            # Get invitation
            invitation = conn.execute("""
                SELECT ti.*, t.name as group_name
                FROM group_invitations ti
                JOIN groups t ON ti.group_id = t.id
                WHERE ti.token = ? AND ti.status = 'pending'
                AND ti.expires_at > CURRENT_TIMESTAMP
            """, (token,)).fetchone()

            if not invitation:
                conn.close()
                flash("Invalid or expired invitation.", "error")
                return redirect(url_for("groups"))
            
            conn.close()
            
            # Check if user is logged in
            if 'user_id' not in session:
                # User is not logged in - store token in session and redirect to signup
                session['invitation_token'] = token
                flash(f"Please sign up to accept invitation to '{invitation['group_name']}'.", "info")
                return redirect(url_for("signup_local", invitation=token))
            
            # User is logged in - proceed with acceptance
            user_id = session["user_id"]
            
            # Re-open connection for logged-in user flow
            conn = sqlite3.connect(str(db_path), timeout=10)
            conn.row_factory = sqlite3.Row
            
            # Get user email
            user = conn.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()

            if not user or user['email'].lower() != invitation['email'].lower():
                conn.close()
                flash("This invitation is not for your account. Please sign up with the email you were invited with.", "error")
                # Clear any stored invitation token since email doesn't match
                if 'invitation_token' in session:
                    session.pop('invitation_token')
                return redirect(url_for("groups"))

            # Check if already a member
            existing_member = conn.execute("""
                SELECT * FROM group_members
                WHERE group_id = ? AND user_id = ? AND status = 'active'
            """, (invitation['group_id'], user_id)).fetchone()

            if existing_member:
                # Update invitation status
                conn.execute("""
                    UPDATE group_invitations
                    SET status = 'accepted'
                    WHERE id = ?
                """, (invitation['id'],))

                conn.commit()
                conn.close()
                flash(f"You are already a member of '{invitation['group_name']}'.", "info")
                return redirect(url_for("group_dashboard", group_id=invitation['group_id']))

            # Add user to group
            conn.execute("""
                INSERT INTO group_members (group_id, user_id, role, invited_by, status)
                VALUES (?, ?, ?, ?, 'active')
            """, (invitation['group_id'], user_id, invitation['role'], invitation['invited_by']))

            # Update invitation status
            conn.execute("""
                UPDATE group_invitations
                    SET status = 'accepted'
                    WHERE id = ?
                """, (invitation['id'],))

            # Log activity (skip if it fails)
            try:
                log_group_activity(invitation['group_id'], user_id, 'member_joined', {
                    'invitation_id': invitation['id'],
                    'role': invitation['role']
                }, request)
            except Exception as log_error:
                print(f"DEBUG: Failed to log activity (non-critical): {log_error}")

            conn.commit()
            conn.close()
            
            # Clear invitation token from session if present
            if 'invitation_token' in session:
                session.pop('invitation_token')

            flash(f"You have joined '{invitation['group_name']}'!", "success")
            print(f"DEBUG: Successfully joined group {invitation['group_id']}")
            return redirect(url_for("group_dashboard", group_id=invitation['group_id']))

        except sqlite3.OperationalError as e:
            error_msg = str(e).lower()
            print(f"DEBUG: SQLite operational error: {e}")
            
            if conn:
                try:
                    conn.rollback()
                    conn.close()
                except:
                    pass
            
            if any(word in error_msg for word in ['locked', 'busy', 'timeout']):
                flash("Database is busy. Please try again in a moment.", "error")
            else:
                flash(f"Database error: {e}", "error")
            return redirect(url_for("groups"))
                
        except Exception as e:
            print(f"DEBUG: General error: {e}")
            
            if conn:
                try:
                    conn.rollback()
                    conn.close()
                except:
                    pass
            
            flash(f"Error accepting invitation: {e}", "error")
            return redirect(url_for("groups"))

    @app.route("/groups/<int:group_id>/members")
    @group_required
    def group_members(group_id):
        """Group members management"""
        conn = get_db_connection()

        # Get group details
        group = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()

        # Get group members with user details
        members = conn.execute("""
            SELECT
                tm.*,
                u.username,
                u.email,
                u.provider
            FROM group_members tm
            JOIN users u ON tm.user_id = u.id
            WHERE tm.group_id = ?
            ORDER BY
                CASE tm.role
                    WHEN 'owner' THEN 1
                    WHEN 'admin' THEN 2
                    WHEN 'member' THEN 3
                    WHEN 'viewer' THEN 4
                    ELSE 5
                END,
                tm.joined_at
        """, (group_id,)).fetchall()

        # Get pending invitations
        invitations = conn.execute("""
            SELECT ti.*, u.username as invited_by_name
            FROM group_invitations ti
            LEFT JOIN users u ON ti.invited_by = u.id
            WHERE ti.group_id = ? AND ti.status = 'pending'
            ORDER BY ti.invited_at DESC
        """, (group_id,)).fetchall()

        # Get user's role in this group
        user_role = conn.execute("""
            SELECT role FROM group_members
            WHERE group_id = ? AND user_id = ?
        """, (group_id, session["user_id"])).fetchone()

        conn.close()

        return render_template("group_members.html",
                             group=group,
                             members=members,
                             invitations=invitations,
                             user_role=user_role["role"] if user_role else None,
                             is_admin=(session.get("role") == "admin"),
                             username=session.get("username"))

    @app.route("/groups/<int:group_id>/bots")
    @group_required
    def group_bots(group_id):
        """Group shared bots"""
        conn = get_db_connection()

        group = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()

        # Get shared bots with details
        shared_bots_raw = conn.execute("""
            SELECT
                b.*,
                sb.id as share_id,
                sb.permissions,
                sb.shared_at,
                sb.shared_by,
                u.username as shared_by_name,
                tm.role as user_role
            FROM shared_bots sb
            JOIN bots b ON sb.bot_id = b.id
            JOIN users u ON sb.shared_by = u.id
            JOIN group_members tm ON tm.group_id = sb.group_id AND tm.user_id = ?
            WHERE sb.group_id = ? AND b.is_active = TRUE
            ORDER BY sb.shared_at DESC
        """, (session["user_id"], group_id)).fetchall()

        # Parse permissions JSON for shared bots
        shared_bots = []
        for bot in shared_bots_raw:
            bot_dict = dict(bot)
            # Parse permissions if it exists
            if bot_dict.get('permissions'):
                try:
                    bot_dict['permissions_parsed'] = json.loads(bot_dict['permissions'])
                except:
                    bot_dict['permissions_parsed'] = {}
            else:
                bot_dict['permissions_parsed'] = {}
            shared_bots.append(bot_dict)

        # Get user's personal bots that aren't shared yet
        user_bots = conn.execute("""
            SELECT b.* FROM bots b
            WHERE b.user_id = ?
            AND b.id NOT IN (
                SELECT bot_id FROM shared_bots
                WHERE group_id = ? AND is_active = TRUE
            )
            ORDER BY b.created_at DESC
        """, (session["user_id"], group_id)).fetchall()

        conn.close()

        return render_template("group_bots.html",
                             group=group,
                             shared_bots=shared_bots,
                             user_bots=user_bots,
                             username=session.get("username"))

    @app.route("/groups/<int:group_id>/bots/<int:bot_id>") 
    @group_required
    def group_bot_detail(group_id, bot_id):
        """View bot details within group context"""
        conn = get_db_connection()
        
        # Get group
        group = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
        
        # Check if bot is shared with this group
        shared_bot = conn.execute("""
            SELECT b.*, sb.permissions, sb.shared_at, sb.shared_by,
                   u.username as shared_by_name
            FROM shared_bots sb
            JOIN bots b ON sb.bot_id = b.id
            JOIN users u ON sb.shared_by = u.id
            WHERE sb.group_id = ? AND sb.bot_id = ? AND sb.is_active = TRUE
        """, (group_id, bot_id)).fetchone()
        
        if not shared_bot:
            conn.close()
            flash("Bot not found in this group or access denied.", "error")
            return redirect(url_for("group_bots", group_id=group_id))
        
        # Parse permissions
        import json
        bot_dict = dict(shared_bot)
        if bot_dict.get('permissions'):
            try:
                bot_dict['permissions_parsed'] = json.loads(bot_dict['permissions'])
            except:
                bot_dict['permissions_parsed'] = {}
        else:
            bot_dict['permissions_parsed'] = {}
        
        conn.close()
        
        return render_template("bot_detail.html",
                             bot=bot_dict,
                             group=group,
                             session_username=session.get("username"),
                             role=session.get("role", "customer"))

    @app.route("/groups/<int:group_id>/bots/share", methods=["POST"])
    @group_required
    def share_bot_with_group(group_id):
        """Share a bot with group"""
        bot_id = request.form.get("bot_id")
        permissions = request.form.get("permissions", "{}")

        if not bot_id:
            flash("Bot ID is required.", "error")
            return redirect(url_for("group_bots", group_id=group_id))

        user_id = session["user_id"]

        # Verify bot ownership
        conn = get_db_connection()
        bot = conn.execute("SELECT * FROM bots WHERE id = ? AND user_id = ?", (bot_id, user_id)).fetchone()

        if not bot:
            conn.close()
            flash("Bot not found or you don't own it.", "error")
            return redirect(url_for("group_bots", group_id=group_id))

        # Check if already shared
        existing_share = conn.execute("""
            SELECT * FROM shared_bots
            WHERE bot_id = ? AND group_id = ? AND is_active = TRUE
        """, (bot_id, group_id)).fetchone()

        if existing_share:
            conn.close()
            flash("This bot is already shared with the group.", "warning")
            return redirect(url_for("group_bots", group_id=group_id))

        try:
            # Share bot
            conn.execute("""
                INSERT INTO shared_bots (bot_id, group_id, shared_by, permissions)
                VALUES (?, ?, ?, ?)
            """, (bot_id, group_id, user_id, permissions))

            # Log activity
            log_group_activity(group_id, user_id, 'bot_shared', {
                'bot_id': bot_id,
                'bot_name': bot['name'],
                'permissions': permissions
            }, request)

            conn.commit()
            conn.close()

            flash(f"Bot '{bot['name']}' shared with group successfully!", "success")

        except Exception as e:
            conn.rollback()
            conn.close()
            flash(f"Error sharing bot: {str(e)}", "error")

        return redirect(url_for("group_bots", group_id=group_id))

    @app.route("/groups/<int:group_id>/bots/<int:share_id>/unshare", methods=["POST"])
    @group_required
    def unshare_bot(group_id, share_id):
        """Unshare a bot from group"""
        user_id = session["user_id"]

        conn = get_db_connection()

        # Get share info
        share = conn.execute("""
            SELECT sb.*, b.name as bot_name
            FROM shared_bots sb
            JOIN bots b ON sb.bot_id = b.id
            WHERE sb.id = ? AND sb.group_id = ?
        """, (share_id, group_id)).fetchone()

        if not share:
            conn.close()
            flash("Share not found.", "error")
            return redirect(url_for("group_bots", group_id=group_id))

        # Check permission (only owner or bot owner can unshare)
        user_role = conn.execute("""
            SELECT role FROM group_members
            WHERE group_id = ? AND user_id = ? AND status = 'active'
        """, (group_id, user_id)).fetchone()

        is_bot_owner = share['shared_by'] == user_id
        is_group_owner = user_role and user_role['role'] == 'owner'

        if not (is_bot_owner or is_group_owner):
            conn.close()
            flash("You don't have permission to unshare this bot.", "error")
            return redirect(url_for("group_bots", group_id=group_id))

        try:
            # Soft delete (set inactive)
            conn.execute("""
                UPDATE shared_bots
                SET is_active = FALSE
                WHERE id = ?
            """, (share_id,))

            # Log activity
            log_group_activity(group_id, user_id, 'bot_unshared', {
                'bot_id': share['bot_id'],
                'bot_name': share['bot_name'],
                'share_id': share_id
            }, request)

            conn.commit()
            conn.close()

            flash(f"Bot '{share['bot_name']}' unshared from group.", "success")

        except Exception as e:
            conn.rollback()
            conn.close()
            flash(f"Error unsharing bot: {str(e)}", "error")

        return redirect(url_for("group_bots", group_id=group_id))

    @app.route("/groups/<int:group_id>/chat")
    @admin_required
    @group_required
    def group_chat(group_id):
        """Group chat interface - DISABLED"""
        flash("Chat feature has been disabled.", "info")
        return redirect(url_for("group_dashboard", group_id=group_id))

    @app.route("/groups/<int:group_id>/chat/send", methods=["POST"])
    @admin_required
    @group_required
    def send_group_message(group_id):
        """Send message to group chat - DISABLED"""
        flash("Chat feature has been disabled.", "info")
        return redirect(url_for("group_dashboard", group_id=group_id))

    @app.route("/groups/<int:group_id>/templates")
    @group_required
    def group_templates(group_id):
        """Group bot templates"""
        conn = get_db_connection()

        group = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()

        # Get group templates
        templates = conn.execute("""
            SELECT tt.*, u.username as creator_name
            FROM group_templates tt
            JOIN users u ON tt.created_by = u.id
            WHERE tt.group_id = ?
            ORDER BY tt.created_at DESC
        """, (group_id,)).fetchall()

        conn.close()

        return render_template("group_templates.html",
                             group=group,
                             templates=templates,
                             username=session.get("username"))

    @app.route("/groups/<int:group_id>/templates/create", methods=["GET", "POST"])
    @admin_required
    @group_required
    def create_group_template(group_id):
        """Create group template"""
        # Get group details
        conn = get_db_connection()
        group = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
        conn.close()

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip()
            config = request.form.get("config", "{}")
            category = request.form.get("category", "").strip()
            tags = request.form.get("tags", "").strip()

            if not name or not config:
                flash("Name and configuration are required.", "error")
                return render_template("group_template.html",
                                     group=group,
                                     username=session.get("username"))

            user_id = session["user_id"]

            # Validate JSON config
            try:
                config_obj = json.loads(config)
            except json.JSONDecodeError:
                flash("Invalid JSON configuration.", "error")
                return render_template("group_template.html",
                                     group=group,
                                     username=session.get("username"))

            conn = get_db_connection()

            try:
                # Create template
                conn.execute("""
                    INSERT INTO group_templates (group_id, name, description, config, category, created_by, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (group_id, name, description, config, category, user_id, tags))

                # Log activity
                log_group_activity(group_id, user_id, 'template_created', {
                    'template_name': name,
                    'category': category
                }, request)

                conn.commit()
                conn.close()

                flash(f"Template '{name}' created successfully!", "success")
                return redirect(url_for("group_templates", group_id=group_id))

            except Exception as e:
                conn.rollback()
                conn.close()
                flash(f"Error creating template: {str(e)}", "error")
                return render_template("group_template.html",
                                     group=group,
                                     username=session.get("username"))

        return render_template("group_template.html",
                             group=group,
                             username=session.get("username"))

    @app.route("/groups/<int:group_id>/settings", methods=["GET", "POST"])
    def group_settings(group_id):
        """Group settings management (site admin or group creator/admin)"""
        # Allow: site-wide admin, OR group owner/admin
        if session.get('role') != 'admin':
            if not check_group_permission(session.get("user_id"), group_id, 'admin'):
                flash("You don't have permission to access group settings.", "error")
                return redirect(url_for("group_dashboard", group_id=group_id))
        if request.method == "POST":
            # Update group settings
            data = request.form

            conn = get_db_connection()

            try:
                # Get current settings
                group = conn.execute("SELECT settings FROM groups WHERE id = ?", (group_id,)).fetchone()
                current_settings = json.loads(group['settings']) if group['settings'] else {}

                # Update settings
                updated_settings = {
                    **current_settings,
                    'allow_public_invites': 'allow_public_invites' in data,
                    'default_role': data.get('default_role', 'member'),
                    'bot_sharing': 'bot_sharing' in data,
                    'message_history': int(data.get('message_history', 90))
                }

                # Update group
                conn.execute("""
                    UPDATE groups
                    SET settings = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (json.dumps(updated_settings), group_id))

                # Log activity
                log_group_activity(group_id, session["user_id"], 'settings_updated', {
                    'updated_fields': list(data.keys())
                }, request)

                conn.commit()
                conn.close()

                flash("Group settings updated successfully!", "success")

            except Exception as e:
                conn.rollback()
                conn.close()
                flash(f"Error updating settings: {str(e)}", "error")

            return redirect(url_for("group_settings", group_id=group_id))

        # GET request - show settings form
        conn = get_db_connection()
        group = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()

        # Parse settings
        settings = json.loads(group['settings']) if group['settings'] else {}

        conn.close()

        return render_template("group_settings.html",
                             group=group,
                             settings=settings,
                             is_admin=(session.get("role") == "admin"),
                             username=session.get("username"))

    @app.route("/groups/<int:group_id>/delete", methods=["POST"])
    @group_admin_required
    def delete_group(group_id):
        """Permanently delete a group"""
        conn = get_db_connection()
        try:
            # Get group info for logging
            group = conn.execute("SELECT name FROM groups WHERE id = ?", (group_id,)).fetchone()
            if not group:
                flash("Group not found.", "error")
                return redirect(url_for("groups"))

            group_name = group["name"]

            # Delete all related data
            conn.execute("DELETE FROM shared_bots WHERE group_id = ?", (group_id,))
            conn.execute("DELETE FROM group_invitations WHERE group_id = ?", (group_id,))
            conn.execute("DELETE FROM group_members WHERE group_id = ?", (group_id,))
            conn.execute("DELETE FROM group_activity WHERE group_id = ?", (group_id,))
            conn.execute("DELETE FROM group_messages WHERE group_id = ?", (group_id,))
            conn.execute("DELETE FROM group_templates WHERE group_id = ?", (group_id,))
            conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))
            conn.commit()

            print(f"[DELETE GROUP] Group '{group_name}' (ID: {group_id}) deleted by user {session.get('user_id')}")
            flash(f"Group '{group_name}' has been permanently deleted.", "success")
        except Exception as e:
            conn.rollback()
            print(f"[DELETE GROUP] Error deleting group: {e}")
            flash(f"Error deleting group: {str(e)}", "error")
        finally:
            conn.close()

        return redirect(url_for("groups"))

    return app