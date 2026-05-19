#!/usr/bin/env python3
"""
Clean, working authentication system.
Fixed all common issues.
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from pathlib import Path
import os
import re

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")

# Database setup
DB_FILENAME = Path(__file__).parent / "users.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILENAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database with correct schema."""
    conn = get_db_connection()
    
    # Create users table WITHOUT UNIQUE constraint on email
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
    
    # Create bots table
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
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()

# Initialize database
init_db()

# ==================== SIMPLE GOOGLE OAUTH SETUP ====================
# We'll implement a simpler Google OAuth that doesn't require Flask-Dance
# This avoids the complex configuration issues

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = "http://localhost:5000/google-callback"

# ==================== ROUTES ====================

@app.route("/")
def index():
    """Main dashboard - requires authentication."""
    # Check if user is authenticated via session
    if "user_id" not in session:
        return redirect(url_for("landing"))
    
    return render_template("home.html", username=session.get("username"))

@app.route("/landing")
def landing():
    """Public landing page."""
    # Simple landing page without Google OAuth complexity
    return render_template("landing_simple.html")

# ==================== LOCAL AUTHENTICATION ====================

@app.route("/signup-local", methods=["GET", "POST"])
def signup_local():
    """Local account registration."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        
        # Validation
        errors = []
        
        # Username validation
        if not username:
            errors.append("Username is required.")
        elif len(username) < 3 or len(username) > 50:
            errors.append("Username must be between 3 and 50 characters.")
        elif not re.match(r'^[a-zA-Z0-9_]+$', username):
            errors.append("Username can only contain letters, numbers, and underscores.")
        
        # Email validation
        if not email:
            errors.append("Email is required.")
        elif not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            errors.append("Please enter a valid email address.")
        
        # Password validation
        if not password:
            errors.append("Password is required.")
        elif len(password) < 8:
            errors.append("Password must be at least 8 characters long.")
        elif not re.search(r'[A-Za-z]', password) or not re.search(r'[0-9]', password):
            errors.append("Password must contain at least one letter and one number.")
        
        # Password confirmation
        if password != confirm_password:
            errors.append("Passwords do not match.")
        
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("signup_local.html")
        
        # Check if username already exists
        conn = get_db_connection()
        existing_user = conn.execute(
            "SELECT * FROM users WHERE username = ?", 
            (username,)
        ).fetchone()
        
        if existing_user:
            conn.close()
            flash("Username already exists. Please choose a different username.", "error")
            return render_template("signup_local.html")
        
        # Create new user
        password_hash = generate_password_hash(password)
        try:
            conn.execute(
                "INSERT INTO users (provider, username, email, password_hash) VALUES (?, ?, ?, ?)",
                ("local", username, email, password_hash)
            )
            conn.commit()
            
            # Get the new user
            user = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            conn.close()
            
            # Set session
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["provider"] = "local"
            
            flash("Account created successfully! Welcome to Magic Bot AI.", "success")
            return redirect(url_for("index"))
            
        except Exception as e:
            conn.close()
            flash(f"An error occurred: {str(e)}", "error")
            return render_template("signup_local.html")
    
    return render_template("signup_local.html")

@app.route("/signin-local", methods=["GET", "POST"])
def signin_local():
    """Local account authentication."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "on"
        
        if not username or not password:
            flash("Please enter both username/email and password.", "error")
            return render_template("signin_local.html")
        
        conn = get_db_connection()
        
        # Try to find user by username first
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND provider = 'local'",
            (username,)
        ).fetchone()
        
        # If not found by username, try email
        if not user:
            user = conn.execute(
                "SELECT * FROM users WHERE email = ? AND provider = 'local'",
                (username,)
            ).fetchone()
            
            # If multiple users have same email, require username
            if user:
                duplicate_check = conn.execute(
                    "SELECT COUNT(*) as count FROM users WHERE email = ? AND provider = 'local'",
                    (username,)
                ).fetchone()
                
                if duplicate_check['count'] > 1:
                    conn.close()
                    flash("Multiple accounts found with this email. Please use your username to sign in.", "error")
                    return render_template("signin_local.html")
        
        if not user:
            conn.close()
            flash("Invalid username/email or password.", "error")
            return render_template("signin_local.html")
        
        # Check password
        if not check_password_hash(user["password_hash"], password):
            conn.close()
            flash("Invalid username/email or password.", "error")
            return render_template("signin_local.html")
        
        conn.close()
        
        # Set session
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["provider"] = "local"
        
        # Set session permanence
        session.permanent = remember
        
        flash(f"Welcome back, {user['username']}!", "success")
        return redirect(url_for("index"))
    
    return render_template("signin_local.html")

