"""
Magic Bot AI Complete Flask App
With Telegram Bot API + Group Collaboration UI
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file, send_from_directory
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from pathlib import Path
import os
import json
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv

# Load .env file for local dev (silently ignore if not present, e.g. in Docker)
try:
    load_dotenv(override=True)
except Exception:
    pass

# Import Telegram Bot API
from telegram_bot_api import create_telegram_bot_api
from telegram_bot_api_part2 import create_telegram_bot_api_part2

# Import Group Collaboration UI
from group_collaboration_ui import (
    get_db_connection, init_group_db, get_user_groups, get_group_members,
    check_group_permission, log_group_activity, login_required, 
    group_required, group_admin_required, create_group_collaboration_ui
)
from group_collaboration_ui_part2 import create_group_collaboration_ui_part2

# Flask extensions
try:
    from flask_dance.contrib.google import make_google_blueprint, google
    HAS_GOOGLE_OAUTH = True
except ImportError:
    HAS_GOOGLE_OAUTH = False
    print("Note: Flask-Dance not available, Google OAuth disabled")

# Setup — set OAUTHLIB_INSECURE_TRANSPORT for local dev, respect env for production
if 'OAUTHLIB_INSECURE_TRANSPORT' not in os.environ:
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = 'true'

app = Flask(__name__)
app.secret_key = "6ce26db79ba4b1ae2613a1dc4fa4177a75847d40f32347ac9388377a5a7b587b"

# Trust AWS ALB's X-Forwarded-Proto header so Flask-Dance generates HTTPS redirect URIs
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# OAuth setup for Google (if available)
if HAS_GOOGLE_OAUTH:
    # Get Google OAuth credentials from environment
    google_client_id = os.environ.get("GOOGLE_CLIENT_ID")
    google_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    
    # For testing - you can hardcode test credentials here
    # Replace these with real credentials from Google Cloud Console
    if not google_client_id or google_client_id == "your-google-client-id":
        google_client_id = "test-client-id-for-development-only"
        google_client_secret = "test-client-secret-for-development-only"
        print("⚠️  Using test Google OAuth credentials (will not work with real Google)")
        print("    To use real Google OAuth, set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET")
        print("    See GOOGLE_OAUTH_SETUP.md for instructions")
    
    # Create Google OAuth blueprint
    google_bp = make_google_blueprint(
        client_id=google_client_id,
        client_secret=google_client_secret,
        scope=[
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email",
            "openid"
        ],
        redirect_to="index"
    )
    app.register_blueprint(google_bp, url_prefix="/login")
    print(f"✅ Google OAuth configured (using {'TEST' if 'test-client-id' in google_client_id else 'REAL'} credentials)")

DB_FILENAME = Path(__file__).parent / "users.db"

# ==================== Database Initialization ====================

def init_db_complete():
    """Initialize all database tables"""
    conn = get_db_connection()
    
    # Basic tables (from original app)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL DEFAULT 'local',
            provider_id TEXT UNIQUE,
            username TEXT NOT NULL UNIQUE,
            email TEXT,
            password_hash TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            email TEXT,
            organization TEXT,
            messaging TEXT,
            token TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            llm TEXT,
            description TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            last_used TIMESTAMP,
            usage_count INTEGER DEFAULT 0,
            config TEXT,
            webhook_url TEXT,
            api_key TEXT,
            tags TEXT,
            file_folder TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, role_id),
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (role_id) REFERENCES roles (id) ON DELETE CASCADE
        )
    """)
    
    conn.execute("INSERT OR IGNORE INTO roles (name) VALUES ('admin')")
    conn.execute("INSERT OR IGNORE INTO roles (name) VALUES ('customer')")
    
    # Group collaboration tables (will be created by init_group_db)
    init_group_db()
    
    conn.commit()
    # Password reset tokens table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            expires_at TIMESTAMP NOT NULL,
            used BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)

    conn.close()

init_db_complete()

# ==================== Authentication Decorators ====================

def login_required_api(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function


import secrets
from datetime import datetime, timedelta


# ==================== Password Reset ====================

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    """Forgot password page - enter email to receive reset link"""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        
        if not email:
            flash("Please enter your email address.", "error")
            return render_template("forgot_password.html")
        
        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ? AND provider = 'local'",
            (email,)
        ).fetchone()
        
        if user:
            # Generate reset token
            token = secrets.token_urlsafe(48)
            expires_at = (datetime.utcnow() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
            
            conn.execute(
                "INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
                (user["id"], token, expires_at)
            )
            conn.commit()
            
            reset_link = f"{request.host_url}reset_password?token={token}"
            print(f"[PASSWORD RESET] Token generated for {email}: {reset_link}")
            
            # Send reset email via gog CLI
            try:
                import subprocess, tempfile
                email_body = (
                    f"Hello,\n\n"
                    f"You requested a password reset for your Magic Bot AI account.\n\n"
                    f"Click the link below to reset your password (valid for 1 hour):\n"
                    f"{reset_link}\n\n"
                    f"If you did not request this, please ignore this email.\n\n"
                    f"Best,\nMagic Bot AI Team"
                )
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                    f.write(email_body)
                    temp_path = f.name
                result = subprocess.run(
                    ["gog", "mail", "send",
                     "--to", email,
                     "--subject", "Password Reset - Magic Bot AI",
                     "--body-file", temp_path,
                     "--account", "chingtshenbot@gmail.com"],
                    capture_output=True, text=True, timeout=30
                )
                os.unlink(temp_path)
                if result.returncode == 0:
                    print(f"[PASSWORD RESET] Email sent to {email}")
                else:
                    print(f"[PASSWORD RESET] Failed to send email: {result.stderr}")
            except Exception as e:
                print(f"[PASSWORD RESET] Email send error: {e}")
        
        conn.close()
        
        # Always show success to prevent email enumeration
        flash("If that email is registered, you will receive a password reset link shortly.", "info")
        return redirect(url_for("signin_local"))
    
    return render_template("forgot_password.html")


@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    """Reset password page - validate token and set new password"""
    if request.method == "GET":
        token = request.args.get("token", "")
        if not token:
            flash("Missing reset token.", "error")
            return redirect(url_for("signin_local"))
        
        # Validate token
        conn = get_db_connection()
        reset = conn.execute(
            "SELECT * FROM password_reset_tokens WHERE token = ? AND used = 0 AND expires_at > datetime('now')",
            (token,)
        ).fetchone()
        conn.close()
        
        if not reset:
            flash("Invalid or expired reset token.", "error")
            return redirect(url_for("signin_local"))
        
        return render_template("reset_password.html", token=token)
    
    elif request.method == "POST":
        token = request.form.get("token", "")
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        
        if not token or not password or not confirm_password:
            flash("Please fill in all fields.", "error")
            return render_template("reset_password.html", token=token)
        
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("reset_password.html", token=token)
        
        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return render_template("reset_password.html", token=token)
        
        conn = get_db_connection()
        
        # Validate token again
        reset = conn.execute(
            "SELECT * FROM password_reset_tokens WHERE token = ? AND used = 0 AND expires_at > datetime('now')",
            (token,)
        ).fetchone()
        
        if not reset:
            conn.close()
            flash("Invalid or expired reset token.", "error")
            return redirect(url_for("signin_local"))
        
        # Update password
        password_hash = generate_password_hash(password)
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, reset["user_id"])
        )
        
        # Mark token as used
        conn.execute(
            "UPDATE password_reset_tokens SET used = 1 WHERE id = ?",
            (reset["id"],)
        )
        
        conn.commit()
        conn.close()
        
        flash("Password has been reset successfully. You can now sign in with your new password.", "success")
        return redirect(url_for("signin_local"))


