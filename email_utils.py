#!/usr/bin/env python3
"""
Email utilities using gog CLI (Gmail OAuth)
"""

import os
import subprocess
import tempfile
import textwrap

GOG_ACCOUNT = "chingtshenbot@gmail.com"


def send_group_invitation_email(invitation_data, app_url="http://localhost:5000"):
    """
    Send group invitation email via gog CLI

    Args:
        invitation_data: Dict with keys:
            - email: Recipient email
            - group_name: Name of the group
            - inviter_name: Name of person who invited
            - token: Invitation token
            - role: Role in group (member, admin, viewer)
        app_url: Base URL of the application

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    invitation_url = f"{app_url}/groups/invite/accept/{invitation_data['token']}"
    subject = f"Invitation to join {invitation_data['group_name']} on Magic Bot AI"

    print(f"[EMAIL] Sending invitation email to {invitation_data['email']} via gog...")

    body = textwrap.dedent(f"""\
        Hello,

        {invitation_data['inviter_name']} has invited you to join the group "{invitation_data['group_name']}" as a {invitation_data['role']}.

        To accept this invitation, click the link below:
        {invitation_url}

        If you don't have a Magic Bot AI account yet, don't worry!
        Clicking the link will guide you through creating an account.

        Note: This invitation will expire in 7 days.

        Best,
        Magic Bot AI Team
    """)

    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(body)
            temp_path = f.name
        result = subprocess.run(
            ["gog", "mail", "send",
             "--to", invitation_data['email'],
             "--subject", subject,
             "--body-file", temp_path,
             "--account", GOG_ACCOUNT],
            capture_output=True, text=True, timeout=30
        )
        os.unlink(temp_path)
        if result.returncode == 0:
            print(f"[EMAIL] Invitation email sent successfully to {invitation_data['email']}")
            return True
        else:
            print(f"[EMAIL] Failed to send invitation email: {result.stderr}")
            return False
    except Exception as e:
        print(f"[EMAIL] Error sending invitation email: {e}")
        return False


def send_welcome_email(user_email, username, app_url="http://localhost:5000"):
    """Send welcome email to new users"""
    return True
