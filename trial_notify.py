"""
Standalone script: Check all users nearing trial end and log notifications.
Can be run as a cron job.
"""

import sys
import os
import json
from datetime import datetime

# Add current dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trial import get_users_near_trial_end, get_trial_info
from db import get_conn

LOG_FILE = "/tmp/trial_notify.log"
THRESHOLD_DAYS = 15


def log_notification(user_id, username, email, days_remaining):
    """Log a notification event (future: could also send email here)."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "username": username,
        "email": email,
        "days_remaining": days_remaining,
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"[TRIAL NOTIFY] User {username} ({email}): {days_remaining} days remaining — notification logged")


def main():
    print(f"=== Trial Notification Check ({datetime.now().isoformat()}) ===")

    users = get_users_near_trial_end(THRESHOLD_DAYS)

    if not users:
        print("No users nearing trial end. All clear!")
        return

    print(f"Found {len(users)} users with ≤{THRESHOLD_DAYS} trial days remaining:\n")

    # Log notification for each user in the threshold
    for u in users:
        log_notification(
            u["user_id"],
            u["username"],
            u["email"],
            u["days_remaining"],
        )

    print(f"\nDone. Notifications logged to {LOG_FILE}")


if __name__ == "__main__":
    main()