# ==================== Core Routes ====================

@app.route("/features/openclaw")
def features_openclaw():
    """OpenClaw platform features page"""
    return render_template("features_openclaw.html")

@app.route("/features/application")
def features_application():
    """Application features page"""
    return render_template("features_application.html")

@app.route("/features/how-to-start")
def features_how_to_start():
    """How to start guide page"""
    return render_template("features_how_to_start.html")

@app.route("/pricing")
def pricing():
    """Pricing page"""
    return render_template("pricing.html")

@app.route("/advertisement")
def advertisement():
    """Advertisement landing page"""
    return render_template("advertisement.html")

@app.route("/api/contact", methods=["POST"])
def handle_contact_form():
    """Handle contact form submissions"""
    try:
        # Get form data
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "message": "No data received"
            }), 400
        
        name = data.get("name", "").strip()
        email = data.get("email", "").strip()
        company = data.get("company", "").strip()
        message = data.get("message", "").strip()
        
        # Validation
        if not name or not email or not message:
            return jsonify({
                "success": False,
                "message": "Please fill in all required fields"
            }), 400
        
        # Email validation
        import re
        email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_regex, email):
            return jsonify({
                "success": False,
                "message": "Please enter a valid email address"
            }), 400
        
        # Save to database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create contacts table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                company TEXT,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'new',
                ip_address TEXT,
                user_agent TEXT
            )
        """)
        
        # Insert contact
        cursor.execute("""
            INSERT INTO contacts (name, email, company, message, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            name,
            email,
            company,
            message,
            request.remote_addr,
            request.headers.get("User-Agent", "")
        ))
        
        conn.commit()
        contact_id = cursor.lastrowid
        conn.close()
        
        # Log the submission
        print(f"[CONTACT FORM] New submission from {name} ({email})")
        print(f"[CONTACT FORM] Message: {message[:100]}...")
        print(f"[CONTACT FORM] Contact ID: {contact_id}")
        
        # TODO: In a real application, you would:
        # 1. Send email notification to admin
        # 2. Send confirmation email to user
        # 3. Add to CRM system
        # 4. Trigger notification in admin dashboard
        
        return jsonify({
            "success": True,
            "message": "Thank you for your message! We'll get back to you within 24 hours.",
            "contact_id": contact_id,
            "data": {
                "name": name,
                "email": email,
                "company": company if company else "Not specified"
            }
        })
        
    except Exception as e:
        print(f"[CONTACT FORM ERROR] {str(e)}")
        return jsonify({
            "success": False,
            "message": "An error occurred. Please try again later."
        }), 500

@app.route("/find_users")
def find_users():
    """Find users page - redirects to users list"""
    # Check if user is logged in and is admin
    if "username" not in session:
        flash("Please log in to access this page", "error")
        return redirect(url_for("signin_local"))
    
    if session.get("role") != "admin":
        flash("Access denied. Admin privileges required.", "error")
        return redirect(url_for("home_with_groups"))
    
    return redirect(url_for("users_list"))

@app.route("/admin/contacts")
def admin_contacts():
    """Admin page to view contact form submissions"""
    # Check if user is logged in and is admin
    if "username" not in session:
        flash("Please log in to access this page", "error")
        return redirect(url_for("signin_local"))
    
    if session.get("role") != "admin":
        flash("Access denied. Admin privileges required.", "error")
        return redirect(url_for("home_with_groups"))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all contacts
    cursor.execute("""
        SELECT id, name, email, company, message, created_at, status
        FROM contacts
        ORDER BY created_at DESC
        LIMIT 100
    """)
    
    contacts = cursor.fetchall()
    conn.close()
    
    # Convert to list of dicts
    contacts_list = []
    for contact in contacts:
        contacts_list.append({
            "id": contact[0],
            "name": contact[1],
            "email": contact[2],
            "company": contact[3] if contact[3] else "Not specified",
            "message": contact[4],
            "created_at": contact[5],
            "status": contact[6]
        })
    
    from datetime import datetime
    return render_template("admin_contacts.html", 
                         contacts=contacts_list,
                         now=datetime.now())