@app.route("/signin")
def signin():
    """Redirect to local signin."""
    return redirect(url_for("signin_local"))

@app.route("/signup")
def signup():
    """Redirect to local signup."""
    return redirect(url_for("signup_local"))

# ==================== LOGOUT ====================

@app.route("/logout")
def logout():
    """Logout user."""
    # Clear session
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("landing"))

# ==================== BOT MANAGEMENT ====================

@app.route("/my-bots")
def my_bots():
    """List user's bots."""
    if "user_id" not in session:
        return redirect(url_for("signin_local"))
    
    user_id = session["user_id"]
    conn = get_db_connection()
    bots = conn.execute(
        "SELECT * FROM bots WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    
    return render_template("my_bots.html", bots=bots, username=session.get("username"))

@app.route("/register-bot")
@app.route("/register-bot/<int:bot_id>")
def register_bot(bot_id=None):
    """Register or edit a bot."""
    if "user_id" not in session:
        return redirect(url_for("signin_local"))
    
    bot = None
    if bot_id:
        user_id = session["user_id"]
        conn = get_db_connection()
        bot = conn.execute(
            "SELECT * FROM bots WHERE id = ? AND user_id = ?",
            (bot_id, user_id)
        ).fetchone()
        conn.close()
    
    return render_template("register_bot.html", bot=bot, username=session.get("username"))

@app.route("/bot/save", methods=["POST"])
def save_bot():
    """Save bot data."""
    if "user_id" not in session:
        return redirect(url_for("signin_local"))
    
    user_id = session["user_id"]
    bot_id = request.form.get("bot_id")
    name = request.form.get("name")
    email = request.form.get("email")
    organization = request.form.get("organization")
    messaging = request.form.get("messaging")
    token = request.form.get("token")
    
    if not all([name, token]):
        flash("Name and Token are required fields.", "error")
        return redirect(url_for("register_bot"))
    
    conn = get_db_connection()
    
    if bot_id:  # Update existing bot
        conn.execute("""
            UPDATE bots 
            SET name = ?, email = ?, organization = ?, messaging = ?, token = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
        """, (name, email, organization, messaging, token, bot_id, user_id))
        flash("Bot updated successfully!", "success")
    else:  # Create new bot
        conn.execute("""
            INSERT INTO bots (user_id, name, email, organization, messaging, token)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, name, email, organization, messaging, token))
        flash("Bot created successfully!", "success")
    
    conn.commit()
    conn.close()
    
    return redirect(url_for("my_bots"))

@app.route("/bot/delete/<int:bot_id>")
def delete_bot(bot_id):
    """Delete a bot."""
    if "user_id" not in session:
        return redirect(url_for("signin_local"))
    
    user_id = session["user_id"]
    conn = get_db_connection()
    conn.execute("DELETE FROM bots WHERE id = ? AND user_id = ?", (bot_id, user_id))
    conn.commit()
    conn.close()
    
    flash("Bot deleted successfully!", "success")
    return redirect(url_for("my_bots"))

# ==================== SIMPLE GOOGLE OAUTH ====================

@app.route("/google-login")
def google_login():
    """Simple Google OAuth login page."""
    if not GOOGLE_CLIENT_ID:
        flash("Google OAuth is not configured. Please contact the administrator.", "error")
        return redirect(url_for("signin_local"))
    
    # In a real implementation, this would redirect to Google's OAuth page
    # For now, we'll show a simple message
    return """
    <html>
    <head><title>Google OAuth</title></head>
    <body style="font-family: Arial, sans-serif; padding: 40px;">
        <h1>Google OAuth Login</h1>
        <p>Google OAuth requires proper configuration:</p>
        <ol>
            <li>Set GOOGLE_CLIENT_ID environment variable</li>
            <li>Set GOOGLE_CLIENT_SECRET environment variable</li>
            <li>Configure Google Cloud Console with redirect URI: {}</li>
        </ol>
        <p>For now, please use <a href="/signin-local">local authentication</a>.</p>
        <p><a href="/">Back to home</a></p>
    </body>
    </html>
    """.format(GOOGLE_REDIRECT_URI)

# ==================== MAIN ====================

if __name__ == "__main__":
    # For development, allow HTTP
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = 'true'
    
    print("=" * 60)
    print("Magic Bot AI - Clean Authentication System")
    print("=" * 60)
    print("Starting on: http://localhost:5000")
    print("=" * 60)
    print("\nFeatures:")
    print("✅ Local authentication (username/password)")
    print("✅ No UNIQUE constraint on email")
    print("✅ Session management")
    print("✅ Bot management")
    print("⚠️  Google OAuth: Requires configuration")
    print("=" * 60)
    
    app.run(debug=True, port=5000)