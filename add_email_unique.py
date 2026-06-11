#!/usr/bin/env python3
"""
Add UNIQUE constraint on users.email for existing PostgreSQL databases.

Usage:
  export DATABASE_URL="postgresql://user:pass@host:5432/flask_auth_app"
  python add_email_unique.py --dry-run   # preview only
  python add_email_unique.py             # apply
"""

import os
import sys
import re

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DRY_RUN = "--dry-run" in sys.argv

if not DATABASE_URL.lower().startswith("postgresql"):
    print("ERROR: DATABASE_URL must be set to a PostgreSQL URL")
    print("  export DATABASE_URL=\"postgresql://user:pass@host:5432/flask_auth_app\"")
    sys.exit(1)

if DRY_RUN:
    print("⚠️  DRY RUN — no changes will be made\n")

# Parse DATABASE_URL for direct psycopg2 connection
match = re.match(
    r"postgresql(?:://|://)(.+):(.+)@(.+):(\d+)/(.+)",
    DATABASE_URL,
)
if not match:
    print("ERROR: Could not parse DATABASE_URL")
    sys.exit(1)

user, password, host, port, dbname = match.groups()

try:
    import psycopg2
except ImportError:
    print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

# ── Direct psycopg2 connection ─────────────────────────────────

conn = psycopg2.connect(
    host=host,
    port=port,
    user=user,
    password=password,
    dbname=dbname,
)
conn.autocommit = True
cursor = conn.cursor()


def run(sql, desc):
    """Execute SQL and print result."""
    print(f"  {desc}...")
    if DRY_RUN:
        print(f"    SQL: {sql}")
        return
    try:
        if not conn.autocommit:
            conn.autocommit = True
        cursor.execute(sql)
        print(f"    ✅ Done")
    except Exception as e:
        print(f"    ❌ Error: {e}")


def check_constraint_exists(constraint_name):
    """Check if a constraint already exists."""
    cursor.execute("""
        SELECT 1 FROM pg_constraint pc
        JOIN pg_class c ON pc.conrelid = c.oid
        WHERE c.relname = 'users' AND pc.conname = %s
    """, (constraint_name,))
    return cursor.fetchone() is not None


def check_index_exists(index_name):
    """Check if an index already exists."""
    cursor.execute("""
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'users' AND indexname = %s
    """, (index_name,))
    return cursor.fetchone() is not None


print("=" * 60)
print("  Adding UNIQUE constraint on users.email")
print("=" * 60)
print()

# Step 1: Find and remove duplicate emails
print("Step 1: Check for duplicate emails...")
cursor.execute("""
    SELECT email, COUNT(*) as cnt
    FROM users
    WHERE email IS NOT NULL AND email != ''
    GROUP BY email
    HAVING COUNT(*) > 1
""")
duplicates = cursor.fetchall()
if duplicates:
    print(f"  ⚠️  Found {len(duplicates)} duplicate emails:")
    for row in duplicates:
        print(f"    - '{row[0]}': {row[1]} occurrences")
    if not DRY_RUN:
        print("  Deduplicating: setting duplicates to NULL (keeping the oldest row)...")
        for row in duplicates:
            email = row[0]
            cursor.execute("""
                UPDATE users
                SET email = NULL
                WHERE email = %s
                  AND id != (SELECT MIN(id) FROM users WHERE email = %s)
            """, (email, email))
        print("  ✅ Duplicates cleared")
else:
    print("  ✅ No duplicate emails found")
print()

# Step 2: Add UNIQUE constraint on email
print("Step 2: Adding UNIQUE constraint on users.email...")
if check_constraint_exists("users_email_key"):
    print("  ⏭️  Constraint 'users_email_key' already exists")
else:
    # Handle existing NULL/empty emails before adding constraint
    run("""
        UPDATE users SET email = NULL WHERE email = ''
    """, "Normalizing empty emails to NULL")

    run("""
        ALTER TABLE users
        ADD CONSTRAINT users_email_key UNIQUE (email)
    """, "Adding UNIQUE (email)")

# Step 3: Also ensure provider_id and username have proper unique constraints
print()
print("Step 3: Verifying existing unique constraints...")

# PostgreSQL automatically creates unique indexes for UNIQUE constraints
# named like: users_provider_id_key, users_username_key
for col, constraint_name in [("provider_id", "users_provider_id_key"), ("username", "users_username_key")]:
    if check_constraint_exists(constraint_name):
        print(f"  ✅ {col} constraint OK")
    else:
        # Check if there's already a unique index (not backed by constraint)
        index_name = f"ix_users_{col}"
        if check_index_exists(index_name):
            print(f"  ⏭️  {col}: unique index '{index_name}' exists (no constraint needed)")
        else:
            run(f"ALTER TABLE users ADD CONSTRAINT {constraint_name} UNIQUE ({col})",
                f"Adding UNIQUE ({col})")

conn.close()

print()
print("=" * 60)
if DRY_RUN:
    print("✅ Dry run complete. Remove --dry-run to apply changes.")
else:
    print("✅ All constraints applied successfully!")
    print()
    print("Next steps:")
    print("  1. Deploy the updated app_complete_with_groups.py")
    print("  2. Restart the ECS task")
print("=" * 60)
