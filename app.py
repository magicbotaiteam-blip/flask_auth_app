from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from pathlib import Path
import os
import re
from flask_dance.contrib.google import make_google_blueprint, google

# Allow insecure transport for development (HTTP on localhost)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = 'true'

app = Flask(__name__)
app.secret_key = "6ce26db79ba4b1ae2613a1dc4fa4177a75847d40f32347ac9388377a5a7b587b"

# OAuth setup for Google
google_bp = make_google_blueprint(
    client_id=os.environ.get("GOOGLE_CLIENT_ID", "your-google-client-id"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", "your-google-client-secret"),
    scope=[
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/userinfo.email",
        "openid"
    ],
    redirect_to="index"  # Redirect to index route after successful auth
)
app.register_blueprint(google_bp, url_prefix="/login")

DB_FILENAME = Path(__file__).parent / "users.db"


def get_db_connection():
    conn = sqlite3.connect(DB_FILENAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    
    # Create users table if it doesn't exist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL DEFAULT 'local',
            provider_id TEXT UNIQUE,
            username TEXT NOT NULL UNIQUE,
            email TEXT,  -- No UNIQUE constraint (allows duplicate emails)
            password_hash TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create roles and user_roles tables
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
    
    # Insert default roles
    conn.execute("INSERT OR IGNORE INTO roles (name) VALUES ('admin')")
    conn.execute("INSERT OR IGNORE INTO roles (name) VALUES ('customer')")
    
    # Create bots table if it doesn't exist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            email TEXT,
            organization TEXT,
            messaging TEXT,
            llm TEXT,
            token TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()


init_db()


@app.route("/landing")
def landing():
    return render_template("landing.html", google=google)











@app.route("/register-bot")
@app.route("/register-bot/<int:bot_id>")
def register_bot(bot_id=None):
    if "user_id" not in session:
        return redirect(url_for("signin"))
    
    bot = None
    role = session.get("role", "customer")
    if bot_id:
        user_id = session["user_id"]
        conn = get_db_connection()
        if role == "admin":
            bot = conn.execute("SELECT * FROM bots WHERE id = ?", (bot_id,)).fetchone()
        else:
            bot = conn.execute("SELECT * FROM bots WHERE id = ? AND user_id = ?", (bot_id, user_id)).fetchone()
        conn.close()
    
    return render_template("register_bot.html", bot=bot, username=session.get("username"), role=role)


@app.route("/logout")
def logout():
    # If user was authenticated via Google, revoke the token
    if "provider" in session and session["provider"] == "google" and google.authorized:
        try:
            token = google.token["access_token"]
            google.post(
                "https://accounts.google.com/o/oauth2/revoke",
                params={"token": token},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
        except:
            pass  # Ignore errors when revoking token
    
    # Clear the session
    session.clear()
    return redirect(url_for("landing"))


# Bot management routes
@app.route("/my-bots")
def my_bots():
    if "user_id" not in session:
        return redirect(url_for("signin"))
    
    user_id = session["user_id"]
    role = session.get("role", "customer")
    conn = get_db_connection()
    if role == "admin":
        bots = conn.execute("SELECT * FROM bots ORDER BY created_at DESC").fetchall()
    else:
        bots = conn.execute("SELECT * FROM bots WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    conn.close()
    
    return render_template("my_bots.html", bots=bots, username=session.get("username"), role=role)





@app.route("/check-bot-name")
def check_bot_name():
    if "user_id" not in session:
        return {"exists": False}
    
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
def save_bot():
    if "user_id" not in session:
        return redirect(url_for("signin"))
    
    user_id = session["user_id"]
    bot_id = request.form.get("bot_id")
    name = request.form.get("name")
    email = request.form.get("email")
    organization = request.form.get("organization")
    messaging = request.form.get("messaging")
    llm = request.form.get("llm")
    token = request.form.get("token")
    description = request.form.get("description")
    
    if not name:
        flash("Bot Name is required.")
        return redirect(url_for("register_bot"))
    
    # Append _magicAIbot suffix if not already present
    SUFFIX = '_magicAIbot'
    if not name.endswith(SUFFIX):
        name = name.strip() + SUFFIX
    
    if not messaging:
        flash("Messaging Platform is required.")
        return redirect(url_for("register_bot"))
    
    conn = get_db_connection()
    role = session.get("role", "customer")
    
    # Check for duplicate bot name (exclude current bot if editing)
    if bot_id:
        dup = conn.execute("SELECT id FROM bots WHERE name = ? AND id != ?", (name, int(bot_id))).fetchone()
    else:
        dup = conn.execute("SELECT id FROM bots WHERE name = ?", (name,)).fetchone()
    
    if dup:
        flash(f'A bot named "{name}" already exists. Please choose a different name.', "error")
        conn.close()
        return redirect(url_for("register_bot", bot_id=bot_id) if bot_id else url_for("register_bot"))
    
    if bot_id:  # Update existing bot
        if role == "admin":
            conn.execute("""
                UPDATE bots 
                SET name = ?, email = ?, organization = ?, messaging = ?, llm = ?, token = ?, description = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (name, email, organization, messaging, llm, token, description, bot_id))
        else:
            conn.execute("""
                UPDATE bots 
                SET name = ?, email = ?, organization = ?, messaging = ?, llm = ?, token = ?, description = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
            """, (name, email, organization, messaging, llm, token, description, bot_id, user_id))
        flash("Bot updated successfully!")
    else:  # Create new bot
        conn.execute("""
            INSERT INTO bots (user_id, name, email, organization, messaging, llm, token, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, name, email, organization, messaging, llm, token, description))
        flash("Bot created successfully!")
    
    conn.commit()
    conn.close()
    
    return redirect(url_for("my_bots"))


@app.route("/bot/delete/<int:bot_id>")
def delete_bot(bot_id):
    if "user_id" not in session:
        return redirect(url_for("signin_local"))
    
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


# Profile management route
@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        return redirect(url_for("signin"))
        
    user_id = session["user_id"]
    conn = get_db_connection()
    
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        # Updating the profile (only email for now since username is unique and tied to auth logic)
        try:
            conn.execute("UPDATE users SET email = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (email, user_id))
            conn.commit()
            flash("Profile updated successfully!", "success")
        except Exception as e:
            flash(f"Error updating profile: {str(e)}", "error")
            
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    role_row = conn.execute("""
        SELECT r.name FROM roles r
        JOIN user_roles ur ON r.id = ur.role_id
        WHERE ur.user_id = ?
    """, (user_id,)).fetchone()
    
    role = role_row["name"] if role_row else "customer"
    conn.close()
    
    return render_template("profile.html", user=user, role=role, username=session.get("username"))

# Local authentication routes
@app.route("/signup-local", methods=["GET", "POST"])
def signup_local():
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
        
        # Check if username already exists (email can be duplicate now)
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
            
            # Assign 'customer' role
            customer_role = conn.execute("SELECT id FROM roles WHERE name = 'customer'").fetchone()
            conn.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (user["id"], customer_role["id"]))
            conn.commit()
            
            conn.close()
            
            # Set session
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["provider"] = "local"
            session["role"] = "customer"
            
            flash("Account created successfully! Welcome to Magic Bot AI.", "success")
            return redirect(url_for("index"))
            
        except Exception as e:
            conn.close()
            flash(f"An error occurred: {str(e)}", "error")
            return render_template("signup_local.html")
    
    return render_template("signup_local.html")


@app.route("/signin-local", methods=["GET", "POST"])
def signin_local():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "on"
        
        if not username or not password:
            flash("Please enter both username/email and password.", "error")
            return render_template("signin_local.html")
        
        conn = get_db_connection()
        
        # Try to find user by username first (exact match)
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND provider = 'local'",
            (username,)
        ).fetchone()
        
        # If not found by username, try email (but warn about potential duplicates)
        if not user:
            user = conn.execute(
                "SELECT * FROM users WHERE email = ? AND provider = 'local'",
                (username,)
            ).fetchone()
            
            # If multiple users have same email, we need to handle this
            if user:
                # Check if there are multiple users with this email
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
            
        # Get role
        role_row = conn.execute("""
            SELECT r.name FROM roles r
            JOIN user_roles ur ON r.id = ur.role_id
            WHERE ur.user_id = ?
        """, (user["id"],)).fetchone()
        
        session["role"] = role_row["name"] if role_row else "customer"
        
        conn.close()
        
        # Set session
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["provider"] = "local"
        
        # Set session permanence based on "remember me"
        if remember:
            session.permanent = True
        else:
            session.permanent = False
        
        flash(f"Welcome back, {user['username']}!", "success")
        return redirect(url_for("index"))
    
    return render_template("signin_local.html")


@app.route("/signin")
def signin():
    # Redirect to local signin page (main entry point)
    return redirect(url_for("signin_local"))


@app.route("/signup")
def signup():
    # Redirect to local signup page
    return redirect(url_for("signup_local"))


# Update the main route to handle both Google and local auth
@app.route("/")
def index():
    # Check if user is authenticated via Google
    if google.authorized:
        try:
            resp = google.get("/oauth2/v2/userinfo")
            if resp.status_code != 200:
                flash(f"Failed to fetch user info: {resp.status_code}")
                return redirect(url_for("signin_local"))
            user_info = resp.json()
        except Exception as e:
            flash(f"Error fetching user info: {str(e)}")
            return redirect(url_for("signin_local"))

        # Store or get user
        conn = get_db_connection()
        
        # First, check if user already exists by Google ID
        user = conn.execute(
            "SELECT * FROM users WHERE provider = ? AND provider_id = ?", 
            ("google", user_info["id"])
        ).fetchone()
        
        if user:
            # User already exists, use existing record
            conn.close()
        else:
            # New Google user - need to create with unique username
            base_username = user_info["name"].replace(" ", "_").lower()[:30]
            username = base_username
            counter = 1
            
            # Generate unique username
            while True:
                existing = conn.execute(
                    "SELECT * FROM users WHERE username = ?", 
                    (username,)
                ).fetchone()
                
                if not existing:
                    break  # Username is available
                
                # Try with number suffix
                username = f"{base_username}_{counter}"
                counter += 1
                
                if counter > 100:  # Safety limit
                    conn.close()
                    flash("Could not create unique username. Please try again.", "error")
                    return redirect(url_for("signin_local"))
            
            try:
                # Create new Google user with unique username
                conn.execute(
                    "INSERT INTO users (provider, provider_id, username, email) VALUES (?, ?, ?, ?)", 
                    ("google", user_info["id"], username, user_info.get("email"))
                )
                
                # Get the newly created user
                user = conn.execute(
                    "SELECT * FROM users WHERE provider = ? AND provider_id = ?", 
                    ("google", user_info["id"])
                ).fetchone()
                
                # Assign customer role
                customer_role = conn.execute("SELECT id FROM roles WHERE name = 'customer'").fetchone()
                conn.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (user["id"], customer_role["id"]))
                conn.commit()
                
                conn.close()
                
            except sqlite3.IntegrityError as e:
                conn.close()
                # This shouldn't happen with our unique username generation, but just in case
                flash(f"User creation failed: {str(e)}. Please try a different Google account or contact support.", "error")
                return redirect(url_for("signin_local"))
            except Exception as e:
                conn.close()
                flash(f"Database error: {str(e)}", "error")
                return redirect(url_for("signin_local"))

        # Get role
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
    
    # Check if user is authenticated via session (both Google and local)
    if "user_id" not in session:
        return redirect(url_for("landing"))
    
    role = session.get("role", "customer")
    return render_template("home.html", username=session.get("username"), google=google, role=role)



@app.route("/users")
def find_users():
    if "user_id" not in session:
        return redirect(url_for("signin"))
    
    role = session.get("role", "customer")
    if role != "admin":
        flash("You do not have permission to view this page.", "error")
        return redirect(url_for("home"))
        
    conn = get_db_connection()
    users = conn.execute("SELECT id, provider, username, email, created_at, updated_at FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    
    return render_template("users.html", users=users, username=session.get("username"), role=role)

@app.route("/users/<int:view_user_id>")
def user_detail(view_user_id):
    if "user_id" not in session:
        return redirect(url_for("signin"))
    
    role = session.get("role", "customer")
    if role != "admin":
        flash("You do not have permission to view this page.", "error")
        return redirect(url_for("home"))
        
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (view_user_id,)).fetchone()
    conn.close()
    
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("find_users"))
        
    return render_template("user_detail.html", user=user, session_username=session.get("username"), role=role)

if __name__ == "__main__":
    app.run(debug=True, port=5000)

