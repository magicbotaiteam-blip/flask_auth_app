import sqlite3
from pathlib import Path

DB_FILENAME = Path("/Users/siyang/flask_auth_app/users.db")

def migrate_db():
    conn = sqlite3.connect(DB_FILENAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Create roles and user_roles tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, role_id),
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (role_id) REFERENCES roles (id) ON DELETE CASCADE
        )
    """)
    
    # 2. Insert default roles
    cursor.execute("INSERT OR IGNORE INTO roles (name) VALUES ('admin')")
    cursor.execute("INSERT OR IGNORE INTO roles (name) VALUES ('customer')")
    
    # Get role IDs
    cursor.execute("SELECT id, name FROM roles")
    roles = {row['name']: row['id'] for row in cursor.fetchall()}
    admin_role_id = roles['admin']
    customer_role_id = roles['customer']
    
    # 3. Assign roles to existing users
    cursor.execute("SELECT id, username FROM users")
    users = cursor.fetchall()
    
    for user in users:
        # Check if user already has a role
        cursor.execute("SELECT * FROM user_roles WHERE user_id = ?", (user['id'],))
        if cursor.fetchone():
            continue
            
        if user['username'] == 'online_fighter':
            cursor.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (user['id'], admin_role_id))
            print(f"Assigned ADMIN to {user['username']}")
        else:
            cursor.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (user['id'], customer_role_id))
            print(f"Assigned CUSTOMER to {user['username']}")
            
    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate_db()
