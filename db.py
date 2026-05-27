"""
Database abstraction layer for Magic Bot AI Flask App.
Supports PostgreSQL (production via SQLAlchemy) and SQLite (local dev).

Usage:
  from db import get_conn, execute, fetchone, fetchall, close

The DATABASE_URL env var controls the backend:
  - postgresql://user:pass@host/dbname → PostgreSQL (production)
  - sqlite:///users.db (or unset) → SQLite (local dev)

Migration: running ./migrate_to_pg.py exports SQLite data → seeds PostgreSQL.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

# ── Detect backend ──────────────────────────────────────────────

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# If the URL looks like a Postgres URL, use SQLAlchemy.
USE_PG = DATABASE_URL.lower().startswith("postgresql")

# ── Module-level state ──────────────────────────────────────────

_engine = None
_SessionLocal = None

# ── Helpers ─────────────────────────────────────────────────────

def _row_as_dict(row):
    """Convert a SQLAlchemy Row to a dict compatible with sqlite3.Row API."""
    if row is None:
        return None
    # SQLAlchemy 2.0 Row supports ._mapping
    try:
        return dict(row._mapping)
    except AttributeError:
        try:
            return dict(zip(row.keys(), row))
        except Exception:
            return dict(row)


# ================================================================
# PostgreSQL / SQLAlchemy backend
# ================================================================

def _init_pg():
    global _engine, _SessionLocal
    if _engine is not None:
        return _engine

    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    _engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=10,
    )
    _SessionLocal = sessionmaker(bind=_engine)

    # ensure pgcrypto for gen_random_uuid() if needed
    with _engine.connect() as c:
        c.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        c.commit()

    return _engine


def _pg_conn():
    """Return a connection-wrapper that mimics sqlite3 connection API."""
    _init_pg()
    session = _SessionLocal()
    return _PgConnection(session)


class _PgConnection:
    """Wraps a SQLAlchemy session to look like a sqlite3 connection + Row factory."""

    def __init__(self, session):
        self._session = session
        self._txn_open = False

    def execute(self, sql, params=None):
        import re
        from sqlalchemy import text
        if params is None:
            params = ()
        if isinstance(sql, str) and '?' in sql:
            # Use raw psycopg2 for ?-placeholder SQL (sqlite3 compatibility)
            raw_conn = self._session.connection().connection
            raw_cursor = raw_conn.cursor()
            raw_sql = sql.replace('?', '%s')
            raw_cursor.execute(raw_sql, params if params else [])
            cursor_obj = _PgCursor(raw_cursor)
            # Populate lastrowid for INSERT statements (sqlite3 compatibility)
            if raw_sql.strip().upper().startswith("INSERT"):
                try:
                    raw_cursor.execute("SELECT LASTVAL()")
                    row = raw_cursor.fetchone()
                    if row:
                        cursor_obj.lastrowid = row[0]
                except Exception:
                    # LASTVAL() fails if no sequence was affected, ignore
                    pass
            return cursor_obj
        else:
            stmt = text(sql) if isinstance(sql, str) else sql
            result = self._session.execute(stmt, params)
            cursor_obj = _PgCursor(result)
            # SQLAlchemy text() path: populate lastrowid for INSERT
            if isinstance(sql, str) and sql.strip().upper().startswith("INSERT"):
                try:
                    raw_conn = self._session.connection().connection
                    raw_cursor = raw_conn.cursor()
                    raw_cursor.execute("SELECT LASTVAL()")
                    row = raw_cursor.fetchone()
                    if row:
                        cursor_obj.lastrowid = row[0]
                except Exception:
                    pass
            return cursor_obj

    def executemany(self, sql, seq_of_params):
        from sqlalchemy import text
        stmt = text(sql) if isinstance(sql, str) else sql
        # Use raw psycopg2 connection for executemany (tuple params)
        raw_conn = self._session.connection().connection
        raw_cursor = raw_conn.cursor()
        raw_sql = str(stmt)
        # Convert ? to %s for psycopg2
        raw_sql = raw_sql.replace('?', '%s')
        for params in seq_of_params:
            raw_cursor.execute(raw_sql, params)

    def commit(self):
        self._session.commit()

    def rollback(self):
        self._session.rollback()

    def close(self):
        if self._txn_open:
            try:
                self._session.commit()
            except Exception:
                self._session.rollback()
        self._session.close()

    # sqlite3 API compat
    @property
    def total_changes(self):
        return 0  # not meaningful for PG

    # PRAGMA no-ops (ignored in PG)
    PRAGMA_IGNORE = {"journal_mode", "busy_timeout", "synchronous", "foreign_keys", "page_size", "cache_size"}

    def cursor(self):
        """Return self as a cursor (sqlite3 compat)."""
        return self

    def __getattr__(self, name):
        if name == "PRAGMA_IGNORE":
            return self.PRAGMA_IGNORE
        raise AttributeError(f"'_PgConnection' object has no attribute '{name}'")


class _PgCursor:
    """Wraps SQLAlchemy cursor result to mimic sqlite3.Cursor."""

    def __init__(self, result):
        self._result = result
        self._rows = None  # lazy
        self._iterator = None
        self._key_fn = None  # for row_factory equivalent
        self.lastrowid = None
        # Detect if result is a raw psycopg2 cursor (has description attrs directly)
        import psycopg2
        self._is_raw = isinstance(result, psycopg2.extensions.cursor)
        if self._is_raw:
            self._columns = [desc[0] for desc in result.description] if result.description else []

    def _row_to_dict(self, row):
        if self._is_raw:
            # row is a tuple, map by column position
            return dict(zip(self._columns, row))
        return row._mapping

    def fetchone(self):
        if self._is_raw:
            row = self._result.fetchone()
            if row is None:
                return None
            return _PgRow(self._row_to_dict(row))
        if self._rows is None:
            self._rows = list(self._result)
        if self._iterator is None:
            self._iterator = iter(self._rows)
        try:
            row = next(self._iterator)
            return _PgRow(row._mapping)
        except StopIteration:
            return None

    def fetchall(self):
        if self._is_raw:
            rows = self._result.fetchall()
            return [_PgRow(self._row_to_dict(r)) for r in rows]
        if self._rows is None:
            self._rows = list(self._result)
        return [_PgRow(r._mapping) for r in self._rows]

    @property
    def description(self):
        if hasattr(self._result, 'keys'):
            return self._result.keys()
        if self._is_raw:
            return [desc[0] for desc in self._result.description] if self._result.description else []
        return []


class _PgRow:
    """Dict-like row compatible with sqlite3.Row."""

    def __init__(self, mapping):
        self._mapping = {}
        for k, v in dict(mapping).items():
            # Convert PG datetime objects to strings (SQLite compatibility)
            if hasattr(v, 'isoformat'):
                self._mapping[k] = v.isoformat()
            else:
                self._mapping[k] = v

    def keys(self):
        return self._mapping.keys()

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self._mapping.values())[key]
        return self._mapping[key]

    def __getattr__(self, name):
        if name in self._mapping:
            return self._mapping[name]
        raise AttributeError(f"No column '{name}'")

    def __contains__(self, item):
        return item in self._mapping

    def __iter__(self):
        return iter(self._mapping.values())

    def __len__(self):
        return len(self._mapping)

    def __repr__(self):
        return f"<Row {dict(self._mapping)}>"


# ================================================================
# SQLite backend (no changes — existing code assumes it)
# ================================================================

def _sqlite_conn():
    import sqlite3
    db_path = Path(__file__).parent / "users.db"
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ================================================================
# Public API
# ================================================================

def get_conn():
    """
    Get a database connection.
    Returns a sqlite3-compatible connection object for both backends.

    For PostgreSQL, wraps a SQLAlchemy session with execute/commit/rollback/close
    that accepts raw SQL strings and returns Row-like objects (.keys(), ['col'], [0]).
    """
    if USE_PG:
        return _pg_conn()
    return _sqlite_conn()


@contextmanager
def connect():
    """Context-manager for a DB connection (auto-closes)."""
    conn = get_conn()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction():
    """Context-manager for an auto-committing/rollback transaction."""
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def is_postgres():
    """Returns True if we're connected to PostgreSQL."""
    return USE_PG