@app.route("/api/contacts/<int:contact_id>/status", methods=["PUT"])
def update_contact_status(contact_id):
    """Update contact status (admin only)"""
    # Check if user is logged in and is admin
    if "username" not in session:
        return jsonify({"success": False, "message": "Authentication required"}), 401
    
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Admin privileges required"}), 403
    
    try:
        data = request.get_json()
        status = data.get("status", "")
        
        if status not in ["new", "read", "replied", "archived"]:
            return jsonify({"success": False, "message": "Invalid status"}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE contacts
            SET status = ?
            WHERE id = ?
        """, (status, contact_id))
        
        conn.commit()
        updated = cursor.rowcount > 0
        conn.close()
        
        if updated:
            return jsonify({
                "success": True,
                "message": f"Status updated to {status}"
            })
        else:
            return jsonify({
                "success": False,
                "message": "Contact not found"
            }), 404
            
    except Exception as e:
        print(f"[CONTACT STATUS ERROR] {str(e)}")
        return jsonify({
            "success": False,
            "message": "An error occurred"
        }), 500

@app.route("/")
def index():
    """Main dashboard"""
    if HAS_GOOGLE_OAUTH and google.authorized:
        try:
            resp = google.get("/oauth2/v2/userinfo")
            if resp.status_code != 200:
                flash(f"Failed to fetch user info: {resp.status_code}")
                return redirect(url_for("landing"))
            user_info = resp.json()
        except Exception as e:
            flash(f"Error fetching user info: {str(e)}")
            return redirect(url_for("landing"))

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE provider = ? AND provider_id = ?", 
            ("google", user_info["id"])
        ).fetchone()
        
        if user:
            conn.close()
        else:
            base_username = user_info["name"].replace(" ", "_").lower()[:30]
            username = base_username
            counter = 1
            
            while True:
                existing = conn.execute(
                    "SELECT * FROM users WHERE username = ?", 
                    (username,)
                ).fetchone()
                
                if not existing:
                    break
                username = f"{base_username}_{counter}"
                counter += 1
                
                if counter > 100:
                    conn.close()
                    flash("Could not create unique username. Please try again.", "error")
                    return redirect(url_for("landing"))
            
            try:
                conn.execute(
                    "INSERT INTO users (provider, provider_id, username, email) VALUES (?, ?, ?, ?)", 
                    ("google", user_info["id"], username, user_info.get("email"))
                )
                
                user = conn.execute(
                    "SELECT * FROM users WHERE provider = ? AND provider_id = ?", 
                    ("google", user_info["id"])
                ).fetchone()
                
                customer_role = conn.execute("SELECT id FROM roles WHERE name = 'customer'").fetchone()
                conn.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (user["id"], customer_role["id"]))
                conn.commit()
                conn.close()
            except Exception as e:
                conn.close()
                flash(f"Database error: {str(e)}", "error")
                return redirect(url_for("landing"))

        conn = get_db_connection()
        role_row = conn.execute("""
            SELECT r.name FROM roles r
            JOIN user_roles ur ON r.id = ur.role_id
            WHERE ur.user_id = ?
        """, (user["id"],)).fetchone()
        conn.close()

        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["provider"] = "google"
        session["role"] = role_row["name"] if role_row else "customer"
    
    if "user_id" not in session:
        return redirect(url_for("landing"))
    
    # Get user stats for dashboard
    user_id = session["user_id"]
    conn = get_db_connection()
    
    # Bot stats
    bot_count = conn.execute("SELECT COUNT(*) as count FROM bots WHERE user_id = ?", (user_id,)).fetchone()["count"]
    
    # Group stats
    group_count = conn.execute("""
        SELECT COUNT(*) as count FROM group_members 
        WHERE user_id = ? AND status = 'active'
    """, (user_id,)).fetchone()["count"]
    
    # Recent bots
    recent_bots = conn.execute("""
        SELECT * FROM bots 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT 5
    """, (user_id,)).fetchall()
    
    # Recent groups
    recent_groups = conn.execute("""
        SELECT t.*, tm.role
        FROM groups t
        JOIN group_members tm ON t.id = tm.group_id
        WHERE tm.user_id = ? AND tm.status = 'active'
        ORDER BY tm.joined_at DESC
        LIMIT 5
    """, (user_id,)).fetchall()
    
    conn.close()
    
    role = session.get("role", "customer")
    
    return render_template("home_with_groups.html", 
                         username=session.get("username"),
                         bot_count=bot_count,
                         group_count=group_count,
                         recent_bots=recent_bots,
                         recent_groups=recent_groups,
                         google=HAS_GOOGLE_OAUTH,
                         role=role)


@app.route("/health")
def health():
    return "OK", 200


@app.route("/landing")
def landing():
    """Public landing page — redirects logged-in users to their bots"""
    if "user_id" in session:
        return redirect(url_for("my_bots"))
    return render_template("landing_with_groups.html", google=HAS_GOOGLE_OAUTH)

@app.route("/landing_with_groups")
def landing_with_groups():
    """Public landing page (alias for /landing)"""
    if "user_id" in session:
        return redirect(url_for("my_bots"))
    return render_template("landing_with_groups.html", google=HAS_GOOGLE_OAUTH)

@app.route("/signin_local", methods=["GET", "POST"])
def signin_local():
    """Local signin"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        if not username or not password:
            flash("Please enter both username and password.", "error")
            return render_template("signin_local.html", google=HAS_GOOGLE_OAUTH)
        
        conn = get_db_connection()
        
        # Try to find user
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND provider = 'local'",
            (username,)
        ).fetchone()
        
        if not user:
            user = conn.execute(
                "SELECT * FROM users WHERE email = ? AND provider = 'local'",
                (username,)
            ).fetchone()
        
        if not user:
            conn.close()
            flash("Invalid username/email or password.", "error")
            return render_template("signin_local.html", google=HAS_GOOGLE_OAUTH)
        
        # Check password
        if not check_password_hash(user["password_hash"], password):
            conn.close()
            flash("Invalid username/email or password.", "error")
            return render_template("signin_local.html", google=HAS_GOOGLE_OAUTH)
            
        role_row = conn.execute("""
            SELECT r.name FROM roles r
            JOIN user_roles ur ON r.id = ur.role_id
            WHERE ur.user_id = ?
        """, (user["id"],)).fetchone()
        
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["provider"] = "local"
        session["role"] = role_row["name"] if role_row else "customer"
        conn.close()
        
        return redirect(url_for("index"))
    
    return render_template("signin_local.html", google=HAS_GOOGLE_OAUTH)

