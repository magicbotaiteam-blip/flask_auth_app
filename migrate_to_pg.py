#!/usr/bin/env python3
"""
Migrate SQLite (users.db) → PostgreSQL (via DATABASE_URL).

Usage:
  # First, set DATABASE_URL env var
  export DATABASE_URL="postgresql://user:pass@host:5432/magic_bot_ai"

  # Run migration
  python migrate_to_pg.py

This script:
  1. Reads all data from the existing SQLite users.db
  2. Creates all tables in PostgreSQL (mirroring the SQLite schema)
  3. Inserts all rows into PostgreSQL
  4. Verifies row counts match
"""

import os
import sys
import sqlite3
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────

SQLITE_PATH = Path(__file__).parent / "users.db"
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DRY_RUN = "--dry-run" in sys.argv

if not DATABASE_URL.lower().startswith("postgresql"):
    print("ERROR: DATABASE_URL must be set to a PostgreSQL URL")
    print("  export DATABASE_URL=\"postgresql://user:pass@host:5432/magic_bot_ai\"")
    sys.exit(1)

print(f"Migrating from: {SQLITE_PATH}")
print(f"Migrating to:   {DATABASE_URL}")
if DRY_RUN:
    print("⚠️  DRY RUN — no changes will be made")
print()

if not SQLITE_PATH.exists():
    print(f"ERROR: SQLite database not found at {SQLITE_PATH}")
    sys.exit(1)


# ── Connect ─────────────────────────────────────────────────────

def get_sqlite_conn():
    c = sqlite3.connect(str(SQLITE_PATH))
    c.row_factory = sqlite3.Row
    return c


def get_pg_conn():
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    session = Session()

    class PgConnection:
        """Thin wrapper to mimic sqlite3 connection for this migration."""

        def __init__(self, s):
            self._session = s

        def execute(self, sql, params=None):
            if params is None:
                params = ()
            return self._session.execute(text(sql), params)

        def executemany(self, sql, seq_params):
            for p in seq_params:
                self._session.execute(text(sql), p)

        def commit(self):
            self._session.commit()

        def rollback(self):
            self._session.rollback()

        def close(self):
            self._session.close()

    return PgConnection(session)


# ── Data types ──────────────────────────────────────────────────

# Tables in order (parents before children to respect FK constraints)
TABLE_ORDER = [
    "users",
    "bots",
    "roles",
    "user_roles",
    "referrals",
    "reward_tiers",
    "reward_redemptions",
    "password_reset_tokens",
    "bot_analytics",
    "groups",
    "group_members",
    "group_invitations",
    "shared_bots",
    "group_activity",
    "group_messages",
    "group_templates",
]


def get_sqlite_schema(sqlite_conn):
    """Get all CREATE TABLE statements from SQLite."""
    tables = sqlite_conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {t["name"]: t["sql"] for t in tables}


def convert_schema_to_pg(sqlite_sql):
    """Convert SQLite CREATE TABLE to PostgreSQL DDL."""
    import re

    if not sqlite_sql:
        return None

    ddl = sqlite_sql.strip()

    # AUTOINCREMENT → SERIAL (already handled in column defs)
    ddl = ddl.replace("AUTOINCREMENT", "")

    # INTEGER PRIMARY KEY → SERIAL PRIMARY KEY at column level
    ddl = re.sub(
        r"(\w+\s+)INTEGER\s+PRIMARY\s+KEY\b",
        lambda m: m.group(1) + "SERIAL PRIMARY KEY"
        if not m.group(0).lower().endswith("references")
        else m.group(0),
        ddl,
        flags=re.IGNORECASE,
    )

    # BOOLEAN DEFAULT TRUE/FALSE → keep as-is (PG supports it)
    # datetime('now') → NOW() in PG
    ddl = ddl.replace("datetime('now')", "NOW()")
    ddl = ddl.replace('datetime("now")', "NOW()")
    ddl = ddl.replace("CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")

    # Remove strftime function calls (migrate_simple handles data)
    # Drop FOREIGN KEY constraints that reference other tables during creation
    # (we'll add them back with ALTER TABLE if needed)

    return ddl


def create_pg_tables(pg_conn, schemas):
    """Create all tables in PostgreSQL (drop first for clean migration)."""
    # Drop existing tables in reverse order
    for table in reversed(TABLE_ORDER):
        if table in schemas:
            pg_conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")

    # Create tables
    for table in TABLE_ORDER:
        sql = schemas.get(table)
        if sql:
            pg_ddl = convert_schema_to_pg(sql)
            if pg_ddl:
                print(f"  Creating table: {table}")
                if not DRY_RUN:
                    pg_conn.execute(pg_ddl)

    if not DRY_RUN:
        pg_conn.commit()


