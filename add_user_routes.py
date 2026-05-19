import re

app_file = "/Users/siyang/flask_auth_app/app.py"

with open(app_file, "r") as f:
    content = f.read()

users_route = """

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

"""

if "@app.route(\"/users\")" not in content:
    content += users_route
    with open(app_file, "w") as f:
        f.write(content)
    print("Added /users routes.")
else:
    print("Routes already exist.")