@app.route("/signup_local", methods=["GET", "POST"])
def signup_local():
    """Local signup"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        
        # Validation
        if not username or not email or not password:
            flash("Please fill in all required fields.", "error")
            return render_template("signup_local.html", google=HAS_GOOGLE_OAUTH)
        
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("signup_local.html", google=HAS_GOOGLE_OAUTH)
        
        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return render_template("signup_local.html", google=HAS_GOOGLE_OAUTH)
        
        conn = get_db_connection()
        
        # Check if username already exists
        existing_user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        
        if existing_user:
            conn.close()
            flash("Username already exists. Please choose a different one.", "error")
            return render_template("signup_local.html", google=HAS_GOOGLE_OAUTH)
        
        # Check if email already exists for local provider
        existing_email = conn.execute(
            "SELECT * FROM users WHERE email = ? AND provider = 'local'",
            (email,)
        ).fetchone()
        
        if existing_email:
            conn.close()
            flash("Email already registered for local account.", "error")
            return render_template("signup_local.html", google=HAS_GOOGLE_OAUTH)
        
        # Create user
        password_hash = generate_password_hash(password)
        try:
            conn.execute(
                "INSERT INTO users (provider, username, email, password_hash) VALUES (?, ?, ?, ?)",
                ("local", username, email, password_hash)
            )
            conn.commit()
            
            # Get the new user
            user = conn.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,)
            ).fetchone()
            
            # Check for invitation token and auto-accept if present
            invitation_token = session.get('invitation_token') or request.args.get('invitation')
            if invitation_token:
                print(f"DEBUG: New user signup with invitation token: {invitation_token}")
                try:
                    # Get invitation details
                    invitation = conn.execute("""
                        SELECT ti.*, t.name as group_name
                        FROM group_invitations ti
                        JOIN groups t ON ti.group_id = t.id
                        WHERE ti.token = ? AND ti.status = 'pending'
                        AND ti.expires_at > CURRENT_TIMESTAMP
                        AND ti.email = ?
                    """, (invitation_token, email)).fetchone()
                    
                    if invitation:
                        # Add user to group
                        conn.execute("""
                            INSERT INTO group_members (group_id, user_id, role, invited_by, status)
                            VALUES (?, ?, ?, ?, 'active')
                        """, (invitation['group_id'], user['id'], invitation['role'], invitation['invited_by']))
                        
                        # Update invitation status
                        conn.execute("""
                            UPDATE group_invitations
                            SET status = 'accepted'
                            WHERE id = ?
                        """, (invitation['id'],))
                        
                        conn.commit()
                        print(f"DEBUG: Auto-accepted invitation for new user to group {invitation['group_id']}")
                        
                        # Store group info for redirect after login
                        session['pending_invitation_group'] = invitation['group_id']
                        session['pending_invitation_group_name'] = invitation['group_name']
                    else:
                        print(f"DEBUG: No valid invitation found for token {invitation_token} and email {email}")
                except Exception as invite_error:
                    print(f"DEBUG: Error auto-accepting invitation: {invite_error}")
                    # Don't fail signup if invitation acceptance fails
                    conn.rollback()
                    # Re-commit the user creation
                    conn.commit()
            
            customer_role = conn.execute("SELECT id FROM roles WHERE name = 'customer'").fetchone()
            conn.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (user["id"], customer_role["id"]))
            conn.commit()
            
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["provider"] = "local"
            session["role"] = "customer"
            
            # Clear invitation token from session
            if 'invitation_token' in session:
                session.pop('invitation_token')
            
            conn.close()
            
            # Redirect to group dashboard if we just accepted an invitation
            if 'pending_invitation_group' in session:
                group_id = session['pending_invitation_group']
                group_name = session.get('pending_invitation_group_name', 'the group')
                # Clear the pending invitation info
                session.pop('pending_invitation_group', None)
                session.pop('pending_invitation_group_name', None)
                
                flash(f"Account created successfully! You have been added to '{group_name}'.", "success")
                return redirect(url_for("group_dashboard", group_id=group_id))
            else:
                flash("Account created successfully! Welcome to Magic Bot AI.", "success")
                return redirect(url_for("index"))
            
        except Exception as e:
            conn.close()
            flash(f"Error creating account: {str(e)}", "error")
            return render_template("signup_local.html", google=HAS_GOOGLE_OAUTH)
    
    # Check if there's an invitation token
    invitation_token = session.get('invitation_token') or request.args.get('invitation')
    invitation_info = None
    
    if invitation_token:
        try:
            conn = get_db_connection()
            invitation = conn.execute("""
                SELECT ti.*, t.name as group_name
                FROM group_invitations ti
                JOIN groups t ON ti.group_id = t.id
                WHERE ti.token = ? AND ti.status = 'pending'
                AND ti.expires_at > CURRENT_TIMESTAMP
            """, (invitation_token,)).fetchone()
            conn.close()
            
            if invitation:
                invitation_info = {
                    'group_name': invitation['group_name'],
                    'email': invitation['email']
                }
        except Exception as e:
            print(f"DEBUG: Error getting invitation info: {e}")
    
    return render_template("signup_local.html", 
                         google=HAS_GOOGLE_OAUTH,
                         invitation=invitation_info)

@app.route("/logout")
def logout():
    """Logout user"""
    if HAS_GOOGLE_OAUTH and "provider" in session and session["provider"] == "google" and google.authorized:
        try:
            token = google.token["access_token"]
            google.post(
                "https://accounts.google.com/o/oauth2/revoke",
                params={"token": token},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
        except:
            pass
    
    session.clear()
    return redirect(url_for("landing"))

# The /login/google route is automatically created by Flask-Dance
# when HAS_GOOGLE_OAUTH is True

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """User profile page"""
    user_id = session["user_id"]
    conn = get_db_connection()
    
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        
        try:
            # Password validation if provided
            if password:
                # Check password strength
                if len(password) < 8 or \
                   not any(c.islower() for c in password) or \
                   not any(c.isupper() for c in password) or \
                   not any(c.isdigit() for c in password) or \
                   not any(c in '!@#$%^&*' for c in password):
                    flash('Password must contain at least 8 characters, including uppercase, lowercase, number, and special character', 'error')
                    conn.close()
                    return redirect(url_for('profile'))
                
                # Check password match
                if password != confirm_password:
                    flash('Passwords do not match.', 'error')
                    conn.close()
                    return redirect(url_for('profile'))
                
                # Hash the password
                password_hash = generate_password_hash(password)
                conn.execute("UPDATE users SET email = ?, password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (email, password_hash, user_id))
            else:
                conn.execute("UPDATE users SET email = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (email, user_id))
            
            conn.commit()
            flash("Profile updated successfully!", "success")
        except Exception as e:
            flash(f"Error updating profile: {str(e)}", "error")
            
    # Get user details
    user = conn.execute("""
        SELECT id, username, email, provider, created_at
        FROM users WHERE id = ?
    """, (user_id,)).fetchone()
    
    role_row = conn.execute("""
        SELECT r.name FROM roles r
        JOIN user_roles ur ON r.id = ur.role_id
        WHERE ur.user_id = ?
    """, (user_id,)).fetchone()
    role = role_row["name"] if role_row else "customer"
    
    # Get user's bot count
    bot_count = conn.execute("""
        SELECT COUNT(*) FROM bots WHERE user_id = ?
    """, (user_id,)).fetchone()[0]
    
    # Get user's group count
    group_count = conn.execute("""
        SELECT COUNT(*) FROM group_members WHERE user_id = ? AND status = 'active'
    """, (user_id,)).fetchone()[0]
    
    # Get recent activity
    recent_activity = conn.execute("""
        SELECT 
            'bot_created' as type,
            name,
            created_at as timestamp
        FROM bots 
        WHERE user_id = ?
        UNION ALL
        SELECT 
            'group_joined' as type,
            t.name,
            tm.joined_at as timestamp
        FROM group_members tm
        JOIN groups t ON tm.group_id = t.id
        WHERE tm.user_id = ?
        ORDER BY timestamp DESC
        LIMIT 10
    """, (user_id, user_id)).fetchall()
    
    conn.close()
    
    return render_template("profile_new.html",
                         user=user,
                         bot_count=bot_count,
                         group_count=group_count,
                         recent_activity=recent_activity,
                         username=session.get("username"),
                         role=role)

# ==================== Context Processors ====================

@app.context_processor
def inject_random_background():
    """Inject a random background image for all templates"""
    import random
    
    # List of available background images
    background_images = [
        '/static/AI_IMG1.jpeg',
        '/static/AI_IMG_2.jpeg',
        '/static/AI_IMG_3.jpeg',
        '/static/AI_IMG_4.jpeg'
    ]
    
    # Pick a random image
    random_bg = random.choice(background_images)
    
    return {
        'random_background': random_bg,
        'all_backgrounds': background_images,
        'is_admin': session.get('role') == 'admin'
    }

# ==================== Admin Decorator ====================

def admin_required_route(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role', 'customer') != 'admin':
            flash("Admin privileges required to access this page.", "error")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== Bots Management ====================

@app.route("/admin/bots")
@admin_required_route
def admin_bots():
    """List all bots for admin users"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    
    conn = get_db_connection()
    
    # Get total count
    total_bots = conn.execute("SELECT COUNT(*) FROM bots").fetchone()[0]
    
    # Get paginated bots
    bots = conn.execute("""
        SELECT b.*, u.username as owner_username
        FROM bots b
        LEFT JOIN users u ON b.user_id = u.id
        ORDER BY b.id DESC
        LIMIT ? OFFSET ?
    """, (per_page, offset)).fetchall()
    
    conn.close()
    
    total_pages = (total_bots + per_page - 1) // per_page
    
    return render_template("admin_bots.html",
                         bots=bots,
                         page=page,
                         total_pages=total_pages,
                         total_bots=total_bots,
                         username=session.get("username"),
                         role=session.get("role", "customer"))