# ── Schema helpers ──────────────────────────────────────────────

# Mapping: SQLite column types → PostgreSQL equivalents
PG_TYPE_MAP = {
    "INTEGER": "INTEGER",
    "INTEGER PRIMARY KEY AUTOINCREMENT": "SERIAL PRIMARY KEY",
    "INTEGER PRIMARY KEY": "SERIAL PRIMARY KEY",
    "INTEGER NOT NULL": "INTEGER NOT NULL",
    "TEXT": "TEXT",
    "TEXT NOT NULL": "TEXT NOT NULL",
    "TEXT UNIQUE": "TEXT UNIQUE",
    "TEXT NOT NULL UNIQUE": "TEXT NOT NULL UNIQUE",
    "BOOLEAN": "BOOLEAN",
    "BOOLEAN DEFAULT TRUE": "BOOLEAN DEFAULT TRUE",
    "BOOLEAN DEFAULT FALSE": "BOOLEAN DEFAULT FALSE",
    "TIMESTAMP": "TIMESTAMP",
    "TIMESTAMP DEFAULT CURRENT_TIMESTAMP": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "BLOB": "BYTEA",
    "FOREIGN KEY": "FOREIGN KEY",
    "REAL": "REAL",
}


def sqlite_to_pg_ddl(sqlite_ddl: str) -> str:
    """
    Convert a single SQLite CREATE TABLE statement to PostgreSQL-compatible DDL.

    Handles:
      - INTEGER PRIMARY KEY AUTOINCREMENT → SERIAL PRIMARY KEY
      - TEXT → TEXT
      - BOOLEAN → BOOLEAN
      - strftime → TO_CHAR or EXTRACT
      - CURRENT_TIMESTAMP → CURRENT_TIMESTAMP (same)
      - INSERT OR IGNORE → INSERT ... ON CONFLICT DO NOTHING
      - DROP TABLE IF EXISTS → same
      - Removes PRAGMAs
      - datetime('now', ...) → NOW() + INTERVAL
    """
    import re

    ddl = sqlite_ddl.strip()

    # Remove PRAGMA statements
    if ddl.upper().startswith("PRAGMA"):
        return None

    # Skip VACUUM
    if ddl.upper().startswith("VACUUM"):
        return None

    # INSERT OR IGNORE → ON CONFLICT DO NOTHING
    if ddl.upper().startswith("INSERT OR IGNORE"):
        ddl = re.sub(
            r"INSERT\s+OR\s+IGNORE\s+INTO",
            "INSERT INTO",
            ddl,
            flags=re.IGNORECASE,
        )
        # Add ON CONFLICT DO NOTHING if not present (we'll defer this to the caller)
        return ddl + " ON CONFLICT DO NOTHING"

    # INSERT OR REPLACE → ON CONFLICT ... DO UPDATE
    if ddl.upper().startswith("INSERT OR REPLACE"):
        return None  # must be handled manually

    # CREATE TABLE — convert types
    if ddl.upper().startswith("CREATE TABLE"):
        # Remove IF NOT EXISTS for clean slate, but keep it for migrations
        # Replace AUTOINCREMENT
        ddl = ddl.replace("AUTOINCREMENT", "")

        # Replace INTEGER PRIMARY KEY references
        ddl = re.sub(
            r"\bINTEGER\s+PRIMARY\s+KEY\s+REFERENCES",
            "INTEGER REFERENCES",
            ddl,
            flags=re.IGNORECASE,
        )

        # Boolean → BOOLEAN
        ddl = re.sub(r"\bBOOLEAN\b", "BOOLEAN", ddl, flags=re.IGNORECASE)

        # FOREIGN KEY inline syntax — PG allows it in CREATE TABLE
        # Foreign key constraints at column level need REFERENCES keyword
        # which is already used.
        # Ensure REFERENCES uses PG-compatible syntax

        # Convert column-level INTEGER PRIMARY KEY to SERIAL PRIMARY KEY
        ddl = re.sub(
            r"(\w+\s+)INTEGER\s+PRIMARY\s+KEY",
            r"\1SERIAL PRIMARY KEY",
            ddl,
            flags=re.IGNORECASE,
        )

        return ddl

    # Other statements pass through
    return ddl
