"""
Magic Bot AI - Complete Final Application
This includes ALL routes from original app.py + ALL enhanced features
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from pathlib import Path
import os
import re
import json
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

# Import our enhanced modules
try:
    from bot_services import BotServiceFactory, test_bot_connection, send_bot_message
    from analytics import get_analytics, log_bot_event
    HAS_ENHANCEMENTS = True
except ImportError:
    HAS_ENHANCEMENTS = False
    print("Note: Enhanced modules not available, running in basic mode")

# Flask extensions
try:
    from flask_dance.contrib.google import make_google_blueprint, google
    HAS_GOOGLE_OAUTH = True
except ImportError:
    HAS_GOOGLE_OAUTH = False
    print("Note: Flask-Dance not available, Google OAuth disabled")

# Setup
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = 'true'

# Load environment variables
load_dotenv(dotenv_path=Path('/Users/siyang/flask_cronjobs/.env'), override=True)

app = Flask(__name__)
app.secret_key = "6ce26db79ba4b1ae2613a1dc4fa4177a75847d40f32347ac9388377a5a7b587b"

# OAuth setup for Google (if available)
if HAS_GOOGLE_OAUTH:
    google_bp = make_google_blueprint(
        client_id=os.environ.get("GOOGLE_CLIENT_ID", "your-google-client-id"),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", "your-google-client-secret"),
        scope=[
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email",
            "openid"
        ],
        redirect_to="index"
    )
    app.register_blueprint(google_bp, url_prefix="/login")

DB_FILENAME = Path(__file__).parent / "users.db"

# ==================== Database Functions ====================

def get_db_connection():
    conn = sqlite3.connect(DB_FILENAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db_safe():
    """Initialize database safely, skipping errors"""
    conn = get_db_connection()
    
    # Basic tables (always create)
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
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()

init_db_safe()

# ==================== Authentication Decorator ====================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("landing"))
        return f(*args, **kwargs)
    return decorated_function

# ==================== ALL ROUTES (Original + Enhanced) ====================

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
                conn.commit()
                user = conn.execute(
                    "SELECT * FROM users WHERE provider = ? AND provider_id = ?", 
                    ("google", user_info["id"])
                ).fetchone()
                conn.close()
            except Exception as e:
                conn.close()
                flash(f"Database error: {str(e)}", "error")
                return redirect(url_for("landing"))

        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["provider"] = "google"
    
    if "user_id" not in session:
        return redirect(url_for("landing"))
    
    return render_template("home.html", 
                         username=session.get("username"), 
                         google=HAS_GOOGLE_OAUTH,
                         has_enhancements=HAS_ENHANCEMENTS)

@app.route("/landing")
def landing():
    """Public landing page"""
    return render_template("landing.html", google=HAS_GOOGLE_OAUTH)

@app.route("/signin")
def signin():
    """Signin page (redirects to appropriate signin method)"""
    return redirect(url_for("signin_local"))

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
        
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["provider"] = "local"
        conn.close()
        
        return redirect(url_for("index"))
    
    return render_template("signin_local.html", google=HAS_GOOGLE_OAUTH)

@app.route("/signup")
def signup():
    """Signup page (redirects to appropriate signup method)"""
    return redirect(url_for("signup_local"))

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
            
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["provider"] = "local"
            conn.close()
            
            flash("Account created successfully! Welcome to Magic Bot AI.", "success")
            return redirect(url_for("index"))
            
        except Exception as e:
            conn.close()
            flash(f"Error creating account: {str(e)}", "error")
            return render_template("signup_local.html", google=HAS_GOOGLE_OAUTH)
    
    return render_template("signup_local.html", google=HAS_GOOGLE_OAUTH)

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

# ==================== Enhanced Bots Management ====================

@app.route("/my-bots")
@login_required
def my_bots():
    """List user's bots"""
    user_id = session["user_id"]
    conn = get_db_connection()
    
    # Get user's bots
    bots = conn.execute("""
        SELECT b.* FROM bots b
        WHERE b.user_id = ? 
        ORDER BY b.created_at DESC
    """, (user_id,)).fetchall()
    
    conn.close()
    
    return render_template("my_bots.html", 
                         bots=bots, 
                         username=session.get("username"),
                         has_enhancements=HAS_ENHANCEMENTS)