@app.route("/my-bots")
@app.route("/my_bots")  # Alias for backward compatibility
@login_required
def my_bots():
    """List user's bots"""
    user_id = session["user_id"]
    role = session.get("role", "customer")
    
    # Redirect admin users to admin bots page
    if role == "admin":
        return redirect(url_for("admin_bots"))
    
    conn = get_db_connection()
    
    # Get user's bots
    bots = conn.execute("""
        SELECT b.* FROM bots b
        WHERE b.user_id = ? 
        ORDER BY b.created_at DESC
    """, (user_id,)).fetchall()
    
    # Get bots shared with user via groups
    shared_bots = conn.execute("""
        SELECT DISTINCT b.*, t.name as group_name, sb.shared_at
        FROM shared_bots sb
        JOIN bots b ON sb.bot_id = b.id
        JOIN groups t ON sb.group_id = t.id
        JOIN group_members tm ON t.id = tm.group_id
        WHERE tm.user_id = ? AND t.is_active = TRUE AND tm.status = 'active' AND b.is_active = TRUE
        ORDER BY sb.shared_at DESC
    """, (user_id,)).fetchall()
    
    conn.close()
    
    return render_template("my_bots_with_groups.html", 
                         bots=bots,
                         shared_bots=shared_bots,
                         username=session.get("username"),
                         role=role)

@app.route("/register-bot")
@app.route("/register_bot")  # Alias for backward compatibility
@app.route("/register-bot/<int:bot_id>")
@app.route("/register_bot/<int:bot_id>")  # Alias for backward compatibility
@login_required
def register_bot(bot_id=None):
    """Register or edit a bot"""
    # Handle query parameter if bot_id not in path
    if bot_id is None:
        bot_id_str = request.args.get('bot_id')
        print(f"Debug: query param bot_id={bot_id_str}")
        if bot_id_str:
            try:
                bot_id = int(bot_id_str)
                print(f"Debug: parsed bot_id={bot_id}")
            except ValueError:
                bot_id = None
    
    bot = None
    role = session.get("role", "customer")
    print(f"Debug: role={role}, session user_id={session.get('user_id')}")
    if bot_id:
        user_id = session["user_id"]
        conn = get_db_connection()
        if role == "admin":
            bot = conn.execute("SELECT * FROM bots WHERE id = ?", (bot_id,)).fetchone()
        else:
            bot = conn.execute("SELECT * FROM bots WHERE id = ? AND user_id = ?", (bot_id, user_id)).fetchone()
        conn.close()
        print(f"Debug: bot raw fetch result={bot}")
        
        # Convert to dict if bot exists
        if bot:
            bot = dict(bot)
            print(f"Debug: bot dict = {bot}")
    
    # Debug: Print bot data for troubleshooting
    print(f"DEBUG: register_bot called with bot_id={bot_id}")
    print(f"DEBUG: Bot data type: {type(bot)}")
    if bot:
        print(f"DEBUG: Bot keys: {list(bot.keys()) if hasattr(bot, 'keys') else 'No keys attribute'}")
        print(f"DEBUG: Bot name: {bot.get('name') if isinstance(bot, dict) else 'Not a dict'}")
    
    return render_template("register_bot_new.html", 
                         bot=bot, 
                         username=session.get("username"),
                         role=role)

@app.route("/check-bot-name")
@login_required
def check_bot_name():
    name = request.args.get("name", "").strip()
    exclude = request.args.get("exclude")
    
    if not name:
        return {"exists": False}
    
    conn = get_db_connection()
    if exclude and exclude.isdigit():
        result = conn.execute("SELECT id FROM bots WHERE name = ? AND id != ?", (name, int(exclude))).fetchone()
    else:
        result = conn.execute("SELECT id FROM bots WHERE name = ?", (name,)).fetchone()
    conn.close()
    
    return {"exists": result is not None}


