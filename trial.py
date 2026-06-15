"""
Trial & Referral Bonus System for Magic Bot AI
Tracks free trial period, bonus months from referrals, and daily notifications.

Rules:
- 30 days free trial after signup
- +1 bonus free month for each successful customer introduction (referral)
- Auto-notify user daily when trial has ≤15 days remaining
"""

from datetime import datetime, timedelta, date
from typing import Optional, Dict, Any
from db import get_conn, is_postgres
from log_util import get_logger

logger = get_logger("app")

TRIAL_DAYS = 30


def init_trial_tables():
    """Add trial columns to users table and create customer_interactions table."""
    pg = is_postgres()
    conn = get_conn()

    # Add trial columns to users (migration-safe)
    migrations = [
        ("ALTER TABLE users ADD COLUMN trial_started_at TIMESTAMP DEFAULT NULL", "trial_started_at"),
        ("ALTER TABLE users ADD COLUMN bonus_trial_months INTEGER DEFAULT 0", "bonus_trial_months"),
    ]
    for col_sql, col_name in migrations:
        if pg:
            chk = conn.execute(f"""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = '{col_name}'
            """).fetchone()
            if not chk:
                logger.info(f"[TRIAL] Added {col_name} column to users")
                conn.execute(col_sql)
        else:
            try:
                conn.execute(col_sql)
                logger.info(f"[TRIAL] Added {col_name} column to users")
            except Exception:
                pass

    # Customer interactions table — tracks every referral the user makes
    pk = "SERIAL PRIMARY KEY" if pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
    if pg:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS customer_interactions (
                id {pk},
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                referee_name TEXT NOT NULL,
                referee_email TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS customer_interactions (
                id {pk},
                user_id INTEGER NOT NULL,
                referee_name TEXT NOT NULL,
                referee_email TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_customer_interactions_user_id ON customer_interactions(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_customer_interactions_status ON customer_interactions(status)")

    conn.commit()
    conn.close()
    logger.info("[TRIAL] Trial tables initialized")


def ensure_trial_started(user_id: int):
    """Set trial_started_at if not already set (called on signup)."""
    pg = is_postgres()
    conn = get_conn()
    user = conn.execute(
        "SELECT trial_started_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if user and user["trial_started_at"] is None:
        now_fn = "CURRENT_TIMESTAMP" if pg else "datetime('now')"
        conn.execute(
            f"UPDATE users SET trial_started_at = {now_fn} WHERE id = ?",
            (user_id,)
        )
        conn.commit()
        logger.info(f"[TRIAL] Started trial for user {user_id}")
    conn.close()


def get_trial_info(user_id: int) -> Dict[str, Any]:
    """
    Calculate trial information for a user.
    Returns dict with: days_remaining, total_days, trial_end, bonus_months, etc.
    Admin users skip the trial system entirely.
    """
    pg = is_postgres()
    conn = get_conn()

    user = conn.execute(
        "SELECT trial_started_at, bonus_trial_months, created_at FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    conn.close()

    if not user:
        return {"error": "User not found"}

    # Check if user is admin (role column may not exist on legacy SQLite)
    try:
        conn2 = get_conn()
        role_row = conn2.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
        conn2.close()
        if role_row and role_row["role"] == "admin":
            return {
                "admin": True,
                "expired": False,
                "days_remaining": 9999,
                "total_days": 9999,
                "bonus_months": 0,
                "trial_end": None,
                "base_days": TRIAL_DAYS,
            }
    except Exception:
        pass

    if not user:
        return {"error": "User not found"}

    # Use trial_started_at if set, otherwise use created_at
    start_raw = user["trial_started_at"] or user["created_at"]
    if isinstance(start_raw, str):
        start_date = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
    else:
        start_date = start_raw

    if start_date.tzinfo is not None:
        now = datetime.now(start_date.tzinfo)
    else:
        now = datetime.now()

    bonus_months = user["bonus_trial_months"] or 0
    total_days = TRIAL_DAYS + (bonus_months * 30)
    trial_end = start_date + timedelta(days=total_days)

    remaining = (trial_end - now).days
    # Fractional day — if less than 1 full day left, show 0
    if remaining < 0:
        remaining = 0

    expired = now >= trial_end

    return {
        "start_date": start_date.isoformat() if hasattr(start_date, 'isoformat') else str(start_date),
        "trial_end": trial_end.isoformat() if hasattr(trial_end, 'isoformat') else str(trial_end),
        "total_days": total_days,
        "days_remaining": remaining,
        "bonus_months": bonus_months,
        "expired": expired,
        "base_days": TRIAL_DAYS,
    }


def add_bonus_month(user_id: int, conn=None):
    """
    Add a bonus free month for a successful referral.
    If conn is provided, reuse the existing connection for atomicity.
    """
    own_conn = False
    if conn is None:
        conn = get_conn()
        own_conn = True
    conn.execute(
        "UPDATE users SET bonus_trial_months = bonus_trial_months + 1 WHERE id = ?",
        (user_id,)
    )
    if own_conn:
        conn.commit()
        conn.close()
    logger.info(f"[TRIAL] Added 1 bonus month for user {user_id}")


def log_customer_interaction(user_id: int, name: str, email: str, status: str = "pending", conn=None):
    """
    Log a customer interaction (referral attempt).
    If a pending interaction exists for this user+email, update it instead of duplicating.
    If conn is provided, reuse the existing connection for atomicity.
    """
    own_conn = False
    if conn is None:
        conn = get_conn()
        own_conn = True
    existing = conn.execute(
        "SELECT id, status FROM customer_interactions WHERE user_id = ? AND referee_email = ? ORDER BY created_at DESC LIMIT 1",
        (user_id, email)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE customer_interactions SET status = ?, referee_name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, name, existing["id"])
        )
    else:
        conn.execute(
            "INSERT INTO customer_interactions (user_id, referee_name, referee_email, status) VALUES (?, ?, ?, ?)",
            (user_id, name, email, status)
        )
    if own_conn:
        conn.commit()
        conn.close()


def update_interaction_status(interaction_id: int, status: str):
    """Update the status of a customer interaction (pending -> signed_up)."""
    conn = get_conn()
    conn.execute(
        "UPDATE customer_interactions SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, interaction_id)
    )
    conn.commit()
    conn.close()


def get_interactions(user_id: int) -> list:
    """Get all customer interactions for a user. Admins get empty list."""
    conn = get_conn()
    try:
        user = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
        if user and user["role"] == "admin":
            conn.close()
            return []
    except Exception:
        pass
    rows = conn.execute(
        "SELECT * FROM customer_interactions WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_interaction_stats(user_id: int) -> Dict[str, int]:
    """Get interaction stats per user. Admins get zeros."""
    conn = get_conn()
    try:
        # Check if admin via roles/user_roles join (works with both app schema and direct role column)
        from db import is_postgres as _is_pg
        if _is_pg():
            user_role = conn.execute(
                """SELECT r.name FROM roles r
                   JOIN user_roles ur ON r.id = ur.role_id
                   WHERE ur.user_id = ?""",
                (user_id,)
            ).fetchone()
        else:
            user_role = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
        if user_role:
            role_val = user_role[0]
            if role_val == "admin":
                conn.close()
                return {"total": 0, "pending": 0, "signed_up": 0, "expired": 0}
    except Exception:
        conn.rollback()
    stats = conn.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status = 'signed_up' THEN 1 ELSE 0 END) as signed_up,
            SUM(CASE WHEN status = 'expired' THEN 1 ELSE 0 END) as expired
        FROM customer_interactions
        WHERE user_id = ?
    """, (user_id,)).fetchone()
    conn.close()
    if stats:
        return dict(stats)
    return {"total": 0, "pending": 0, "signed_up": 0, "expired": 0}


def get_users_near_trial_end(days_threshold: int = 15) -> list:
    """
    Find users whose trial is ending within `days_threshold` days.
    Returns list of dicts with user_id, username, email, days_remaining.
    """
    pg = is_postgres()
    conn = get_conn()

    rows = conn.execute("SELECT id, username, email, trial_started_at, bonus_trial_months, created_at FROM users").fetchall()
    conn.close()

    result = []
    for row in rows:
        user = dict(row)
        info = get_trial_info(user["id"])
        if "error" in info:
            continue
        d = info["days_remaining"]
        if 0 < d <= days_threshold:
            result.append({
                "user_id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "days_remaining": d,
                "trial_end": info["trial_end"],
            })
        elif d == 0 and not info["expired"]:
            # Last day
            result.append({
                "user_id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "days_remaining": 0,
                "trial_end": info["trial_end"],
            })

    return result
