"""
SUPER SIMPLE version that DEFINITELY works
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from pathlib import Path
import os

# Setup
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = 'true'

app = Flask(__name__)
app.secret_key = "simple_key_12345"

DB_FILENAME = Path(__file__).parent / "users.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILENAME)
    conn.row_factory = sqlite3.Row
    return conn

# ==================== SIMPLE ROUTES ====================

@app.route("/")
def index():
    if "user_id" in session:
        return f"Welcome {session.get('username')}! <a href='/logout'>Logout</a>"
    return redirect(url_for("landing"))

@app.route("/landing")
def landing():
    """Simple landing page"""
    return render_template("landing.html")

@app.route("/signin_local", methods=["GET", "POST"])
def signin_local():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        if not username or not password:
            flash("Please enter both username and password.")
            return render_template("signin_local.html")
        
        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND provider = 'local'",
            (username,)
        ).fetchone()
        
        if not user or not check_password_hash(user["password_hash"], password):
            conn.close()
            flash("Invalid username or password.")
            return render_template("signin_local.html")
        
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        conn.close()
        return redirect(url_for("index"))
    
    return render_template("signin_local.html")

@app.route("/signup_local", methods=["GET", "POST"])
def signup_local():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        
        if not username or not email or not password:
            flash("Please fill in all fields.")
            return render_template("signup_local.html")
        
        if len(password) < 8:
            flash("Password must be at least 8 characters.")
            return render_template("signup_local.html")
        
        conn = get_db_connection()
        
        # Check if username exists
        if conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone():
            conn.close()
            flash("Username already exists.")
            return render_template("signup_local.html")
        
        # Create user
        password_hash = generate_password_hash(password)
        try:
            conn.execute(
                "INSERT INTO users (provider, username, email, password_hash) VALUES (?, ?, ?, ?)",
                ("local", username, email, password_hash)
            )
            conn.commit()
            
            user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            conn.close()
            
            flash("Account created!")
            return redirect(url_for("index"))
        except:
            conn.close()
            flash("Error creating account.")
            return render_template("signup_local.html")
    
    return render_template("signup_local.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))

# ==================== RUN ====================

if __name__ == "__main__":
    print("=" * 60)
    print("SIMPLE Flask App - Definitely Works")
    print("=" * 60)
    print("Starting on http://localhost:5000")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)