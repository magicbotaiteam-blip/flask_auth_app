#!/usr/bin/env python3
"""
Update shared_bots table to add is_active column
"""

import sqlite3
import os

DB_FILENAME = "users.db"

def update_schema():
    """Add is_active column to shared_bots table if it doesn't exist"""
    if not os.path.exists(DB_FILENAME):
        print(f"Database {DB_FILENAME} doesn't exist yet.")
        print("It will be created with the new schema when the app starts.")
        return
    
    conn = sqlite3.connect(DB_FILENAME)
    conn.row_factory = sqlite3.Row
    
    print(f"Updating database: {DB_FILENAME}")
    print("=" * 60)
    
    # Check if is_active column exists
    cursor = conn.execute("PRAGMA table_info(shared_bots)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'is_active' in columns:
        print("✅ shared_bots table already has is_active column")
    else:
        print("Adding is_active column to shared_bots table...")
        try:
            # SQLite doesn't support ADD COLUMN IF NOT EXISTS directly
            # We need to check first
            conn.execute("ALTER TABLE shared_bots ADD COLUMN is_active BOOLEAN DEFAULT TRUE")
            conn.commit()
            print("✅ Added is_active column to shared_bots table")
            
            # Verify
            cursor = conn.execute("PRAGMA table_info(shared_bots)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'is_active' in columns:
                print("✅ Verified: is_active column added successfully")
            else:
                print("❌ Failed to add is_active column")
                
        except Exception as e:
            print(f"❌ Error adding column: {e}")
            # Try a different approach - recreate table
            print("\nTrying alternative approach...")
            try:
                # Create a backup of the table
                conn.execute("CREATE TABLE IF NOT EXISTS shared_bots_backup AS SELECT * FROM shared_bots")
                
                # Drop the old table
                conn.execute("DROP TABLE shared_bots")
                
                # Create new table with is_active column
                conn.execute("""
                    CREATE TABLE shared_bots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        bot_id INTEGER NOT NULL,
                        group_id INTEGER NOT NULL,
                        shared_by INTEGER NOT NULL,
                        shared_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        permissions TEXT DEFAULT '{}',
                        is_active BOOLEAN DEFAULT TRUE,
                        FOREIGN KEY (bot_id) REFERENCES bots (id) ON DELETE CASCADE,
                        FOREIGN KEY (group_id) REFERENCES groups (id) ON DELETE CASCADE,
                        FOREIGN KEY (shared_by) REFERENCES users (id) ON DELETE CASCADE,
                        UNIQUE(bot_id, group_id)
                    )
                """)
                
                # Copy data back (is_active will be TRUE by default)
                conn.execute("""
                    INSERT INTO shared_bots (id, bot_id, group_id, shared_by, shared_at, permissions)
                    SELECT id, bot_id, group_id, shared_by, shared_at, permissions
                    FROM shared_bots_backup
                """)
                
                # Drop backup
                conn.execute("DROP TABLE shared_bots_backup")
                
                conn.commit()
                print("✅ Recreated shared_bots table with is_active column")
                
            except Exception as e2:
                print(f"❌ Error recreating table: {e2}")
                conn.rollback()
    
    # Also check other tables for consistency
    print("\nChecking other tables...")
    
    tables_to_check = ['bots', 'groups']
    for table in tables_to_check:
        cursor = conn.execute(f"PRAGMA table_info({table})")
        columns = [col[1] for col in cursor.fetchall()]
        if 'is_active' in columns:
            print(f"✅ {table} table has is_active column")
        else:
            print(f"⚠️  {table} table doesn't have is_active column")
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("Schema update complete!")
    print("The app should now work without 'no such column' errors.")
    print("=" * 60)

if __name__ == "__main__":
    update_schema()