import os

app_path = "/Users/siyang/flask_auth_app/app_complete_with_groups.py"
home_template_path = "/Users/siyang/flask_auth_app/templates/home_with_groups.html"

# 1. Update app_complete_with_groups.py
with open(app_path, "r") as f:
    content = f.read()

injection = """
# ==================== User Management (Admin Only) ====================

def admin_required_route(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role', 'customer') != 'admin':
            flash("Admin privileges required to access user management.", "error")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/users")
@login_required
@admin_required_route
def users_list():
    conn = get_db_connection()
    users = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template("users_list.html", users=users, username=session.get("username"), role=session.get("role"))

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
        password = request.form.get("password", "")
        role_name = request.form.get("role", "customer")
        
        if not username or not password:
            flash("Username and password are required", "error")
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
        password = request.form.get("password", "")
        
        try:
            if password:
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

# ==================== Run Application ====================
"""

if "# ==================== User Management (Admin Only) ====================" not in content:
    content = content.replace("# ==================== Run Application ====================", injection)
    with open(app_path, "w") as f:
        f.write(content)
        print("Injected user routes.")

# 2. Update home_with_groups.html
with open(home_template_path, "r") as f:
    home_content = f.read()

find_users_html = """
                            {% if role == 'admin' %}
                            <a href="/users" class="btn btn-secondary quick-action-btn">
                                <i class="bi bi-search"></i> Find Users
                            </a>
                            {% endif %}
"""

if "Find Users" not in home_content:
    search_str = """                            <a href="/my-bots" class="btn btn-warning quick-action-btn">
                                <i class="bi bi-robot"></i> Manage Bots
                            </a>"""
    replace_str = search_str + find_users_html
    home_content = home_content.replace(search_str, replace_str)
    with open(home_template_path, "w") as f:
        f.write(home_content)
        print("Added Find Users button to home.")
