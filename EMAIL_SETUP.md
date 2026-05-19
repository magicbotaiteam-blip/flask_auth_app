# Email Configuration for Magic Bot AI

The group invitation system now supports sending actual invitation emails to users. This document explains how to configure it.

## Current Status

✅ **Group invitation system FIXED** for new users (seamless signup + auto-join)
✅ **Email system IMPLEMENTED** (sends invitation emails)
⚠️ **Email configuration REQUIRED** (needs SMTP settings)

## How It Works

### Without Email Configuration:
- Invitations are created in the database
- System shows invitation link to the inviter
- Inviter must manually share the link (Slack, chat, etc.)
- New users can click link → sign up → auto-join group

### With Email Configuration:
- Invitations are created in the database
- System automatically sends invitation email
- Email includes beautiful HTML template with accept button
- System also shows invitation link to inviter (for backup)
- New users receive email → click link → sign up → auto-join group

## Email Configuration

### Option 1: Gmail (Recommended for Testing)

1. **Enable 2-Factor Authentication** on your Google account
2. **Generate an App Password**:
   - Go to [Google App Passwords](https://myaccount.google.com/apppasswords)
   - Select "Mail" as app
   - Select your device
   - Copy the 16-character password

3. **Set Environment Variables**:
```bash
# For Gmail
export SMTP_HOST='smtp.gmail.com'
export SMTP_PORT='587'
export SMTP_USERNAME='your-email@gmail.com'
export SMTP_PASSWORD='your-16-character-app-password'
export FROM_EMAIL='noreply@yourdomain.com'  # or use your Gmail address
```

### Option 2: Other SMTP Services

**SendGrid:**
```bash
export SMTP_HOST='smtp.sendgrid.net'
export SMTP_PORT='587'
export SMTP_USERNAME='apikey'
export SMTP_PASSWORD='your-sendgrid-api-key'
export FROM_EMAIL='noreply@yourdomain.com'
```

**Mailgun:**
```bash
export SMTP_HOST='smtp.mailgun.org'
export SMTP_PORT='587'
export SMTP_USERNAME='postmaster@yourdomain.mailgun.org'
export SMTP_PASSWORD='your-mailgun-password'
export FROM_EMAIL='noreply@yourdomain.com'
```

**AWS SES:**
```bash
export SMTP_HOST='email-smtp.us-east-1.amazonaws.com'
export SMTP_PORT='587'
export SMTP_USERNAME='your-ses-smtp-username'
export SMTP_PASSWORD='your-ses-smtp-password'
export FROM_EMAIL='noreply@yourdomain.com'
```

## Testing Email Configuration

Run the test script to verify your setup:
```bash
python test_email_system.py
```

Or test directly in the app:
1. Go to a group → Members → Invite Someone
2. Enter email address
3. If configured: "Invitation email sent to [email]"
4. If not configured: "Invitation created... share this link manually: [link]"

## Files Modified

### 1. `email_utils.py` (NEW)
- Email sending utilities
- HTML email templates
- SMTP configuration handling
- Graceful fallback when not configured

### 2. `group_collaboration_ui_part2.py`
- Modified `invite_to_group()` function
- Added email sending after invitation creation
- Shows invitation link regardless of email configuration
- Better error handling and user feedback

### 3. `app_complete_with_groups.py`
- Enhanced signup flow for new users with invitations
- Auto-accepts invitations after signup
- Redirects to group dashboard

### 4. `templates/signup_local.html`
- Shows invitation context during signup
- Informs user which group they're joining

## Email Template Features

The invitation email includes:
- **Beautiful HTML design** with gradient header
- **Group name** and **inviter name**
- **Role** (member, admin, viewer)
- **Accept button** with direct link
- **Plain text fallback** for email clients
- **Expiration notice** (7 days)
- **Instructions** for new users
- **Responsive design** for mobile devices

## Troubleshooting

### Emails not sending:
1. Check environment variables are set
2. Verify SMTP credentials are correct
3. Check firewall/port restrictions
4. Look for error messages in console

### Gmail specific issues:
1. Enable "Less secure app access" (deprecated, use App Passwords instead)
2. Check if 2FA is enabled
3. Verify App Password was generated for "Mail" app

### Development/testing:
- Without email config: Links are shown for manual sharing
- Test with [Mailtrap](https://mailtrap.io/) for development
- Use [Ethereal Email](https://ethereal.email/) for testing

## Security Considerations

1. **Never commit credentials** to version control
2. **Use environment variables** for configuration
3. **App Passwords** for Gmail (not your main password)
4. **Rate limiting** - be mindful of sending limits
5. **SPF/DKIM/DMARC** - configure for production domains

## Future Enhancements

Potential improvements:
1. Email templates for different languages
2. Email tracking (opened, clicked)
3. Reminder emails before expiration
4. Welcome emails for new users
5. Email preferences/unsubscribe
6. Queue system for bulk invitations

## Quick Start for Development

For quick testing without email:
```bash
# No configuration needed
# System will show invitation links
# Manually share links with test users
```

For testing with email:
```bash
# Set up Mailtrap (free for development)
export SMTP_HOST='smtp.mailtrap.io'
export SMTP_PORT='2525'
export SMTP_USERNAME='your-mailtrap-username'
export SMTP_PASSWORD='your-mailtrap-password'
export FROM_EMAIL='test@openclaw.ai'
```

The email system is now fully integrated and ready for use! 🚀📧