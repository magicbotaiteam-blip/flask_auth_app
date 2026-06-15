"""
Payment & Billing System for Magic Bot AI
Uses Stripe Checkout for payment processing.
Supports monthly subscriptions with async usage-based billing.

Free Trial → $5/month base subscription → Enterprise (custom)

Fully optional — if STRIPE_SECRET_KEY is not set, the system shows
a "Contact Sales" fallback instead.
"""

import os
import logging
from typing import Optional, Dict, Any
from db import get_conn, is_postgres

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Stripe keys (optional — system degrades gracefully without them)
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
BASIC_PRICE_ID = os.environ.get("STRIPE_BASIC_PRICE_ID", "price_basic_monthly")

HAS_STRIPE = bool(STRIPE_SECRET_KEY and STRIPE_PUBLISHABLE_KEY)

stripe = None
if HAS_STRIPE:
    try:
        import stripe as _stripe
        _stripe.api_key = STRIPE_SECRET_KEY
        stripe = _stripe
        logger.info("[PAYMENT] Stripe initialized")
    except ImportError:
        logger.warning("[PAYMENT] stripe package not installed — install with: pip install stripe")
        HAS_STRIPE = False
else:
    logger.info("[PAYMENT] Stripe not configured (STRIPE_SECRET_KEY missing) — payments disabled")


# ==================== DB Setup ====================

