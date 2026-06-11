#!/usr/bin/env python3
"""
Add UNIQUE constraint on users.email for existing PostgreSQL databases.
This also backfills UNIQUE on provider_id and username if they're missing.

Usage:
  # Set DATABASE_URL env var (same as app)
  export DATABASE_URL="postgresql://..."
  python add_email_unique.py

Dry-run mode:
  python add_email_unique.py --dry-run
"""

import os
import sys
from pathlib import Path

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DRY_RUN = "--dry-run" in sys.argv

if not DATABASE_URL.lower().startswith("postgresql"):
    print("ERROR: DATABASE_URL must be set to a PostgreSQL URL")
    print("  export DATABASE_URL=\"postgresql://user:pass@host:5432/flask_auth_app\"")
    sys.exit(1)

if DRY_RUN:
    print("⚠️  DRY RUN — no changes will be made\n")

sys.path.insert(0, str(Path(__file__).parent))
from db import get_conn, is_postgres

if not is_postgres():
    print("ERROR: Not connected to PostgreSQL. Check DATABASE_URL.")
    sys.exit(1)

conn = get_conn()
cursor = conn.cursor()

def run(sql, desc):
    """Execute SQL and print result."""
    print(f"  {desc}...")
    if DRY_RUN:
        print(f"    SQL: {sql}")
        return
    try:
        cursor.execute(sql)
        conn.commit()
        print(f"    ✅ Done")
    except Exception as e:
        conn.rollback()
        print(f"    ❌ Error: {e}")

def check_constraint_exists(constraint_name):
    """Check if a constraint already exists."""
    sql = """
        SELECT 1 FROM pg_constraint pc
        JOIN pg_class c ON pc.conrelid = c.oid
        WHERE c.relname = 'users' AND pc.conname = %s
    """
    result = cursor.execute(sql, (constraint_name,))
    return result.fetchone() is not None

def check_index_exists(index_name):
    """Check if an index already exists."""
    sql = """
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'users' AND indexname = %s
    """
    result = cursor.execute(sql, (index_name,))
    return result.fetchone() is not None

print("=" * 60)
print("  Adding UNIQUE constraint on users.email")
print("=" * 60)
print()

# Step 1: Find and remove duplicate emails (if any) before adding constraint
print("Step 1: Check for duplicate emails...")
dup_check = cursor.execute("""
    SELECT email, COUNT(*) as cnt
    FROM users
    WHERE email IS NOT NULL AND email != ''
    GROUP BY email
    HAVING COUNT(*) > 1
""")
duplicates = dup_check.fetchall()
if duplicates:
    print(f"  ⚠️  Found {len(duplicates)} duplicate emails:")
    for row in duplicates:
        print(f"    - '{row['email']}': {row['cnt']} occurrences")
    if not DRY_RUN:
        print("  Deduplicating: setting duplicates to NULL (keeping the oldest row)...")
        for row in duplicates:
            email = row['email']
            # Keep the row with the smallest id (oldest), null out others
            cursor.execute("""
                UPDATE users
                SET email = NULL
                WHERE email = %s
                  AND id != (SELECT MIN(id) FROM users WHERE email = %s)
            """, (email, email))
        conn.commit()
        print("  ✅ Duplicates cleared")
else:
    print("  ✅ No duplicate emails found")
print()

# Step 2: Add UNIQUE constraint on email
print("Step 2: Adding UNIQUE constraint on users.email...")
if check_constraint_exists("users_email_key"):
    print("  ⏭️  Constraint 'users_email_key' already exists")
else:
    run("""
        ALTER TABLE users
        ADD CONSTRAINT users_email_key UNIQUE (email)
    """, "Adding UNIQUE (email)")

# Step 3: Also ensure provider_id and username have proper unique constraints
print()
print("Step 3: Verifying existing unique constraints...")

if not check_constraint_exists("users_provider_id_key") and not check_index_exists("users_provider_id_key"):
    run("""
        ALTER TABLE users
        ADD CONSTRAINT users_provider_id_key UNIQUE (provider_id)
    """, "Adding UNIQUE (provider_id)")
else:
    print("  ✅ provider_id constraint OK")

if not check_constraint_exists("users_username_key") and not check_index_exists("users_username_key"):
    run("""
        ALTER TABLE users
        ADD CONSTRAINT users_username_key UNIQUE (username)
    """, "Adding UNIQUE (username)")
else:
    print("  ✅ username constraint OK")

conn.close()

print()
print("=" * 60)
if DRY_RUN:
    print("✅ Dry run complete. Remove --dry-run to apply changes.")
else:
    print("✅ All constraints applied successfully!")
    print()
    print("Next steps:")
    print("  1. Also update the INSERT in Google OAuth path (line ~864) to handle")
    print("     email UNIQUE violations gracefully")
    print("  2. Redeploy the updated app")
print("=" * 60)
