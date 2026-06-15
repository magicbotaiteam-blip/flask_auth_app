"""
Audit Logging System for Magic Bot AI
Records important actions to a DB-backed audit trail.

Auto-logs: login, signup, subscription changes, payment submissions,
payment approval/rejection, admin actions, and config changes.

Admin view: /admin/audit
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from db import get_conn, is_postgres
from log_util import get_logger, setup_file_logger

# Use a shared file logger (or fallback to console if not yet configured)
logger = get_logger("audit")

# Severity levels
INFO = "info"
WARNING = "warning"
ERROR = "error"
SECURITY = "security"


def init_audit_tables():
    """Create audit_logs table."""
    pg = is_postgres()
    conn = get_conn()
    pk = "SERIAL PRIMARY KEY" if pg else "INTEGER PRIMARY KEY AUTOINCREMENT"

    if pg:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id {pk},
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                username TEXT,
                action TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'general',
                severity TEXT NOT NULL DEFAULT 'info',
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                old_value TEXT,
                new_value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id {pk},
                user_id INTEGER,
                username TEXT,
                action TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'general',
                severity TEXT NOT NULL DEFAULT 'info',
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                old_value TEXT,
                new_value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
            )
        """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_category ON audit_logs(category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_severity ON audit_logs(severity)")

    conn.commit()
    conn.close()
    logger.info("[AUDIT] Audit tables initialized")


def log_action(
    user_id: Optional[int],
    username: Optional[str],
    action: str,
    category: str = "general",
    severity: str = INFO,
    details: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    conn_override=None,
):
    """Record an audit log entry.

    Args:
        user_id: The user who performed the action (None for system actions).
        username: Username at time of action (preserved even if user is later deleted).
        action: Short description of what happened (e.g. 'user.login', 'payment.approved').
        category: Grouping category (auth, payment, subscription, admin, config, etc.).
        severity: info, warning, error, or security.
        details: Free-form text description.
        ip_address: Request IP.
        user_agent: Request User-Agent.
        old_value: Previous state (for change tracking).
        new_value: New state.
        conn_override: Optional existing DB connection to reuse.
    """
    try:
        if conn_override:
            conn = conn_override
            close_after = False
        else:
            conn = get_conn()
            close_after = True

        conn.execute(
            """INSERT INTO audit_logs
               (user_id, username, action, category, severity, details,
                ip_address, user_agent, old_value, new_value)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id, username, action, category, severity,
                details, ip_address, user_agent, old_value, new_value
            )
        )
        conn.commit()

        if close_after:
            conn.close()

        # Also write to audit log file for system-level audit trail
        logger.log(
            logging.WARNING if severity == SECURITY or severity == WARNING else (
                logging.ERROR if severity == ERROR else logging.INFO
            ),
            f"[AUDIT] [{severity.upper()}] user={username or 'system'} action={action} "
            f"category={category} details={details or ''} "
            f"ip={ip_address or 'N/A'}"
        )

    except Exception as e:
        logger.error(f"[AUDIT] Failed to log action: {e}")


def get_audit_logs(
    limit: int = 100,
    offset: int = 0,
    user_id: Optional[int] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Query audit logs with optional filters."""
    conn = get_conn()
    conditions = []
    params = []

    if user_id is not None:
        conditions.append("al.user_id = ?")
        params.append(user_id)
    if category:
        conditions.append("al.category = ?")
        params.append(category)
    if severity:
        conditions.append("al.severity = ?")
        params.append(severity)
    if search:
        conditions.append("(al.action LIKE ? OR al.details LIKE ? OR al.username LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    rows = conn.execute(
        f"""SELECT al.* FROM audit_logs al
            {where}
            ORDER BY al.created_at DESC
            LIMIT ? OFFSET ?""",
        params + [limit, offset]
    ).fetchall()

    conn.close()
    return [dict(r) for r in rows]


def get_audit_stats() -> Dict[str, Any]:
    """Get audit log summary stats."""
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) as cnt FROM audit_logs").fetchone()["cnt"]
    by_category = conn.execute("""
        SELECT category, COUNT(*) as cnt FROM audit_logs GROUP BY category ORDER BY cnt DESC
    """).fetchall()
    by_severity = conn.execute("""
        SELECT severity, COUNT(*) as cnt FROM audit_logs GROUP BY severity ORDER BY cnt DESC
    """).fetchall()
    recent_actions = conn.execute("""
        SELECT action, COUNT(*) as cnt FROM audit_logs
        WHERE created_at > datetime('now', '-7 days')
        GROUP BY action ORDER BY cnt DESC LIMIT 10
    """).fetchall()
    conn.close()
    return {
        "total": total,
        "by_category": [dict(r) for r in by_category],
        "by_severity": [dict(r) for r in by_severity],
        "recent_actions": [dict(r) for r in recent_actions],
    }


def cleanup_old_logs(days: int = 90):
    """Delete audit logs older than specified days."""
    conn = get_conn()
    deleted = conn.execute(
        "DELETE FROM audit_logs WHERE created_at < datetime('now', ? || ' days')",
        (f"-{days}",)
    ).rowcount if not is_postgres() else None
    if is_postgres():
        conn.execute(
            "DELETE FROM audit_logs WHERE created_at < NOW() - INTERVAL %s DAY",
            (days,)
        )
        deleted = conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
    conn.commit()
    conn.close()
    logger.info(f"[AUDIT] Cleaned up logs older than {days} days")
    return deleted