def init_payment_tables():
    """Create payment-related tables."""
    pg = is_postgres()
    conn = get_conn()
    pk = "SERIAL PRIMARY KEY" if pg else "INTEGER PRIMARY KEY AUTOINCREMENT"

    # Add billing columns to users table
    migrations = [
        ("ALTER TABLE users ADD COLUMN stripe_customer_id TEXT DEFAULT NULL", "stripe_customer_id"),
        ("ALTER TABLE users ADD COLUMN subscription_status TEXT DEFAULT 'trial'", "subscription_status"),
        ("ALTER TABLE users ADD COLUMN subscription_id TEXT DEFAULT NULL", "subscription_id"),
        ("ALTER TABLE users ADD COLUMN billing_plan TEXT DEFAULT 'free_trial'", "billing_plan"),
        ("ALTER TABLE users ADD COLUMN trial_ended_at TIMESTAMP DEFAULT NULL", "trial_ended_at"),
    ]
    for col_sql, col_name in migrations:
        if pg:
            chk = conn.execute(f"""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = '{col_name}'
            """).fetchone()
            if not chk:
                conn.execute(col_sql)
        else:
            try:
                conn.execute(col_sql)
            except Exception:
                pass

    # Payment history table
    if pg:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS payments (
                id {pk},
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                stripe_payment_intent_id TEXT,
                amount INTEGER NOT NULL,
                currency TEXT NOT NULL DEFAULT 'usd',
                status TEXT NOT NULL DEFAULT 'pending',
                description TEXT,
                period_start TIMESTAMP,
                period_end TIMESTAMP,
                invoice_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS payments (
                id {pk},
                user_id INTEGER NOT NULL,
                stripe_payment_intent_id TEXT,
                amount INTEGER NOT NULL,
                currency TEXT NOT NULL DEFAULT 'usd',
                status TEXT NOT NULL DEFAULT 'pending',
                description TEXT,
                period_start TIMESTAMP,
                period_end TIMESTAMP,
                invoice_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status)")

    # Payment submissions table (manual payment entry)
    if pg:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS payment_submissions (
                id {pk},
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                payment_method TEXT NOT NULL DEFAULT 'card',
                method_details TEXT,
                receipt_url TEXT,
                notes TEXT,
                amount REAL DEFAULT 5.0,
                currency TEXT DEFAULT 'USD',
                plan TEXT DEFAULT 'basic_monthly',
                status TEXT NOT NULL DEFAULT 'pending',
                admin_notes TEXT,
                reviewed_by INTEGER,
                reviewed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS payment_submissions (
                id {pk},
                user_id INTEGER NOT NULL,
                payment_method TEXT NOT NULL DEFAULT 'card',
                method_details TEXT,
                receipt_url TEXT,
                notes TEXT,
                amount REAL DEFAULT 5.0,
                currency TEXT DEFAULT 'USD',
                plan TEXT DEFAULT 'basic_monthly',
                status TEXT NOT NULL DEFAULT 'pending',
                admin_notes TEXT,
                reviewed_by INTEGER,
                reviewed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_payment_submissions_user_id ON payment_submissions(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_payment_submissions_status ON payment_submissions(status)")

    conn.commit()
    conn.close()
    logger.info("[PAYMENT] Payment tables initialized")


# ==================== Helper Functions ====================

def get_billing_info(user_id: int) -> Dict[str, Any]:
    """
    Get billing info for a user.
    Returns dict with current plan, status, and payment history.
    """
    conn = get_conn()
    user = conn.execute(
        """SELECT id, username, email, subscription_status, billing_plan,
                  stripe_customer_id, trial_started_at, bonus_trial_months, created_at
           FROM users WHERE id = ?""",
        (user_id,)
    ).fetchone()
    conn.close()

    if not user:
        return {"error": "User not found"}

    user = dict(user)
    # Get trial info from trial.py
    from trial import get_trial_info
    trial_info = get_trial_info(user_id)
    trial_expired = trial_info.get("expired", False) if trial_info else True
    days_remaining = trial_info.get("days_remaining", 0) if trial_info else 0

    # Determine overall status
    sub_status = user.get("subscription_status", "trial")

    if sub_status == "trial" and trial_expired:
        sub_status = "expired"

    # Get recent payments
    conn2 = get_conn()
    payments = conn2.execute(
        """SELECT * FROM payments WHERE user_id = ? ORDER BY created_at DESC LIMIT 10""",
        (user_id,)
    ).fetchall()
    conn2.close()

    return {
        "status": sub_status,
        "plan": user.get("billing_plan", "free_trial"),
        "stripe_customer_id": user.get("stripe_customer_id"),
        "trial_expired": trial_expired,
        "trial_days_remaining": days_remaining,
        "stripe_publishable_key": STRIPE_PUBLISHABLE_KEY if HAS_STRIPE else None,
        "payments": [dict(p) for p in payments],
        "has_stripe": HAS_STRIPE,
    }


def get_user_subscription_status(user_id: int) -> str:
    """Quick check: 'active', 'trial', 'expired', or 'canceled'."""
    conn = get_conn()
    user = conn.execute(
        "SELECT subscription_status, trial_started_at, bonus_trial_months, created_at FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()
    if not user:
        return "unknown"

    status = user["subscription_status"] or "trial"

    if status == "trial":
        # Check if trial has expired
        from trial import get_trial_info
        info = get_trial_info(user_id)
        if info.get("expired", False):
            status = "expired"

    return status


# ==================== Stripe Checkout Integration ====================

def create_checkout_session(user_id: int, price_id: str = None, success_url: str = None, cancel_url: str = None) -> Optional[str]:
    """
    Create a Stripe Checkout Session for subscription.
    Returns the checkout URL, or None if Stripe is not configured.
    """
    if not HAS_STRIPE or stripe is None:
        logger.warning("[PAYMENT] Cannot create checkout — Stripe not configured")
        return None

    try:
        conn = get_conn()
        user = conn.execute(
            "SELECT id, email, username, stripe_customer_id FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        conn.close()

        if not user:
            return None

        user = dict(user)
        customer_id = user.get("stripe_customer_id")

        # Create or retrieve Stripe customer
        if not customer_id:
            customer = stripe.Customer.create(
                email=user["email"],
                metadata={"user_id": str(user["id"]), "username": user["username"]},
            )
            customer_id = customer.id
            conn = get_conn()
            conn.execute(
                "UPDATE users SET stripe_customer_id = ? WHERE id = ?",
                (customer_id, user_id)
            )
            conn.commit()
            conn.close()

        # Create checkout session
        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": price_id or BASIC_PRICE_ID, "quantity": 1}],
            success_url=success_url or request.host_url.rstrip("/") + "/billing?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url or request.host_url.rstrip("/") + "/pricing",
            metadata={"user_id": str(user_id)},
        )
        return session.url

    except Exception as e:
        logger.error(f"[PAYMENT] Stripe checkout error: {e}")
        return None


def handle_checkout_completed(session_id: str):
    """
    Process successful Stripe checkout.
    Updates user subscription status and creates payment record.
    """
    if not HAS_STRIPE or stripe is None:
        return

    try:
        checkout = stripe.checkout.Session.retrieve(session_id)
        user_id = int(checkout.metadata.get("user_id", 0))
        subscription_id = checkout.subscription
        customer_id = checkout.customer

        if not user_id:
            logger.error("[PAYMENT] No user_id in checkout metadata")
            return

        conn = get_conn()
        # Update user
        conn.execute(
            """UPDATE users SET
                subscription_status = 'active',
                subscription_id = ?,
                stripe_customer_id = ?,
                billing_plan = 'basic_monthly'
               WHERE id = ?""",
            (subscription_id, customer_id, user_id)
        )

        # Record payment
        amount = checkout.amount_total or 0
        pg = is_postgres()
        if pg:
            conn.execute("""
                INSERT INTO payments (user_id, stripe_payment_intent_id, amount, currency, status, description)
                VALUES (?, ?, ?, ?, 'completed', ?)
            """, (user_id, checkout.payment_intent, amount, checkout.currency or 'usd', f"Subscription {subscription_id}"))
        else:
            conn.execute("""
                INSERT INTO payments (user_id, stripe_payment_intent_id, amount, currency, status, description)
                VALUES (?, ?, ?, ?, 'completed', ?)
            """, (user_id, checkout.payment_intent, amount, checkout.currency or 'usd', f"Subscription {subscription_id}"))

        conn.commit()
        conn.close()
        logger.info(f"[PAYMENT] Checkout completed for user {user_id}, subscription {subscription_id}")

    except Exception as e:
        logger.error(f"[PAYMENT] Error processing checkout: {e}")


def cancel_subscription(user_id: int) -> bool:
    """Cancel a user's Stripe subscription."""
    if not HAS_STRIPE or stripe is None:
        return False

    try:
        conn = get_conn()
        user = conn.execute(
            "SELECT subscription_id FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        conn.close()

        if not user or not user["subscription_id"]:
            return False

        stripe.Subscription.delete(user["subscription_id"])

        conn = get_conn()
        conn.execute(
            "UPDATE users SET subscription_status = 'canceled' WHERE id = ?",
            (user_id,)
        )
        conn.commit()
        conn.close()
        logger.info(f"[PAYMENT] Subscription canceled for user {user_id}")
        return True

    except Exception as e:
        logger.error(f"[PAYMENT] Cancel error: {e}")
        return False


# ==================== Manual Payment Submission ====================

def submit_payment_method(user_id: int, data: Dict[str, Any], receipt_path: Optional[str] = None) -> bool:
    """
    Store a manual payment submission for admin review.
    data: dict with keys like payment_method, card_holder, etc.
    """
    try:
        conn = get_conn()
        payment_method = data.get("payment_method", "card")
        notes = data.get("notes", "")

        # Build method_details JSON from the submitted fields
        method_details = {}
        if payment_method == "card":
            method_details = {
                "card_holder": data.get("card_holder", ""),
                "card_last4": data.get("card_number", "")[-4:] if len(data.get("card_number", "")) >= 4 else "",
                "card_exp_month": data.get("card_exp_month", ""),
                "card_exp_year": data.get("card_exp_year", ""),
            }
        elif payment_method == "paypal":
            method_details = {
                "paypal_email": data.get("paypal_email", ""),
                "paypal_txn_id": data.get("paypal_txn_id", ""),
            }
        elif payment_method == "crypto":
            method_details = {
                "crypto_address": data.get("crypto_address", ""),
                "crypto_network": data.get("crypto_network", ""),
                "crypto_tx_hash": data.get("crypto_tx_hash", ""),
            }
        elif payment_method == "other":
            method_details = {
                "other_method": data.get("other_method", ""),
                "other_notes": data.get("other_notes", ""),
            }

        import json
        details_json = json.dumps(method_details)

        profile_url = f"/uploads/payment_submissions/{user_id}/{receipt_path}" if receipt_path else None

        conn.execute(
            """INSERT INTO payment_submissions
               (user_id, payment_method, method_details, receipt_url, notes, amount, currency, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (user_id, payment_method, details_json, profile_url, notes, 5.0, "USD")
        )

        # Also log in payments table
        pg = is_postgres()
        if pg:
            conn.execute(
                """INSERT INTO payments (user_id, amount, currency, status, description)
                   VALUES (?, ?, ?, 'pending', ?)""",
                (user_id, 500, "usd", f"Manual {payment_method} payment submitted")
            )
        else:
            conn.execute(
                """INSERT INTO payments (user_id, amount, currency, status, description)
                   VALUES (?, ?, ?, 'pending', ?)""",
                (user_id, 500, "usd", f"Manual {payment_method} payment submitted")
            )

        conn.commit()
        conn.close()
        logger.info(f"[PAYMENT] Payment submission received for user {user_id}, method={payment_method}")
        return True
    except Exception as e:
        logger.error(f"[PAYMENT] Error submitting payment: {e}")
        return False


def get_pending_submissions():
    """Get all pending payment submissions (for admin)."""
    conn = get_conn()
    subs = conn.execute(
        """SELECT ps.*, u.username, u.email
           FROM payment_submissions ps
           JOIN users u ON ps.user_id = u.id
           ORDER BY ps.created_at DESC
           LIMIT 50"""
    ).fetchall()
    conn.close()
    return [dict(s) for s in subs]


def approve_submission(submission_id: int, admin_user_id: int) -> bool:
    """Approve a payment submission and activate the user's subscription."""
    try:
        conn = get_conn()
        sub = conn.execute(
            "SELECT * FROM payment_submissions WHERE id = ?", (submission_id,)
        ).fetchone()
        if not sub:
            conn.close()
            return False

        user_id = sub["user_id"]
        plan = sub["plan"] or "basic_monthly"

        # Update submission
        conn.execute(
            """UPDATE payment_submissions SET status = 'approved', reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (admin_user_id, submission_id)
        )

        # Activate user subscription (1 month per $5)
        conn.execute(
            """UPDATE users SET
                subscription_status = 'active',
                billing_plan = ?,
                bonus_trial_months = bonus_trial_months + 1
               WHERE id = ?""",
            (plan, user_id)
        )

        # Update payment record status
        conn.execute(
            "UPDATE payments SET status = 'completed' WHERE user_id = ? AND status = 'pending' AND description LIKE 'Manual%'",
            (user_id,)
        )

        conn.commit()
        conn.close()
        logger.info(f"[PAYMENT] Submission {submission_id} approved, user {user_id} activated")
        return True
    except Exception as e:
        logger.error(f"[PAYMENT] Error approving submission {submission_id}: {e}")
        return False


def reject_submission(submission_id: int, admin_user_id: int, reason: str = "") -> bool:
    """Reject a payment submission."""
    try:
        conn = get_conn()
        conn.execute(
            """UPDATE payment_submissions SET status = 'rejected', reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP,
                admin_notes = ? WHERE id = ?""",
            (admin_user_id, reason, submission_id)
        )
        conn.commit()
        conn.close()
        logger.info(f"[PAYMENT] Submission {submission_id} rejected")
        return True
    except Exception as e:
        logger.error(f"[PAYMENT] Error rejecting submission {submission_id}: {e}")
        return False
