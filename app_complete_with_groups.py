"""
Magic Bot AI Complete Flask App
With Telegram Bot API + Group Collaboration UI
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from pathlib import Path
import os
import json
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
import io

# Database layer - use db.py (SQLite local, PostgreSQL production)
from db import get_conn as get_db_connection, is_postgres as _is_pg_db, connect as _db_connect

# S3 storage (optional, for production)
S3_BUCKET = os.environ.get("S3_BUCKET_NAME", "flask-auth-app-uploads")
S3_ENABLED = bool(os.environ.get("S3_BUCKET_NAME")) or os.path.exists("/.dockerenv")

# Only enable S3 if credentials are available (env vars or IAM role)
has_creds = bool(os.environ.get("AWS_ACCESS_KEY_ID")) or bool(os.environ.get("AWS_SECRET_ACCESS_KEY"))
if has_creds or not os.path.exists("/.dockerenv"):
    S3_ENABLED = S3_ENABLED and has_creds

s3_client = None
if S3_ENABLED:
    try:
        import boto3
        s3_client = boto3.client("s3", region_name="us-east-1")
        # Verify bucket exists / is accessible
        s3_client.head_bucket(Bucket=S3_BUCKET)
        print(f"S3 storage enabled: bucket={S3_BUCKET}")
    except Exception as e:
        print(f"S3 storage not available, falling back to local filesystem: {e}")
        S3_ENABLED = False
        s3_client = None

# Load .env file for local dev (silently ignore if not present, e.g. in Docker)
# Skip in production when env vars are set via build args or system env.
if not os.environ.get('SKIP_DOTENV'):
    try:
        load_dotenv(override=True)
    except Exception:
        pass

# Import Telegram Bot API
from telegram_bot_api import create_telegram_bot_api
from telegram_bot_api_part2 import create_telegram_bot_api_part2

# Import Group Collaboration UI
from group_collaboration_ui import (
    init_group_db, get_user_groups, get_group_members,
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

# Setup - set OAUTHLIB_INSECURE_TRANSPORT for local dev, respect env for production
if 'OAUTHLIB_INSECURE_TRANSPORT' not in os.environ:
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = 'true'

app = Flask(__name__)
app.secret_key = "6ce26db79ba4b1ae2613a1dc4fa4177a75847d40f32347ac9388377a5a7b587b"

# Force HTTPS for redirect URIs (AWS ALB terminates SSL, so Flask sees HTTP)
# ProxyFix would be ideal but requires X-Forwarded-Proto, which Express Mode may not send
from flask import Flask as FlaskBase
class FixedFlask(FlaskBase):
    def __call__(self, environ, start_response):
        environ['wsgi.url_scheme'] = 'https'
        return super().__call__(environ, start_response)
# Override the existing app's __class__ so it uses FixedFlask
app.__class__ = FixedFlask

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

# ==================== Database Initialization ====================

def _int_pk(is_pg):
    """Return appropriate primary key type"""
    if is_pg:
        return "SERIAL PRIMARY KEY"
    return "INTEGER PRIMARY KEY AUTOINCREMENT"

def _on_conflict_prefix(is_pg):
    """SQLite prefix: ' OR IGNORE' between INSERT and INTO"""
    return "" if is_pg else " OR IGNORE"

def _on_conflict_suffix(is_pg, action="NOTHING"):
    """PG suffix: ' ON CONFLICT DO NOTHING' after VALUES"""
    return f" ON CONFLICT DO {action}" if is_pg else ""

def _is_pg():
    """Check if we're running on PostgreSQL"""
    return _is_pg_db()