@app.route("/bot/save", methods=["POST"])
@login_required
def save_bot():
    """Save bot data"""
    user_id = session["user_id"]
    bot_id = request.form.get("bot_id")
    
    # Collect form data
    form_data = {
        'name': request.form.get("name"),
        'email': request.form.get("email"),
        'organization': request.form.get("organization"),
        'messaging': request.form.get("messaging"),
        'llm': request.form.get("llm"),
        'token': request.form.get("token"),
        'description': request.form.get("description", ""),
        'webhook_url': request.form.get("webhook_url", ""),
        'api_key': request.form.get("api_key", ""),
        'tags': request.form.get("tags", ""),
        'file_folder': request.form.get("file_folder", "")
    }
    
    if not form_data['name']:
        flash("Bot Name is required.")
        return redirect(url_for("register_bot"))
    
    # Append _magicAIbot suffix if not already present
    SUFFIX = '_magicAIbot'
    if not form_data['name'].endswith(SUFFIX):
        form_data['name'] = form_data['name'].strip() + SUFFIX
    
    if not form_data['messaging']:
        flash("Messaging Platform is required.")
        return redirect(url_for("register_bot"))
    
    if not form_data['email']:
        flash("Email Address is required.")
        return redirect(url_for("register_bot"))
    
    # Check for duplicate bot name
    conn_check = get_db_connection()
    if bot_id:
        dup = conn_check.execute("SELECT id FROM bots WHERE name = ? AND id != ?", (form_data['name'], int(bot_id))).fetchone()
    else:
        dup = conn_check.execute("SELECT id FROM bots WHERE name = ?", (form_data['name'],)).fetchone()
    if dup:
        flash(f'A bot named "{form_data["name"]}" already exists. Please choose a different name.', "error")
        conn_check.close()
        return redirect(url_for("register_bot", bot_id=bot_id) if bot_id else url_for("register_bot"))
    conn_check.close()
    
    # Prepare config JSON
    config = {
        "messaging_platform": form_data['messaging'],
        "llm_provider": form_data['llm'],
        "webhook_enabled": bool(form_data['webhook_url']),
        "tags": [tag.strip() for tag in form_data['tags'].split(',') if tag.strip()],
        "features": {},
        "created_at": datetime.now().isoformat()
    }
    config_json = json.dumps(config)
    
    conn = get_db_connection()
    role = session.get("role", "customer")
    
    if bot_id:  # Update existing bot
        if role == "admin":
            conn.execute("""
                UPDATE bots 
                SET name = ?, email = ?, organization = ?, messaging = ?, llm = ?, token = ?, 
                    description = ?, webhook_url = ?, api_key = ?, config = ?, tags = ?, file_folder = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (form_data['name'], form_data['email'], form_data['organization'], form_data['messaging'], 
                  form_data['llm'], form_data['token'], form_data['description'], form_data['webhook_url'], 
                  form_data['api_key'], config_json, form_data['tags'], form_data['file_folder'], bot_id))
        else:
            conn.execute("""
                UPDATE bots 
                SET name = ?, email = ?, organization = ?, messaging = ?, llm = ?, token = ?, 
                    description = ?, webhook_url = ?, api_key = ?, config = ?, tags = ?, file_folder = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
            """, (form_data['name'], form_data['email'], form_data['organization'], form_data['messaging'], 
                  form_data['llm'], form_data['token'], form_data['description'], form_data['webhook_url'], 
                  form_data['api_key'], config_json, form_data['tags'], form_data['file_folder'], bot_id, user_id))
        flash("Bot updated successfully!")
    else:  # Create new bot
        conn.execute("""
            INSERT INTO bots (user_id, name, email, organization, messaging, llm, token, 
                             description, webhook_url, api_key, config, tags, file_folder)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, form_data['name'], form_data['email'], form_data['organization'], 
              form_data['messaging'], form_data['llm'], form_data['token'], form_data['description'], 
              form_data['webhook_url'], form_data['api_key'], config_json, form_data['tags'], form_data['file_folder']))
        flash("Bot created successfully!")
    
    conn.commit()
    conn.close()
    
    return redirect(url_for("my_bots"))

@app.route("/bot/<int:bot_id>")
@login_required
def bot_detail(bot_id):
    """View bot details"""
    user_id = session["user_id"]
    role = session.get("role", "customer")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get bot details with permission check
    if role == "admin":
        cursor.execute("SELECT * FROM bots WHERE id = ?", (bot_id,))
    else:
        cursor.execute("SELECT * FROM bots WHERE id = ? AND user_id = ?", (bot_id, user_id))
    
    bot = cursor.fetchone()
    
    if not bot:
        flash("Bot not found or you don't have permission to view it", "error")
        conn.close()
        return redirect(url_for("my_bots"))
    
    # Convert to dict for template
    bot_dict = dict(bot)
    
    conn.close()
    
    return render_template(
        "bot_detail.html",
        bot=bot_dict,
        username=session.get("username"),
        role=role
    )

@app.route("/bot/<int:bot_id>/usage")
@login_required
def bot_usage(bot_id):
    """View usage statistics for a bot's agent"""
    user_id = session["user_id"]
    role = session.get("role", "customer")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get bot
    if role == "admin":
        cursor.execute("SELECT * FROM bots WHERE id = ?", (bot_id,))
    else:
        cursor.execute("SELECT * FROM bots WHERE id = ? AND user_id = ?", (bot_id, user_id))
    
    bot = cursor.fetchone()
    conn.close()
    
    if not bot:
        flash("Bot not found", "error")
        return redirect(url_for("my_bots"))
    
    bot_dict = dict(bot)
    agent_name = bot_dict["name"] + "_agent"
    
    # Load usage data
    # Agent names in trajectory files are lowercased, normalize
    agent_name_lower = agent_name.lower()
    import json, os
    usage_file = "/Users/siyang/.openclaw/workspace-coding/usage_data.json"
    
    if not os.path.exists(usage_file):
        return render_template(
            "bot_usage.html",
            bot=bot_dict,
            agent_name=agent_name,
            no_agent=True,
            no_data=False,
            username=session.get("username"),
            role=role
        )
    
    with open(usage_file) as f:
        try:
            all_usage = json.load(f)
        except:
            all_usage = []
    
    # Find this agent's usage (case-insensitive match)
    agent_usage = None
    for a in all_usage:
        if a.get("agent", "").lower() == agent_name_lower:
            agent_usage = a
            break
    
    if not agent_usage:
        return render_template(
            "bot_usage.html",
            bot=bot_dict,
            agent_name=agent_name,
            no_agent=True,
            no_data=False,
            username=session.get("username"),
            role=role
        )
    
    daily = agent_usage.get("daily", [])
    if not daily:
        return render_template(
            "bot_usage.html",
            bot=bot_dict,
            agent_name=agent_name,
            no_agent=False,
            no_data=True,
            username=session.get("username"),
            role=role
        )
    
    # Build per-day input/output (estimate from total ratio if needed)
    total_tokens = agent_usage.get("total_tokens", 0)
    total_input = agent_usage.get("total_input", 0)
    total_output = agent_usage.get("total_output", 0)
    total_calls = agent_usage.get("total_calls", 0)
    total_runs = agent_usage.get("total_runs", 0)
    first_seen = agent_usage.get("first_seen", "")
    
    # Build chart data with estimated input/output per day
    daily_ratio = (total_input / total_tokens) if total_tokens > 0 else 0.8
    chart_data = []
    for d in daily:
        input_tok = int(d["tokens"] * daily_ratio)
        output_tok = d["tokens"] - input_tok
        chart_data.append({
            "date": d["date"],
            "calls": d["calls"],
            "tokens": d["tokens"],
            "input": input_tok,
            "output": output_tok
        })
    
    return render_template(
        "bot_usage.html",
        bot=bot_dict,
        agent_name=agent_name,
        no_agent=False,
        no_data=False,
        total_tokens=total_tokens,
        total_input=total_input,
        total_output=total_output,
        total_calls=total_calls,
        total_runs=total_runs,
        first_seen=first_seen,
        total_days_active=len(daily),
        daily_data=chart_data,
        chart_data=json.dumps(chart_data),
        username=session.get("username"),
        role=role
    )