@app.route("/register-bot")
@app.route("/register-bot/<int:bot_id>")
@login_required
def register_bot(bot_id=None):
    """Register or edit a bot"""
    bot = None
    if bot_id:
        user_id = session["user_id"]
        conn = get_db_connection()
        bot = conn.execute("SELECT * FROM bots WHERE id = ? AND user_id = ?", (bot_id, user_id)).fetchone()
        conn.close()
    
    return render_template("register_bot.html", 
                         bot=bot, 
                         username=session.get("username"),
                         has_enhancements=HAS_ENHANCEMENTS)

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
        'tags': request.form.get("tags", "")
    }
    
    if not all([form_data['name'], form_data['token']]):
        flash("Name and Token are required fields.")
        return redirect(url_for("register_bot"))
    
    # Prepare config JSON if enhancements available
    if HAS_ENHANCEMENTS:
        config = {
            "messaging_platform": form_data['messaging'],
            "llm_provider": form_data['llm'],
            "webhook_enabled": bool(form_data['webhook_url']),
            "tags": [tag.strip() for tag in form_data['tags'].split(',') if tag.strip()],
            "features": {},
            "created_at": datetime.now().isoformat()
        }
        config_json = json.dumps(config)
    else:
        config_json = "{}"
    
    conn = get_db_connection()
    
    if bot_id:  # Update existing bot
        conn.execute("""
            UPDATE bots 
            SET name = ?, email = ?, organization = ?, messaging = ?, llm = ?, token = ?, 
                description = ?, webhook_url = ?, api_key = ?, config = ?, tags = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
        """, (form_data['name'], form_data['email'], form_data['organization'], form_data['messaging'], 
              form_data['llm'], form_data['token'], form_data['description'], form_data['webhook_url'], 
              form_data['api_key'], config_json, form_data['tags'], bot_id, user_id))
        flash("Bot updated successfully!")
    else:  # Create new bot
        conn.execute("""
            INSERT INTO bots (user_id, name, email, organization, messaging, llm, token, 
                             description, webhook_url, api_key, config, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, form_data['name'], form_data['email'], form_data['organization'], 
              form_data['messaging'], form_data['llm'], form_data['token'], form_data['description'], 
              form_data['webhook_url'], form_data['api_key'], config_json, form_data['tags']))
        flash("Bot created successfully!")
    
    conn.commit()
    conn.close()
    
    return redirect(url_for("my_bots"))

@app.route("/bot/delete/<int:bot_id>")
@login_required
def delete_bot(bot_id):
    """Delete a bot"""
    user_id = session["user_id"]
    conn = get_db_connection()
    conn.execute("DELETE FROM bots WHERE id = ? AND user_id = ?", (bot_id, user_id))
    conn.commit()
    conn.close()
    
    flash("Bot deleted successfully!")
    return redirect(url_for("my_bots"))

# ==================== Enhanced API Endpoints ====================

@app.route("/api/bot/<int:bot_id>/test")
@login_required
def test_bot_api(bot_id):
    """Test bot API connection"""
    if not HAS_ENHANCEMENTS:
        return jsonify({"error": "Enhanced features not available"}), 501
    
    user_id = session["user_id"]
    conn = get_db_connection()
    
    # Check access
    bot = conn.execute("""
        SELECT * FROM bots WHERE id = ? AND user_id = ?
    """, (bot_id, user_id)).fetchone()
    
    if not bot:
        conn.close()
        return jsonify({"error": "Bot not found"}), 404
    
    # Test connection
    result = test_bot_connection(bot['messaging'], bot['token'])
    
    conn.close()
    return jsonify(result)

# ==================== Run Application ====================

if __name__ == "__main__":
    print("=" * 60)
    print("Magic Bot AI - Complete Final Application")
    print("=" * 60)
    print(f"Google OAuth: {'Enabled' if HAS_GOOGLE_OAUTH else 'Disabled'}")
    print(f"Enhanced Features: {'Enabled' if HAS_ENHANCEMENTS else 'Disabled'}")
    print(f"Database: {DB_FILENAME}")
    print("=" * 60)
    print("Starting server on http://localhost:5000")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)