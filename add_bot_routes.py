import os

app_file = "/Users/siyang/flask_auth_app/app_complete_with_groups.py"
with open(app_file, "r") as f:
    content = f.read()

new_routes = """
@app.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required_route
def user_edit(user_id):
    conn = get_db_connection()
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        provider = request.form.get("provider", "local")
        
        try:
            conn.execute("UPDATE users SET username = ?, email = ?, provider = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                         (username, email, provider, user_id))
            conn.commit()
            flash("User updated successfully.", "success")
            return redirect(f"/users/{user_id}")
        except Exception as e:
            flash(f"Error updating user: {str(e)}", "error")
    
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('users_list'))
        
    return render_template("user_form.html", user=user, session_username=session.get("username"), role=session.get("role"))

@app.route("/users/add", methods=["GET", "POST"])
@login_required
@admin_required_route
def user_add():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        provider = request.form.get("provider", "local")
        
        from werkzeug.security import generate_password_hash
        password_hash = generate_password_hash(password) if password else None
        
        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO users (username, email, password_hash, provider) VALUES (?, ?, ?, ?)", 
                         (username, email, password_hash, provider))
            conn.commit()
            
            user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if user:
                customer_role = conn.execute("SELECT id FROM roles WHERE name = 'customer'").fetchone()
                if customer_role:
                    conn.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (user["id"], customer_role["id"]))
                    conn.commit()
            
            flash("User created successfully.", "success")
            return redirect(url_for('users_list'))
        except Exception as e:
            flash(f"Error creating user: {str(e)}", "error")
        finally:
            conn.close()
            
    return render_template("user_form.html", user=None, session_username=session.get("username"), role=session.get("role"))

@app.route("/users/<int:user_id>/delete", methods=["GET", "POST"])
@login_required
@admin_required_route
def user_delete(user_id):
    if user_id == session.get("user_id"):
        flash("You cannot delete your own account.", "error")
        return redirect(f"/users/{user_id}")
        
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        flash("User deleted successfully.", "success")
    except Exception as e:
        flash(f"Error deleting user: {str(e)}", "error")
    finally:
        conn.close()
        
    return redirect(url_for('users_list'))

@app.route("/users/<int:user_id>/bots")
@login_required
@admin_required_route
def user_bots(user_id):
    conn = get_db_connection()
    target_user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    
    if not target_user:
        conn.close()
        flash("User not found.", "error")
        return redirect(url_for('users_list'))
        
    bots = conn.execute("SELECT * FROM bots WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    conn.close()
    
    return render_template("user_bots.html", target_user=target_user, bots=bots, session_username=session.get("username"), role=session.get("role"))

@app.route("/bots/<int:bot_id>")
@login_required
def view_bot_detail(bot_id):
    conn = get_db_connection()
    
    # Standard users can only view their own bots, admins can view any bot
    role = session.get("role", "customer")
    if role == "admin":
        bot = conn.execute("SELECT * FROM bots WHERE id = ?", (bot_id,)).fetchone()
    else:
        bot = conn.execute("SELECT * FROM bots WHERE id = ? AND user_id = ?", (bot_id, session.get("user_id"))).fetchone()
        
    conn.close()
    
    if not bot:
        flash("Bot not found or access denied.", "error")
        return redirect("/")
        
    return render_template("bot_detail.html", bot=bot, session_username=session.get("username"), role=role)
"""

if "@app.route(\"/users/<int:user_id>/bots\")" not in content:
    content = content.replace("if __name__ == '__main__':", new_routes + "\nif __name__ == '__main__':")
    # also check if __name__ == "__main__":
    content = content.replace('if __name__ == "__main__":', new_routes + '\nif __name__ == "__main__":')
    with open(app_file, "w") as f:
        f.write(content)