@app.route("/bot/files/<int:bot_id>")
@login_required
def bot_files(bot_id):
    """List files saved for a bot"""
    user_id = session["user_id"]
    role = session.get("role", "customer")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get bot
    if role == "admin":
        cursor.execute("SELECT * FROM bots WHERE id = ?", (bot_id,))
    else:
        cursor.execute("SELECT * FROM bots WHERE id = ? AND user_id = ?", (bot_id, user_id))
    
    bot = cursor.fetchone()
    
    if not bot:
        flash("Bot not found or you don't have permission", "error")
        conn.close()
        return redirect(url_for("my_bots"))
    
    bot_dict = dict(bot)
    conn.close()
    
    # Get files from the bot's file folder
    file_folder = bot_dict.get("file_folder", "")
    files = []
    if file_folder and os.path.exists(file_folder):
        for f in sorted(os.listdir(file_folder)):
            full_path = os.path.join(file_folder, f)
            if os.path.isfile(full_path):
                size = os.path.getsize(full_path)
                modified = os.path.getmtime(full_path)
                files.append({
                    "name": f,
                    "size": size,
                    "modified": datetime.fromtimestamp(modified).strftime("%Y-%m-%d %H:%M:%S"),
                    "path": full_path
                })
    
    return render_template(
        "bot_files.html",
        bot=bot_dict,
        files=files,
        username=session.get("username"),
        role=role
    )

import mimetypes


@app.route("/bot/download/<int:bot_id>/<path:filename>")
@login_required
def bot_download_file(bot_id, filename):
    """Download a file from a bot's file folder"""
    user_id = session["user_id"]
    role = session.get("role", "customer")

    conn = get_db_connection()
    cursor = conn.cursor()

    if role == "admin":
        cursor.execute("SELECT * FROM bots WHERE id = ?", (bot_id,))
    else:
        cursor.execute("SELECT * FROM bots WHERE id = ? AND user_id = ?", (bot_id, user_id))

    bot = cursor.fetchone()
    conn.close()

    if not bot:
        flash("Bot not found", "error")
        return redirect(url_for("my_bots"))

    bot_dict = dict(bot)
    file_folder = bot_dict.get("file_folder", "")
    if not file_folder:
        flash("No file folder configured", "error")
        return redirect(url_for("bot_files", bot_id=bot_id))

    # Security: resolve to absolute path and ensure it's inside the file folder
    abs_folder = os.path.abspath(file_folder)
    file_path = os.path.normpath(os.path.join(abs_folder, filename))

    if not file_path.startswith(abs_folder + os.sep):
        flash("Invalid file path", "error")
        return redirect(url_for("bot_files", bot_id=bot_id))

    if not os.path.isfile(file_path):
        flash("File not found", "error")
        return redirect(url_for("bot_files", bot_id=bot_id))

    mime_type, _ = mimetypes.guess_type(filename)
    if not mime_type:
        mime_type = "application/octet-stream"

    return send_file(file_path, mimetype=mime_type, as_attachment=False, download_name=filename)


@app.route("/bot/delete/<int:bot_id>")
@login_required
def delete_bot(bot_id):
    """Delete a bot"""
    user_id = session["user_id"]
    role = session.get("role", "customer")
    conn = get_db_connection()
    if role == "admin":
        conn.execute("DELETE FROM bots WHERE id = ?", (bot_id,))
    else:
        conn.execute("DELETE FROM bots WHERE id = ? AND user_id = ?", (bot_id, user_id))
    conn.commit()
    conn.close()
    
    flash("Bot deleted successfully!")
    return redirect(url_for("my_bots"))

# ==================== API Integrations ====================

# Register Telegram Bot API
create_telegram_bot_api(app)
create_telegram_bot_api_part2(app)

# Register Group Collaboration UI
create_group_collaboration_ui(app)
create_group_collaboration_ui_part2(app)


# ==================== User Management (Admin Only) ====================

@app.route("/users")
@login_required
@admin_required_route
def users_list():
    # Get query parameters
    page = request.args.get('page', 1, type=int)
    sort_by = request.args.get('sort_by', 'id')
    sort_order = request.args.get('sort_order', 'asc')
    
    # Validate sort parameters
    valid_sort_columns = ['id', 'username', 'email', 'created_at', 'updated_at']
    if sort_by not in valid_sort_columns:
        sort_by = 'id'
    
    if sort_order not in ['asc', 'desc']:
        sort_order = 'asc'
    
    # Calculate pagination
    per_page = 20
    offset = (page - 1) * per_page
    
    conn = get_db_connection()
    
    # Get total count
    total_count = conn.execute("SELECT COUNT(*) as count FROM users").fetchone()['count']
    
    # Calculate total pages
    total_pages = (total_count + per_page - 1) // per_page
    
    # Build SQL query with sorting and role
    order_clause = f"u.{sort_by} {sort_order}"
    query = f"""
        SELECT u.*, COALESCE(r.name, 'customer') as user_role
        FROM users u
        LEFT JOIN user_roles ur ON u.id = ur.user_id
        LEFT JOIN roles r ON ur.role_id = r.id
        ORDER BY {order_clause}
        LIMIT ? OFFSET ?
    """
    
    users = conn.execute(query, (per_page, offset)).fetchall()
    conn.close()
    
    return render_template(
        "users.html", 
        users=users, 
        username=session.get("username"), 
        role=session.get("role"),
        page=page,
        total_pages=total_pages,
        total_count=total_count,
        sort_by=sort_by,
        sort_order=sort_order
    )