def init_db_complete():
    """Initialize all database tables (supports both SQLite and PostgreSQL)"""
    pg = _is_pg()
    pk = _int_pk(pg)
    conn = get_db_connection()

    # Basic tables (from original app)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS users (
            id {pk},
            provider TEXT NOT NULL DEFAULT 'local',
            provider_id TEXT UNIQUE,
            username TEXT NOT NULL UNIQUE,
            email TEXT,
            password_hash TEXT,
            referral_credits INTEGER DEFAULT 0,
            referral_badge TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS bots (
            id {pk},
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
            online INTEGER DEFAULT 0,
            last_used TIMESTAMP,
            usage_count INTEGER DEFAULT 0,
            config TEXT,
            webhook_url TEXT,
            api_key TEXT,
            tags TEXT,
            file_folder TEXT
            {"" if pg else ", FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE"}
        )
    """)

    # Bot migration: is_active, online, status columns
    try:
        if pg:
            # PostgreSQL supports IF NOT EXISTS
            conn.execute("ALTER TABLE bots ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE")
            conn.execute("ALTER TABLE bots ADD COLUMN IF NOT EXISTS online INTEGER DEFAULT 0")
            conn.execute("UPDATE bots SET online = 0 WHERE online IS NULL")
            conn.execute("ALTER TABLE bots ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active'")
        else:
            # SQLite - catch errors if column already exists
            try:
                conn.execute("ALTER TABLE bots ADD COLUMN is_active BOOLEAN DEFAULT TRUE")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE bots ADD COLUMN online INTEGER DEFAULT 0")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE bots ADD COLUMN status TEXT DEFAULT 'active'")
            except Exception:
                pass
            conn.execute("UPDATE bots SET online = 0 WHERE online IS NULL")
        conn.execute("UPDATE bots SET status = 'active' WHERE status IS NULL")
        conn.commit()
    except Exception as e:
        print(f"Bot column migration error (non-fatal): {e}")

    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS roles (
            id {pk},
            name TEXT NOT NULL UNIQUE
        )
    """)

    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, role_id){"" if pg else ","}
            {"" if pg else "FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,"}
            {"" if pg else "FOREIGN KEY (role_id) REFERENCES roles (id) ON DELETE CASCADE"}
        )
    """)

    insert_role = _on_conflict_suffix(pg)
    conn.execute(f"""INSERT{_on_conflict_prefix(pg)} INTO roles (name) VALUES ('admin'){insert_role}""")
    conn.execute(f"""INSERT{_on_conflict_prefix(pg)} INTO roles (name) VALUES ('customer'){insert_role}""")

    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS referrals (
            id {pk},
            referrer_user_id INTEGER NOT NULL,
            your_name TEXT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            relationship TEXT,
            signed_up_user_id INTEGER,
            reward_given BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP{"" if pg else ","}
            {"" if pg else "FOREIGN KEY (referrer_user_id) REFERENCES users (id) ON DELETE CASCADE,"}
            {"" if pg else "FOREIGN KEY (signed_up_user_id) REFERENCES users (id) ON DELETE SET NULL"}
        )
    """)

    # Migration: add referral columns to existing users table
    for col_sql, col_name in [
        ("ALTER TABLE users ADD COLUMN referral_credits INTEGER DEFAULT 0", "referral_credits"),
        ("ALTER TABLE users ADD COLUMN referral_badge TEXT DEFAULT NULL", "referral_badge"),
        ("ALTER TABLE referrals ADD COLUMN reward_given BOOLEAN DEFAULT FALSE", "reward_given"),
        ("ALTER TABLE users ADD COLUMN preferred_platform TEXT DEFAULT NULL", "preferred_platform"),
        ("ALTER TABLE users ADD COLUMN platform_user_id TEXT DEFAULT NULL", "platform_user_id"),
    ]:
        if pg:
            # Check if column exists in PG
            chk = conn.execute(f"""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = '{col_sql.split()[2]}' AND column_name = '{col_name}'
            """).fetchone()
            if not chk:
                print(f"[DB] Added {col_name} column")
                conn.execute(col_sql)
        else:
            try:
                conn.execute(col_sql)
                print(f"[DB] Added {col_name} column")
            except Exception:
                pass

    # Reward tiers table
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS reward_tiers (
            id {pk},
            min_referrals INTEGER NOT NULL,
            max_referrals INTEGER,
            badge_name TEXT NOT NULL UNIQUE,
            badge_icon TEXT NOT NULL,
            credits_reward INTEGER DEFAULT 0,
            description TEXT
        )
    """)

    # Reward redemptions table
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS reward_redemptions (
            id {pk},
            user_id INTEGER NOT NULL,
            reward_type TEXT NOT NULL,
            credits_spent INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Reset reward tiers to clean state
    conn.execute('DROP TABLE IF EXISTS reward_tiers')
    conn.execute(f"""
        CREATE TABLE reward_tiers (
            id {pk},
            min_referrals INTEGER NOT NULL,
            max_referrals INTEGER,
            badge_name TEXT NOT NULL UNIQUE,
            badge_icon TEXT NOT NULL,
            credits_reward INTEGER DEFAULT 0,
            description TEXT
        )
    """)

    # Seed reward tiers
    reward_tiers_data = [
        (0, 0, 'Newcomer', '🌱', 0, 'Start referring friends to earn badges!'),
        (1, 2, 'Helper', '🌟', 1, 'You referred your first person!'),
        (3, 4, 'Contributor', '⭐', 3, '3 referrals - you are making an impact!'),
        (5, 9, 'Advisor', '🏅', 5, '5 referrals - people trust your recommendations!'),
        (10, 24, 'Champion', '🥇', 10, '10 referrals - you are a referral champion!'),
        (25, 49, 'Ambassador', '👑', 25, '25 referrals - you are an ambassador!'),
        (50, None, 'Legend', '💎', 50, '50 referrals - LEGENDARY status!'),
    ]
    conflict_clause = _on_conflict_suffix(pg)
    conn.executemany(
        f"INSERT{_on_conflict_prefix(pg)} INTO reward_tiers (min_referrals, max_referrals, badge_name, badge_icon, credits_reward, description) VALUES (?, ?, ?, ?, ?, ?){conflict_clause}",
        reward_tiers_data
    )

    # Group collaboration tables (will be created by init_group_db)
    init_group_db(conn)

    # Password reset tokens table
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id {pk},
            user_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            expires_at TIMESTAMP NOT NULL,
            used BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
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
            "SELECT * FROM password_reset_tokens WHERE token = ? AND used = 0 AND expires_at > " + ("NOW()" if _is_pg_db() else "datetime('now')") + "",
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
            "SELECT * FROM password_reset_tokens WHERE token = ? AND used = 0 AND expires_at > " + ("NOW()" if _is_pg_db() else "datetime('now')") + "",
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

@app.route("/features/qa")
def features_qa():
    """Q&A page"""
    return render_template("features_qa.html")

@app.route("/pricing")
def pricing():
    """Pricing page"""
    return render_template("pricing.html")

@app.route("/referral-program")
def referral_program():
    """Public referral program page"""
    return render_template("referral_program.html")


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
        SELECT id, name, email, company, message, created_at, status, ip_address
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
            "status": contact[6],
            "ip_address": contact[7] if len(contact) > 7 and contact[7] else "N/A"
        })

    from datetime import datetime
    return render_template("admin_contacts.html",
                         contacts=contacts_list,
                         now=datetime.now(),
                         username=session.get("username"),
                         role=session.get("role", "customer"))

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

@app.route("/api/contacts/<int:contact_id>", methods=["GET"])
def get_contact_detail(contact_id):
    """Get single contact details (admin only)"""
    if "username" not in session:
        return jsonify({"success": False, "message": "Authentication required"}), 401

    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Admin privileges required"}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, email, company, message, created_at, status, ip_address, user_agent
            FROM contacts WHERE id = ?
        """, (contact_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify({"success": False, "message": "Contact not found"}), 404

        # Auto-mark as read when viewed
        if row[6] == "new":
            cursor = conn.cursor()
            cursor.execute("UPDATE contacts SET status = 'read' WHERE id = ?", (contact_id,))
            conn.commit()

        return jsonify({
            "success": True,
            "contact": {
                "id": row[0],
                "name": row[1],
                "email": row[2],
                "company": row[3] or "Not specified",
                "message": row[4],
                "created_at": row[5],
                "status": row[6],
                "ip_address": row[7] or "N/A",
                "user_agent": row[8] or "N/A"
            }
        })
    except Exception as e:
        print(f"[CONTACT DETAIL ERROR] {str(e)}")
        return jsonify({"success": False, "message": "An error occurred"}), 500

@app.route("/legal/privacy")
def legal_privacy():
    return render_template("legal.html", page="privacy")


@app.route("/legal/terms")
def legal_terms():
    return render_template("legal.html", page="terms")


@app.route("/legal/cookies")
def legal_cookies():
    return render_template("legal.html", page="cookies")


@app.route("/legal/gdpr")
def legal_gdpr():
    return render_template("legal.html", page="gdpr")


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

                # Update any pending referrals that match this email
                conn.execute("""
                    UPDATE referrals SET signed_up_user_id = ?
                    WHERE email = ? AND signed_up_user_id IS NULL
                """, (user["id"], user_info.get("email")))

                # Check if a referrer referred this user - reward them
                referrer_id = session.pop('referrer_id', None)
                if referrer_id:
                    referrer = conn.execute("SELECT id FROM users WHERE id = ?", (referrer_id,)).fetchone()
                    if referrer and referrer['id'] != user['id']:
                        conn.execute(
                            "UPDATE users SET referral_credits = referral_credits + 1 WHERE id = ?",
                            (referrer_id,)
                        )
                        conn.execute(
                            "UPDATE referrals SET reward_given = TRUE WHERE referrer_user_id = ? AND email = ?",
                            (referrer_id, user_info.get("email"))
                        )
                        print(f"[REFERRAL] Referrer {referrer_id} earned 1 credit for Google-signup {user_info.get('email')}")

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

    # Referral stats
    referral_credits = conn.execute(
        "SELECT referral_credits FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    referral_signed_up = conn.execute(
        "SELECT COUNT(*) as cnt FROM referrals WHERE referrer_user_id = ? AND signed_up_user_id IS NOT NULL",
        (user_id,)
    ).fetchone()["cnt"]
    referral_credits_val = referral_credits["referral_credits"] if referral_credits else 0

    conn.close()

    role = session.get("role", "customer")

    return render_template("home_with_groups.html",
                         username=session.get("username"),
                         bot_count=bot_count,
                         group_count=group_count,
                         recent_bots=recent_bots,
                         recent_groups=recent_groups,
                         referral_credits=referral_credits_val,
                         referral_signed_up=referral_signed_up,
                         google=HAS_GOOGLE_OAUTH,
                         role=role)


@app.route("/health")
def health():
    return "OK", 200


@app.route("/debug/env")
def debug_env():
    """Debug endpoint to check env vars (safe, no secrets exposed)"""
    cid = os.environ.get("GOOGLE_CLIENT_ID", "NOT SET")
    # Mask the secret: show first 25 chars and last 10
    if cid and cid != "NOT SET" and len(cid) > 35:
        masked = cid[:30] + "..." + cid[-10:]
    else:
        masked = cid
    return {
        "GOOGLE_CLIENT_ID_length": len(cid) if cid != "NOT SET" else 0,
        "GOOGLE_CLIENT_ID_value": masked,
        "OAUTHLIB_INSECURE_TRANSPORT": os.environ.get("OAUTHLIB_INSECURE_TRANSPORT", "NOT SET"),
        "FLASK_SECRET_KEY_set": "FLASK_SECRET_KEY" in os.environ,
        "wsgi_url_scheme_override": str(app.__class__.__name__ == "FixedFlask")
    }


@app.route("/landing")
def landing():
    """Public landing page - redirects logged-in users to their bots"""
    # Capture referrer from URL parameter for Google OAuth users
    ref_param = request.args.get('ref', '').strip()
    if ref_param and ref_param.isdigit():
        session['referrer_id'] = int(ref_param)
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
    # Capture referrer from URL parameter
    ref_param = request.args.get('ref', '').strip()
    if ref_param and ref_param.isdigit():
        session['referrer_id'] = int(ref_param)

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

            # Update any pending referrals that match this email
            conn.execute("""
                UPDATE referrals SET signed_up_user_id = ?
                WHERE email = ? AND signed_up_user_id IS NULL
            """, (user["id"], email))

            # Check if a referrer referred this user - reward them
            referrer_id = session.pop('referrer_id', None)
            if referrer_id:
                referrer = conn.execute("SELECT id, referral_credits FROM users WHERE id = ?", (referrer_id,)).fetchone()
                if referrer:
                    # Check that the referrer didn't refer themselves
                    if referrer['id'] != user['id']:
                        # Grant 1 credit to referrer
                        conn.execute(
                            "UPDATE users SET referral_credits = referral_credits + 1 WHERE id = ?",
                            (referrer_id,)
                        )
                        # Mark this referral as rewarded
                        conn.execute(
                            "UPDATE referrals SET reward_given = TRUE WHERE referrer_user_id = ? AND email = ?",
                            (referrer_id, email)
                        )
                        print(f"[REFERRAL] Referrer {referrer_id} earned 1 credit for referring {email}")
                        flash('You were referred by a friend! Welcome! 🎉', 'success')

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
        preferred_platform = request.form.get("preferred_platform", "").strip()
        platform_user_id = request.form.get("platform_user_id", "").strip()

        if not preferred_platform:
            flash("Preferred Platform is required.", "error")
            conn.close()
            return redirect(url_for('profile'))

        if not platform_user_id:
            flash("Platform User ID is required.", "error")
            conn.close()
            return redirect(url_for('profile'))

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
                conn.execute("UPDATE users SET email = ?, password_hash = ?, preferred_platform = ?, platform_user_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (email, password_hash, preferred_platform, platform_user_id, user_id))
            else:
                conn.execute("UPDATE users SET email = ?, preferred_platform = ?, platform_user_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (email, preferred_platform, platform_user_id, user_id))

            conn.commit()
            flash("Profile updated successfully!", "success")
        except Exception as e:
            flash(f"Error updating profile: {str(e)}", "error")

    # Get user details
    user = conn.execute("""
        SELECT id, username, email, provider, preferred_platform, platform_user_id, created_at
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

    # Fetch user's email for default value
    user_email = ""
    try:
        conn = get_db_connection()
        user = conn.execute("SELECT email FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        if user:
            user_email = user["email"]
        conn.close()
    except Exception as e:
        print(f"DEBUG: Error fetching user email: {e}")

    return render_template("register_bot_new.html",
                         bot=bot,
                         username=session.get("username"),
                         role=role,
                         user_email=user_email)

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
        'messaging': request.form.get("messaging", "Not Set"),
        'llm': request.form.get("llm"),
        'token': request.form.get("token"),
        'description': request.form.get("description", ""),
        'webhook_url': request.form.get("webhook_url", ""),
        'api_key': request.form.get("api_key", ""),
        'tags': request.form.get("tags", ""),
        'file_folder': request.form.get("file_folder", ""),
        'online': 1 if request.form.get("online") == "1" else 0
    }

    if not form_data['name']:
        flash("Bot Name is required.")
        return redirect(url_for("register_bot"))

    # Validate bot name ends with "bot" or "Bot"
    if not form_data['name'].strip().lower().endswith('bot'):
        flash('Bot name must end with "bot" or "Bot" (e.g., TetrisBot, tetris_bot).')
        return redirect(url_for("register_bot", bot_id=bot_id) if bot_id else url_for("register_bot"))


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
                    description = ?, webhook_url = ?, api_key = ?, config = ?, tags = ?, file_folder = ?, online = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (form_data['name'], form_data['email'], form_data['organization'], form_data['messaging'],
                  form_data['llm'], form_data['token'], form_data['description'], form_data['webhook_url'],
                  form_data['api_key'], config_json, form_data['tags'], form_data['file_folder'], form_data['online'], bot_id))
        else:
            conn.execute("""
                UPDATE bots
                SET name = ?, email = ?, organization = ?, messaging = ?, llm = ?, token = ?,
                    description = ?, webhook_url = ?, api_key = ?, config = ?, tags = ?, file_folder = ?, online = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
            """, (form_data['name'], form_data['email'], form_data['organization'], form_data['messaging'],
                  form_data['llm'], form_data['token'], form_data['description'], form_data['webhook_url'],
                  form_data['api_key'], config_json, form_data['tags'], form_data['file_folder'], form_data['online'], bot_id, user_id))
        flash("Bot updated successfully!")
    else:  # Create new bot - default status is 'pending'
        conn.execute("""
            INSERT INTO bots (user_id, name, email, organization, messaging, llm, token,
                             description, webhook_url, api_key, config, tags, file_folder, online, status, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', FALSE)
        """, (user_id, form_data['name'], form_data['email'], form_data['organization'],
              form_data['messaging'], form_data['llm'], form_data['token'], form_data['description'],
              form_data['webhook_url'], form_data['api_key'], config_json, form_data['tags'], form_data['file_folder'], form_data['online']))
        flash("Bot created successfully! Our team will review and activate it shortly.")

    conn.commit()
    conn.close()

    return redirect(url_for("my_bots"))

# ==================== Email helpers (SMTP, works on ECS) ====================

def send_bot_activation_email(bot_name, recipient_email):
    """
    Send bot activation notification via SMTP using magicopenclawbot@gmail.com.
    Works in AWS ECS (no keychain/gog dependency).
    """
    import smtplib
    from email.mime.text import MIMEText

    smtp_user = "magicopenclawbot@gmail.com"
    # App Password stored in env var - set in ECS task definition or local .env
    smtp_pass = os.environ.get("GMAIL_BOT_APP_PASSWORD", "")

    if not smtp_pass:
        print("[ACTIVATE] GMAIL_BOT_APP_PASSWORD not set, skipping email")
        return False

    subject = f"Your Bot is Ready - {bot_name}"
    body = (
        f"Dear Customer,\n\n"
        f"your new Telegram bot, {bot_name}, is\n"
        f"ready for use. Search for the bot name directly in Telegram to get\n"
        f"started. Enjoy your new bot!\n\n"
        f"Magic Bot AI team"
    )

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = f"Magic Bot AI <{smtp_user}>"
    msg["To"] = recipient_email

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        print(f"[ACTIVATE] Activation email sent to {recipient_email}")
        return True
    except Exception as e:
        print(f"[ACTIVATE] Failed to send email: {e}")
        return False


@app.route("/admin/bot/<int:bot_id>/activate", methods=["POST"])
@admin_required_route
def admin_activate_bot(bot_id):
    """Activate a pending bot and send notification email"""
    conn = get_db_connection()
    bot = conn.execute("SELECT * FROM bots WHERE id = ?", (bot_id,)).fetchone()

    if not bot:
        conn.close()
        flash("Bot not found.", "error")
        return redirect(url_for("admin_bots"))

    if bot["status"] == "active":
        conn.close()
        flash(f"Bot '{bot['name']}' is already active.", "info")
        return redirect(url_for("admin_bots"))

    # Update status to active
    conn.execute(
        "UPDATE bots SET status = 'active', is_active = TRUE, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (bot_id,)
    )
    conn.commit()
    conn.close()

    # Send activation email
    recipient_email = bot["email"] or ""
    if recipient_email:
        send_bot_activation_email(bot["name"], recipient_email)
    else:
        print(f"[ACTIVATE] Bot {bot_id} has no email, skipping notification")

    flash(f"Bot '{bot['name']}' has been activated. Email sent to {recipient_email}.", "success")
    return redirect(url_for("admin_bots"))

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
    role = session.get("role", "customer")

    # Restrict to admins only (usage data file may not exist for non-admins)
    if role != "admin":
        flash("Usage statistics are only available for admin users.", "error")
        return redirect(url_for("my_bots"))

    user_id = session["user_id"]

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get bot
    cursor.execute("SELECT * FROM bots WHERE id = ?", (bot_id,))

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
    usage_file = os.environ.get("USAGE_DATA_FILE", "/Users/siyang/.openclaw/workspace-coding/usage_data.json")

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
    if file_folder:
        if S3_ENABLED and s3_client:
            # List files from S3
            prefix = file_folder.strip("/")
            try:
                resp = s3_client.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix + "/")
                for obj in resp.get("Contents", []):
                    key = obj["Key"]
                    filename = key[len(prefix)+1:]
                    if not filename:
                        continue
                    files.append({
                        "name": filename,
                        "size": obj["Size"],
                        "modified": obj["LastModified"].strftime("%Y-%m-%d %H:%M:%S"),
                        "s3_key": key
                    })
            except Exception as e:
                print(f"Error listing S3 objects: {e}")
        elif os.path.exists(file_folder):
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

    if S3_ENABLED and s3_client:
        # Download from S3
        s3_key = f"{file_folder.strip('/')}/{filename}"
        try:
            obj = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
            file_bytes = obj["Body"].read()
            mime_type, _ = mimetypes.guess_type(filename)
            if not mime_type:
                mime_type = obj.get("ContentType", "application/octet-stream")
            from io import BytesIO
            return send_file(
                BytesIO(file_bytes),
                mimetype=mime_type,
                as_attachment=False,
                download_name=filename
            )
        except s3_client.exceptions.NoSuchKey as e:
            print(f"S3 key not found: {s3_key}")
            flash("File not found", "error")
            return redirect(url_for("bot_files", bot_id=bot_id))
    else:
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
    valid_sort_columns = ['id', 'username', 'email', 'provider', 'preferred_platform', 'platform_user_id', 'created_at', 'updated_at', 'user_role']
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
    if sort_by == 'user_role':
        order_clause = f"r.name {sort_order}"
    else:
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

            # Update any pending referrals that match this email
            conn.execute("""
                UPDATE referrals SET signed_up_user_id = ?
                WHERE email = ? AND signed_up_user_id IS NULL
            """, (new_user['id'], email))

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
        preferred_platform = request.form.get("preferred_platform", "").strip()
        platform_user_id = request.form.get("platform_user_id", "").strip()

        if not preferred_platform:
            flash("Preferred Platform is required.", "error")
            conn.close()
            return redirect(url_for('user_edit', user_id=user_id))

        if not platform_user_id:
            flash("Platform User ID is required.", "error")
            conn.close()
            return redirect(url_for('user_edit', user_id=user_id))

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
                conn.execute("UPDATE users SET email = ?, password_hash = ?, preferred_platform = ?, platform_user_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (email, password_hash, preferred_platform, platform_user_id, user_id))
            else:
                conn.execute("UPDATE users SET email = ?, preferred_platform = ?, platform_user_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (email, preferred_platform, platform_user_id, user_id))

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
    if session.get("role") != "admin":
        flash("Access denied. Admin privileges required.", "error")
        return redirect(url_for("index"))
    return render_template("usage.html")

@app.route("/usage_data.json")
def usage_data():
    if session.get("role") != "admin":
        return jsonify({"error": "Access denied. Admin privileges required."}), 403
    import os
    usage_dir = os.environ.get("USAGE_DATA_DIR", "/Users/siyang/.openclaw/workspace-coding")
    usage_file = os.path.join(usage_dir, "usage_data.json")
    if not os.path.exists(usage_file):
        return jsonify({"error": "Usage data file not found. The usage report may not have been generated yet."}), 404
    return send_from_directory(usage_dir, "usage_data.json")

@app.route("/refresh-usage")
def refresh_usage():
    if session.get("role") != "admin":
        flash("Access denied. Admin privileges required.", "error")
        return redirect(url_for("index"))
    import subprocess
    result = subprocess.run(
        ["bash", os.environ.get("REFRESH_USAGE_SCRIPT", "/Users/siyang/.openclaw/workspace-coding/refresh-usage.sh")],
        capture_output=True, text=True, timeout=30
    )
    return f"<pre>stdout:\n{result.stdout}\nstderr:\n{result.stderr}</pre>"

# ==================== Referral API - Share Link Info ====================

@app.route("/api/referral/info")
def api_referral_info():
    """JSON endpoint with referral stats for the current user"""
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    user_id = session["user_id"]
    conn = get_db_connection()

    user = conn.execute(
        "SELECT id, username, referral_credits, referral_badge FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    signed_up_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM referrals WHERE referrer_user_id = ? AND signed_up_user_id IS NOT NULL",
        (user_id,)
    ).fetchone()["cnt"]

    # Determine current badge
    badge = conn.execute(
        "SELECT * FROM reward_tiers WHERE min_referrals <= ? AND (max_referrals IS NULL OR max_referrals >= ?) ORDER BY min_referrals DESC LIMIT 1",
        (signed_up_count, signed_up_count)
    ).fetchone()

    # Next tier
    next_tier = conn.execute(
        "SELECT * FROM reward_tiers WHERE min_referrals > ? ORDER BY min_referrals ASC LIMIT 1",
        (signed_up_count,)
    ).fetchone()

    conn.close()

    return jsonify({
        "referral_link": f"{request.host_url.rstrip('/')}/signup_local?ref={user_id}",
        "credits": user["referral_credits"],
        "signed_up_referrals": signed_up_count,
        "badge_name": badge["badge_name"] if badge else None,
        "badge_icon": badge["badge_icon"] if badge else None,
        "next_tier_name": next_tier["badge_name"] if next_tier else None,
        "next_tier_icon": next_tier["badge_icon"] if next_tier else None,
        "next_tier_min": next_tier["min_referrals"] if next_tier else None,
        "next_tier_credits": next_tier["credits_reward"] if next_tier else None,
    })


# ==================== Referral Rewards - Redeem Credits ====================

@app.route("/api/referral/redeem", methods=["POST"])
def api_redeem_credits():
    """Redeem referral credits for a reward"""
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    user_id = session["user_id"]
    reward_type = request.json.get("reward_type", "")
    cost = int(request.json.get("cost", 0))

    conn = get_db_connection()
    user = conn.execute(
        "SELECT referral_credits FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if not user:
        conn.close()
        return jsonify({"error": "User not found"}), 404

    if user["referral_credits"] < cost:
        conn.close()
        return jsonify({"error": "Not enough credits"}), 400

    conn.execute(
        "UPDATE users SET referral_credits = referral_credits - ? WHERE id = ?",
        (cost, user_id)
    )
    conn.execute(
        "INSERT INTO reward_redemptions (user_id, reward_type, credits_spent, status) VALUES (?, ?, ?, 'completed')",
        (user_id, reward_type, cost)
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"Redeemed {reward_type} for {cost} credits!"})


# ==================== Referral Page ====================

@app.route("/referrer", methods=["GET", "POST"])
def referrer():
    if "user_id" not in session:
        return redirect(url_for("signin_local"))

    user_id = session["user_id"]
    role = session.get("role", "customer")
    conn = get_db_connection()

    # Get user data
    user = conn.execute(
        "SELECT id, username, referral_credits, referral_badge FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        relationship = request.form.get("relationship", "").strip()

        errors = []
        if not name:
            errors.append("Name is required.")
        if not email:
            errors.append("Email is required.")
        elif '@' not in email or '.' not in email.split('@')[-1]:
            errors.append("Please enter a valid email address.")

        if errors:
            for error in errors:
                flash(error, "error")
        else:
            existing = conn.execute(
                "SELECT id FROM referrals WHERE referrer_user_id = ? AND email = ?",
                (user_id, email)
            ).fetchone()

            if existing:
                flash(f"You have already referred {email}.", "warning")
            else:
                referred_user = conn.execute(
                    "SELECT id FROM users WHERE email = ?", (email,)
                ).fetchone()
                signed_up_user_id = referred_user["id"] if referred_user else None
                your_name = request.form.get("your_name", "").strip()
                if not your_name:
                    your_name = session.get("username", "A friend")

                conn.execute(
                    """INSERT INTO referrals (referrer_user_id, your_name, name, email, relationship, signed_up_user_id)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (user_id, your_name, name, email, relationship, signed_up_user_id)
                )
                conn.commit()

                # If the referred user already exists, immediately reward the referrer
                if signed_up_user_id and signed_up_user_id != user_id:
                    conn.execute(
                        "UPDATE users SET referral_credits = referral_credits + 1 WHERE id = ?",
                        (user_id,)
                    )
                    conn.execute(
                        "UPDATE referrals SET reward_given = TRUE WHERE referrer_user_id = ? AND email = ?",
                        (user_id, email)
                    )
                    conn.commit()
                    flash(f"{name} is already a member! You earned 1 credit! 🎉", "success")
                else:
                    # Send invitation email
                    try:
                        import tempfile, subprocess
                        app_url = request.host_url.rstrip('/')
                        signup_link = f"{app_url}/signup_local?ref={user_id}"
                        email_body = (
                            f"Hi {name},\n\n"
                            f"{your_name} has invited you to join Magic Bot AI - an intelligent automation platform "
                            f"that helps you create and manage AI-powered bots with ease.\n\n"
                            f"Whether you need to automate repetitive tasks, build intelligent chatbots, "
                            f"or streamline your workflow, Magic Bot AI makes it simple and powerful.\n\n"
                            f"Join {your_name} and start your journey today:\n"
                            f"{signup_link}\n\n"
                            f"We look forward to seeing what you'll create!\n\n"
                            f"Warmly,\n"
                            f"The Magic Bot AI Team"
                        )
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                            f.write(email_body)
                            temp_path = f.name
                        result = subprocess.run(
                            ["gog", "mail", "send",
                             "--to", email,
                             "--subject", f"{your_name} has invited you to join Magic Bot AI!",
                             "--body-file", temp_path,
                             "--account", "chingtshenbot@gmail.com"],
                            capture_output=True, text=True, timeout=30
                        )
                        os.unlink(temp_path)
                        if result.returncode == 0:
                            print(f"[REFERRAL] Invitation email sent to {email}")
                        else:
                            print(f"[REFERRAL] Failed to send email to {email}: {result.stderr}")
                    except Exception as e:
                        print(f"[REFERRAL] Email send error for {email}: {e}")

                    flash(f"{name} has been referred successfully! An invitation email has been sent.", "success")

    # Get referrals list
    if role == "admin":
        referrals = conn.execute("""
            SELECT r.*, u.username as referrer_username
            FROM referrals r
            JOIN users u ON r.referrer_user_id = u.id
            ORDER BY r.created_at DESC
        """).fetchall()
    else:
        referrals = conn.execute(
            """SELECT r.*,
                      (SELECT u2.username FROM users u2 WHERE u2.id = r.signed_up_user_id) as signed_up_username
               FROM referrals r
               WHERE r.referrer_user_id = ?
               ORDER BY r.created_at DESC""",
            (user_id,)
        ).fetchall()

    total_referred = len(referrals)
    pending_count = sum(1 for ref in referrals if ref["signed_up_user_id"] is None)
    signed_up_count = sum(1 for ref in referrals if ref["signed_up_user_id"] is not None)
    credits = user["referral_credits"] if user else 0

    # Get current badge tier
    current_tier = conn.execute(
        "SELECT * FROM reward_tiers WHERE min_referrals <= ? AND (max_referrals IS NULL OR max_referrals >= ?) ORDER BY min_referrals DESC LIMIT 1",
        (signed_up_count, signed_up_count)
    ).fetchone()

    # Get next tier
    next_tier = conn.execute(
        "SELECT * FROM reward_tiers WHERE min_referrals > ? ORDER BY min_referrals ASC LIMIT 1",
        (signed_up_count,)
    ).fetchone()

    # Get all tiers for display
    all_tiers = conn.execute(
        "SELECT * FROM reward_tiers ORDER BY min_referrals ASC"
    ).fetchall()

    # Calculate progress to next tier
    progress_pct = 100
    next_tier_name = None
    next_tier_icon = None
    if next_tier:
        current_min = current_tier["min_referrals"] if current_tier else 0
        next_min = next_tier["min_referrals"]
        range_size = next_min - current_min
        if range_size > 0:
            progress_pct = min(100, int((signed_up_count - current_min) / range_size * 100))
        next_tier_name = next_tier["badge_name"]
        next_tier_icon = next_tier["badge_icon"]

    # Get reward redemption history
    redemptions = conn.execute(
        "SELECT * FROM reward_redemptions WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
        (user_id,)
    ).fetchall()

    # Build referral link with ref parameter
    referral_link = f"{request.host_url.rstrip('/')}/signup_local?ref={user_id}"

    conn.close()

    return render_template("referrer.html",
                           referrals=referrals,
                           total_referred=total_referred,
                           pending_count=pending_count,
                           signed_up_count=signed_up_count,
                           credits=credits,
                           badge_name=current_tier["badge_name"] if current_tier else "Newcomer",
                           badge_icon=current_tier["badge_icon"] if current_tier else "🌱",
                           next_tier_name=next_tier_name,
                           next_tier_icon=next_tier_icon,
                           progress_pct=progress_pct,
                           all_tiers=all_tiers,
                           redemptions=redemptions,
                           referral_link=referral_link,
                           username=session.get("username"),
                           role=role)


# ==================== File Upload REST API ====================

import uuid


@app.route("/api/upload", methods=["POST"])
@login_required_api
def api_upload_files():
    """
    REST API: Upload files to a caller-specified folder.

    POST /api/upload
    Content-Type: multipart/form-data

    Form fields:
      - folder (required): Relative path (acts as S3 prefix on ECS, path on local)
      - files (required): One or more file attachments

    Returns:
      JSON with uploaded file details or error message.

    On ECS (production): files are uploaded to S3 bucket.
    Locally: files are saved to ~/folder_param.
    """
    folder_param = request.form.get("folder", "").strip()
    if not folder_param:
        return jsonify({"error": "Missing required field: 'folder'"}), 400

    if "files" not in request.files:
        return jsonify({"error": "Missing required field: 'files' (multipart file upload)"}), 400

    uploaded_files = request.files.getlist("files")
    if not uploaded_files or all(f.filename == "" for f in uploaded_files):
        return jsonify({"error": "No files provided or all filenames are empty."}), 400

    results = []
    errors = []

    for file_storage in uploaded_files:
        filename = file_storage.filename
        if not filename:
            continue

        safe_filename = Path(filename).name
        s3_key = f"{folder_param}/{safe_filename}" if folder_param else safe_filename

        try:
            if S3_ENABLED and s3_client:
                # Upload to S3
                file_bytes = file_storage.read()
                s3_client.put_object(
                    Bucket=S3_BUCKET,
                    Key=s3_key,
                    Body=file_bytes,
                    ContentType=file_storage.content_type or "application/octet-stream",
                )
                results.append({
                    "filename": safe_filename,
                    "size": len(file_bytes),
                    "s3_key": s3_key,
                    "s3_bucket": S3_BUCKET,
                    "folder": folder_param,
                    "storage": "s3",
                })
            else:
                # Local filesystem (dev mode)
                home_dir = Path.home().resolve()
                target = (home_dir / folder_param).resolve()
                try:
                    target.relative_to(home_dir)
                except ValueError:
                    errors.append({"filename": safe_filename, "error": "Path traversal is not allowed."})
                    continue
                target.mkdir(parents=True, exist_ok=True)
                dest_path = target / safe_filename
                file_storage.seek(0)
                file_storage.save(str(dest_path))
                results.append({
                    "filename": safe_filename,
                    "size": dest_path.stat().st_size,
                    "path": str(dest_path),
                    "folder": folder_param,
                    "storage": "local",
                })
        except Exception as e:
            errors.append({"filename": safe_filename, "error": str(e)})

    response = {
        "uploaded": results,
        "total_uploaded": len(results),
        "folder": folder_param,
    }
    if errors:
        response["errors"] = errors
        response["total_errors"] = len(errors)

    status_code = 200 if results else 400
    return jsonify(response), status_code


# ==================== Delete Referral ====================

@app.route("/referrer/delete/<int:ref_id>")
def delete_referral(ref_id):
    if "user_id" not in session:
        return redirect(url_for("signin_local"))

    user_id = session["user_id"]
    role = session.get("role", "customer")
    conn = get_db_connection()

    if role == "admin":
        ref = conn.execute("SELECT * FROM referrals WHERE id = ?", (ref_id,)).fetchone()
    else:
        ref = conn.execute("SELECT * FROM referrals WHERE id = ? AND referrer_user_id = ?", (ref_id, user_id)).fetchone()

    if not ref:
        conn.close()
        flash("Referral not found.", "error")
        return redirect(url_for("referrer"))

    conn.execute("DELETE FROM referrals WHERE id = ?", (ref_id,))
    conn.commit()
    conn.close()

    flash(f"Referral for {ref['name']} has been deleted.", "success")
    return redirect(url_for("referrer"))


# ==================== Run Application ====================


if __name__ == "__main__":
    print("=" * 60)
    print("Magic Bot AI - Complete Edition")
    print("=" * 60)
    print(f"Google OAuth: {'Enabled' if HAS_GOOGLE_OAUTH else 'Disabled'}")
    print(f"Telegram Bot API: Enabled (11 endpoints)")
    print(f"Group Collaboration: Enabled")
    print(f"Database: db.py (auto-detected SQLite or PostgreSQL)")
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