def migrate_data(sqlite_conn, pg_conn):
    """Migrate all data from SQLite to PostgreSQL."""
    print()
    print("Migrating data...")
    print("=" * 60)

    total_rows = 0
    errors = []

    for table in TABLE_ORDER:
        # Check if table exists in SQLite
        tables = sqlite_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchall()
        if not tables:
            print(f"  ⏭️  {table}: table not found in SQLite, skipping")
            continue

        # Read all rows
        rows = sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()
        if not rows:
            print(f"  ⏭️  {table}: 0 rows, skipping")
            continue

        # Get column names
        columns = [desc[0] for desc in sqlite_conn.execute(f"SELECT * FROM {table} limit 0").description]

        col_list = ", ".join(columns)
        placeholders = ", ".join([f":{c}" for c in columns])

        insert_sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"

        if DRY_RUN:
            print(f"  📋 {table}: {len(rows)} rows (dry run, not inserted)")
            total_rows += len(rows)
            continue

        # Insert in batches
        batch_size = 100
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            try:
                pg_conn.executemany(insert_sql, [dict(r) for r in batch])
            except Exception as e:
                errors.append(f"{table} batch {i}: {e}")
                # Try row by row for better error messages
                for r in batch:
                    try:
                        pg_conn.execute(insert_sql, dict(r))
                    except Exception as e2:
                        errors.append(f"{table} row {r['id'] if 'id' in dict(r) else '?'}: {e2}")

        # Reset sequences for SERIAL columns
        try:
            pg_conn.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE(MAX(id), 0)) FROM {table}"
            )
        except Exception:
            pass  # table might not have an 'id' column

        print(f"  ✅ {table}: {len(rows)} rows migrated")
        total_rows += len(rows)

    if not DRY_RUN:
        pg_conn.commit()

    print()
    print(f"Total rows migrated: {total_rows}")
    if errors:
        print(f"Errors ({len(errors)}):")
        for e in errors[:10]:
            print(f"  ❌ {e}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")

    return total_rows, errors


def verify_migration(sqlite_conn, pg_conn):
    """Verify row counts match between SQLite and PostgreSQL."""
    print()
    print("Verifying migration...")
    print("=" * 60)

    all_ok = True
    for table in TABLE_ORDER:
        try:
            sq_count = sqlite_conn.execute(f"SELECT COUNT(*) as c FROM {table}").fetchone()["c"]
        except Exception:
            sq_count = -1

        try:
            pg_result = pg_conn.execute(f"SELECT COUNT(*) as c FROM {table}").fetchone()
            pg_count = pg_result["c"] if pg_result else -1
        except Exception as e:
            pg_count = -1
            print(f"  ❌ {table}: PG query error: {e}")

        if sq_count == pg_count:
            print(f"  ✅ {table}: {sq_count} rows ✓")
        else:
            print(f"  ❌ {table}: SQLite={sq_count} PG={pg_count}")
            all_ok = False

    return all_ok


# ── Main ────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("SQLite → PostgreSQL Migration")
    print("=" * 60)
    print()

    # Connect to both databases
    sqlite_conn = get_sqlite_conn()
    pg_conn = get_pg_conn()

    try:
        # Get schemas
        print("Reading SQLite schema...")
        schemas = get_sqlite_schema(sqlite_conn)
        print(f"  Found {len(schemas)} tables:")
        for name, sql in schemas.items():
            print(f"    - {name}")
        print()

        # Create PG tables
        print("Creating PostgreSQL tables...")
        print("-" * 40)
        create_pg_tables(pg_conn, schemas)

        # Migrate data
        total, errors = migrate_data(sqlite_conn, pg_conn)

        if not DRY_RUN:
            # Verify
            verify_migration(sqlite_conn, pg_conn)

        print()
        print("=" * 60)
        if DRY_RUN:
            print("✅ Dry run complete. Set DATABASE_URL and remove --dry-run to execute.")
        else:
            if errors:
                print("⚠️  Migration completed with some errors. Review above.")
            else:
                print("✅ Migration complete! Data transferred to PostgreSQL.")
            print()
            print("Next steps:")
            print("  1. Update ECS task definition with DATABASE_URL env var")
            print("  2. Redeploy the app")
            print("  3. Monitor application logs for DB errors")
            print("  4. Once confirmed working, you can archive/remove users.db")

    finally:
        sqlite_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    main()