@app.route("/users/<int:user_id>")
@login_required
@admin_required_route
def user_detail(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        flash("User not found", "error")
        return redirect(url_for('users_list'))
    
    role_row = conn.execute("SELECT r.name FROM roles r JOIN user_roles ur ON r.id = ur.role_id WHERE ur.user_id = ?", (user_id,)).fetchone()
    user_role = role_row['name'] if role_row else 'customer'
    conn.close()
    
    return render_template("user_detail.html", user=user, user_role=user_role, username=session.get("username"), role=session.get("role"))

@app.route("/users/add", methods=["GET", "POST"])
@login_required
@admin_required_route
def user_add():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        role_name = request.form.get("role", "customer")
        
        if not username or not password:
            flash("Username and password are required", "error")
            return render_template("user_form.html", user=None, username=session.get("username"), role=session.get("role"))
        
        # Password strength validation
        if len(password) < 8 or \
           not any(c.islower() for c in password) or \
           not any(c.isupper() for c in password) or \
           not any(c.isdigit() for c in password) or \
           not any(c in '!@#$%^&*' for c in password):
            flash('Password must contain at least 8 characters, including uppercase, lowercase, number, and special character', 'error')
            return render_template("user_form.html", user=None, username=session.get("username"), role=session.get("role"))
        
        # Password match validation
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template("user_form.html", user=None, username=session.get("username"), role=session.get("role"))
            
        conn = get_db_connection()
        existing = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            conn.close()
            flash("Username already exists", "error")
            return render_template("user_form.html", user=None, username=session.get("username"), role=session.get("role"))
            
        try:
            password_hash = generate_password_hash(password)
            conn.execute("INSERT INTO users (provider, username, email, password_hash) VALUES (?, ?, ?, ?)", ("local", username, email, password_hash))
            new_user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            role_id = conn.execute("SELECT id FROM roles WHERE name = ?", (role_name,)).fetchone()['id']
            conn.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (new_user['id'], role_id))
            conn.commit()
            flash("User created successfully", "success")
            conn.close()
            return redirect(url_for('users_list'))
        except Exception as e:
            conn.rollback()
            conn.close()
            flash(f"Error creating user: {e}", "error")
            
    return render_template("user_form.html", user=None, username=session.get("username"), role=session.get("role"))

@app.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required_route
def user_edit(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    
    if not user:
        conn.close()
        flash("User not found", "error")
        return redirect(url_for('users_list'))
        
    role_row = conn.execute("SELECT r.name FROM roles r JOIN user_roles ur ON r.id = ur.role_id WHERE ur.user_id = ?", (user_id,)).fetchone()
    user_role = role_row['name'] if role_row else 'customer'
        
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        new_role = request.form.get("role", "customer")
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        
        try:
            # Password validation if provided
            if password:
                # Check password strength
                if len(password) < 8 or \
                   not any(c.islower() for c in password) or \
                   not any(c.isupper() for c in password) or \
                   not any(c.isdigit() for c in password) or \
                   not any(c in '!@#$%^&*' for c in password):
                    flash('Password must contain at least 8 characters, including uppercase, lowercase, number, and special character', 'error')
                    conn.close()
                    return redirect(url_for('user_edit', user_id=user_id))
                
                # Check password match
                if password != confirm_password:
                    flash('Passwords do not match.', 'error')
                    conn.close()
                    return redirect(url_for('user_edit', user_id=user_id))
                
                password_hash = generate_password_hash(password)
                conn.execute("UPDATE users SET email = ?, password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (email, password_hash, user_id))
            else:
                conn.execute("UPDATE users SET email = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (email, user_id))
                
            role_id = conn.execute("SELECT id FROM roles WHERE name = ?", (new_role,)).fetchone()['id']
            conn.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))
            conn.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (user_id, role_id))
            
            conn.commit()
            flash("User updated successfully", "success")
            conn.close()
            return redirect(url_for('user_detail', user_id=user_id))
        except Exception as e:
            conn.rollback()
            flash(f"Error updating user: {e}", "error")
            
    conn.close()
    return render_template("user_form.html", user=user, user_role=user_role, username=session.get("username"), role=session.get("role"))

@app.route("/users/<int:user_id>/delete", methods=["GET", "POST"])
@login_required
@admin_required_route
def user_delete(user_id):
    if user_id == session.get("user_id"):
        flash("You cannot delete yourself", "error")
        return redirect(url_for('users_list'))
        
    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    flash("User deleted successfully", "success")
    return redirect(url_for('users_list'))

@app.route("/users/<int:user_id>/bots")
@login_required
@admin_required_route
def user_bots(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        flash("User not found", "error")
        return redirect(url_for('users_list'))
        
    bots = conn.execute("SELECT * FROM bots WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    conn.close()
    
    return render_template("user_bots_list.html", user=user, bots=bots, username=session.get("username"), role=session.get("role"))

# ==================== Usage Tracking Page ====================

@app.route("/usage")
def usage_page():
    return send_from_directory("/Users/siyang/.openclaw/workspace-coding", "usage.html")

@app.route("/usage_data.json")
def usage_data():
    return send_from_directory("/Users/siyang/.openclaw/workspace-coding", "usage_data.json")

@app.route("/refresh-usage")
def refresh_usage():
    import subprocess
    result = subprocess.run(
        ["bash", "/Users/siyang/.openclaw/workspace-coding/refresh-usage.sh"],
        capture_output=True, text=True, timeout=30
    )
    return f"<pre>stdout:\n{result.stdout}\nstderr:\n{result.stderr}</pre>"

# ==================== Run Application ====================


if __name__ == "__main__":
    print("=" * 60)
    print("Magic Bot AI - Complete Edition")
    print("=" * 60)
    print(f"Google OAuth: {'Enabled' if HAS_GOOGLE_OAUTH else 'Disabled'}")
    print(f"Telegram Bot API: Enabled (11 endpoints)")
    print(f"Group Collaboration: Enabled")
    print(f"Database: {DB_FILENAME}")
    print("=" * 60)
    print("Features:")
    print("  • User Authentication (Local + Google OAuth)")
    print("  • Bots Management Dashboard")
    print("  • Telegram Bots Management API")
    print("  • Group Collaboration System")
    print("  • Shared Bots & Templates")
    print("  • Group Chat & Analytics")
    print("=" * 60)
    print("Starting server on http://localhost:5000")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=80)