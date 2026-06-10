"""
Group Collaboration UI Part 2 - More routes and templates
Refactored to use shared db.py (SQLite local, PostgreSQL production).
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from db import get_conn, is_postgres
from pathlib import Path
import json
from datetime import datetime, timedelta
import secrets
from functools import wraps

def get_db_connection():
    """Get database connection via shared db.py"""
    return get_conn()

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

    role_hierarchy = {'owner': 4, 'admin': 3, 'member': 2, 'viewer': 1}
    user_role_level = role_hierarchy.get(member['role'], 0)
    required_role_level = role_hierarchy.get(required_role, 0)

    return user_role_level >= required_role_level

def log_group_activity(group_id, user_id, activity_type, activity_data=None, request=None):
    """Log group activity"""
    try:
        conn = get_db_connection()
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
        """Invite someone to group"""
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role", "member")

        if not email:
            flash("Email is required.", "error")
            return redirect(url_for("group_members", group_id=group_id))

        user_id = session["user_id"]

        valid_roles = ['viewer', 'member', 'admin']
        if role not in valid_roles:
            role = 'member'

        conn = None
        try:
            conn = get_db_connection()

            existing_user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

            if existing_user:
                existing_member = conn.execute("""
                    SELECT * FROM group_members
                    WHERE group_id = ? AND user_id = ? AND status = 'active'
                """, (group_id, existing_user['id'])).fetchone()

                if existing_member:
                    conn.close()
                    flash(f"{email} is already a group member.", "warning")
                    return redirect(url_for("group_members", group_id=group_id))

            token = secrets.token_urlsafe(32)
            expires_at = datetime.now() + timedelta(days=7)

            conn.execute("""
                INSERT INTO group_invitations (group_id, email, invited_by, token, role, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (group_id, email, user_id, token, role, expires_at))
            
            group_info = conn.execute("SELECT name FROM groups WHERE id = ?", (group_id,)).fetchone()
            inviter_info = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
            
            conn.commit()
            conn.close()

            try:
                from email_utils import send_group_invitation_email
                
                invitation_data = {
                    'email': email,
                    'group_name': group_info['name'] if group_info else 'Unknown Group',
                    'inviter_name': inviter_info['username'] if inviter_info else 'Unknown User',
                    'token': token,
                    'role': role
                }
                
                app_url = request.host_url.rstrip('/')
                email_sent = send_group_invitation_email(invitation_data, app_url)
                invitation_link = f"{app_url}/groups/invite/accept/{token}"
                
                if email_sent:
                    flash(f"Invitation email sent to {email}. You can also share this link: {invitation_link}", "success")
                else:
                    flash(f"Invitation created for {email}. Email not configured - share this link manually: {invitation_link}", "warning")
                    
            except ImportError:
                flash(f"Invitation created for {email}. Share this link manually: {request.host_url.rstrip('/')}/groups/invite/accept/{token}", "warning")
            except Exception as email_error:
                flash(f"Invitation created for {email} but email failed to send. Share this link: {request.host_url.rstrip('/')}/groups/invite/accept/{token}", "warning")
            
            try:
                log_group_activity(group_id, user_id, 'member_invited', {
                    'email': email,
                    'role': role,
                    'expires_at': expires_at.isoformat(),
                }, request)
            except Exception:
                pass

        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                    conn.close()
                except:
                    pass
            flash(f"Error sending invitation: {e}", "error")
        
        return redirect(url_for("group_members", group_id=group_id))

    @app.route("/groups/<int:group_id>/invite/revoke/<token>", methods=["POST"])
    @group_admin_required
    def revoke_invitation(group_id, token):
        """Revoke a pending invitation"""
        conn = get_db_connection()
        try:
            conn.execute("DELETE FROM group_invitations WHERE token = ? AND group_id = ? AND status = 'pending'", (token, group_id))
            conn.commit()
            flash("Invitation revoked.", "success")
        except Exception as e:
            flash("Failed to revoke invitation.", "error")
        finally:
            conn.close()
        return redirect(url_for("group_members", group_id=group_id))

    @app.route("/groups/invite/accept/<token>")
    def accept_group_invitation(token):
        """Accept group invitation - handles both logged in and new users"""
        conn = None
        try:
            conn = get_db_connection()
            
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
            
            if 'user_id' not in session:
                session['invitation_token'] = token
                flash(f"Please sign up to accept invitation to '{invitation['group_name']}'.", "info")
                return redirect(url_for("signup_local", invitation=token))
            
            user_id = session["user_id"]
            
            conn = get_db_connection()
            
            user = conn.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()

            if not user or user['email'].lower() != invitation['email'].lower():
                conn.close()
                flash("This invitation is not for your account. Please sign up with the email you were invited with.", "error")
                if 'invitation_token' in session:
                    session.pop('invitation_token')
                return redirect(url_for("groups"))

            existing_member = conn.execute("""
                SELECT * FROM group_members
                WHERE group_id = ? AND user_id = ? AND status = 'active'
            """, (invitation['group_id'], user_id)).fetchone()

            if existing_member:
                conn.execute("""
                    UPDATE group_invitations
                    SET status = 'accepted'
                    WHERE id = ?
                """, (invitation['id'],))
                conn.commit()
                conn.close()
                flash(f"You are already a member of '{invitation['group_name']}'.", "info")
                return redirect(url_for("group_dashboard", group_id=invitation['group_id']))

            conn.execute("""
                INSERT INTO group_members (group_id, user_id, role, invited_by, status)
                VALUES (?, ?, ?, ?, 'active')
            """, (invitation['group_id'], user_id, invitation['role'], invitation['invited_by']))

            conn.execute("""
                UPDATE group_invitations
                    SET status = 'accepted'
                    WHERE id = ?
                """, (invitation['id'],))

            try:
                log_group_activity(invitation['group_id'], user_id, 'member_joined', {
                    'invitation_id': invitation['id'],
                    'role': invitation['role']
                }, request)
            except Exception:
                pass

            conn.commit()
            conn.close()
            
            if 'invitation_token' in session:
                session.pop('invitation_token')

            flash(f"You have joined '{invitation['group_name']}'!", "success")
            return redirect(url_for("group_dashboard", group_id=invitation['group_id']))

        except Exception as e:
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

        group = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()

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

        invitations = conn.execute("""
            SELECT ti.*, u.username as invited_by_name
            FROM group_invitations ti
            LEFT JOIN users u ON ti.invited_by = u.id
            WHERE ti.group_id = ? AND ti.status = 'pending'
            ORDER BY ti.created_at DESC
        """, (group_id,)).fetchall()

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
                             username=session.get("username"),
                             role=session.get("role", "customer"))

    @app.route("/groups/<int:group_id>/bots")
    @group_required
    def group_bots(group_id):
        """Group shared bots"""
        conn = get_db_connection()

        group = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()

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

        shared_bots = []
        for bot in shared_bots_raw:
            bot_dict = dict(bot)
            if bot_dict.get('permissions'):
                try:
                    bot_dict['permissions_parsed'] = json.loads(bot_dict['permissions'])
                except:
                    bot_dict['permissions_parsed'] = {}
            else:
                bot_dict['permissions_parsed'] = {}
            shared_bots.append(bot_dict)

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
        
        group = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
        
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

        conn = get_db_connection()
        bot = conn.execute("SELECT * FROM bots WHERE id = ? AND user_id = ?", (bot_id, user_id)).fetchone()

        if not bot:
            conn.close()
            flash("Bot not found or you don't own it.", "error")
            return redirect(url_for("group_bots", group_id=group_id))

        existing_share = conn.execute("""
            SELECT * FROM shared_bots
            WHERE bot_id = ? AND group_id = ? AND is_active = TRUE
        """, (bot_id, group_id)).fetchone()

        if existing_share:
            conn.close()
            flash("This bot is already shared with the group.", "warning")
            return redirect(url_for("group_bots", group_id=group_id))

        try:
            conn.execute("""
                INSERT INTO shared_bots (bot_id, group_id, shared_by, permissions)
                VALUES (?, ?, ?, ?)
            """, (bot_id, group_id, user_id, permissions))

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
            conn.execute("""
                UPDATE shared_bots
                SET is_active = FALSE
                WHERE id = ?
            """, (share_id,))

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

            try:
                config_obj = json.loads(config)
            except json.JSONDecodeError:
                flash("Invalid JSON configuration.", "error")
                return render_template("group_template.html",
                                     group=group,
                                     username=session.get("username"))

            conn = get_db_connection()

            try:
                conn.execute("""
                    INSERT INTO group_templates (group_id, name, description, config, category, created_by, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (group_id, name, description, config, category, user_id, tags))

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
        """Group settings management"""
        if session.get('role') != 'admin':
            if not check_group_permission(session.get("user_id"), group_id, 'admin'):
                flash("You don't have permission to access group settings.", "error")
                return redirect(url_for("group_dashboard", group_id=group_id))

        if request.method == "POST":
            data = request.form

            conn = get_db_connection()

            try:
                group = conn.execute("SELECT settings FROM groups WHERE id = ?", (group_id,)).fetchone()
                current_settings = json.loads(group['settings']) if group['settings'] else {}

                name = data.get("name", "").strip()
                description = data.get("description", "").strip()
                group_chat_id = data.get("group_chat_id", "").strip()

                updated_settings = {
                    **current_settings,
                    'allow_public_invites': 'allow_public_invites' in data,
                    'default_role': data.get('default_role', 'member'),
                    'bot_sharing': 'bot_sharing' in data,
                    'message_history': int(data.get('message_history', 90))
                }

                conn.execute("""
                    UPDATE groups
                    SET name = ?, description = ?, group_chat_id = ?, settings = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (name, description, group_chat_id or None, json.dumps(updated_settings), group_id))

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

        conn = get_db_connection()
        group = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
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
            group = conn.execute("SELECT name FROM groups WHERE id = ?", (group_id,)).fetchone()
            if not group:
                flash("Group not found.", "error")
                return redirect(url_for("groups"))

            group_name = group["name"]

            conn.execute("DELETE FROM shared_bots WHERE group_id = ?", (group_id,))
            conn.execute("DELETE FROM group_invitations WHERE group_id = ?", (group_id,))
            conn.execute("DELETE FROM group_members WHERE group_id = ?", (group_id,))
            conn.execute("DELETE FROM group_activity WHERE group_id = ?", (group_id,))
            conn.execute("DELETE FROM group_messages WHERE group_id = ?", (group_id,))
            conn.execute("DELETE FROM group_templates WHERE group_id = ?", (group_id,))
            conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))
            conn.commit()

            flash(f"Group '{group_name}' has been permanently deleted.", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Error deleting group: {str(e)}", "error")
        finally:
            conn.close()

        return redirect(url_for("groups"))

    return app
