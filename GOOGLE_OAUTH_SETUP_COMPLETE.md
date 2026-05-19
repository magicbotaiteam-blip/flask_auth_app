# Complete Google OAuth Setup Guide

## ✅ Google OAuth Has Been Restored!

The Google OAuth functionality has been successfully restored to your authentication system. Here's what has been done:

### **What's Been Fixed:**
1. ✅ Google OAuth buttons restored in all templates
2. ✅ Correct endpoint names (`google.login` with dot, not `google_login`)
3. ✅ Full Flask-Dance implementation in `app.py`
4. ✅ All templates updated to work with original `app.py`

## **🚀 How to Use Google OAuth:**

### **Step 1: Get Google OAuth Credentials**

1. **Go to Google Cloud Console:**
   - https://console.cloud.google.com/

2. **Create or select a project:**
   - Click project dropdown → "New Project" or select existing

3. **Enable OAuth Consent Screen:**
   - Go to "APIs & Services" → "OAuth consent screen"
   - Choose "External" (for testing) or "Internal" (for G Suite)
   - Fill in required fields (App name, support email, etc.)
   - Add scopes: `.../auth/userinfo.email`, `.../auth/userinfo.profile`, `openid`
   - Add test users (your email addresses)

4. **Create OAuth 2.0 Credentials:**
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth 2.0 Client ID"
   - Choose "Web application"
   - Name: "Magic Bot AI Local"
   - **Authorized redirect URIs (CRITICAL):**
     ```
     http://localhost:5000/login/google/authorized
     http://127.0.0.1:5000/login/google/authorized
     ```
   - Click "Create"
   - Copy your **Client ID** and **Client Secret**

### **Step 2: Set Environment Variables**

#### **Option A: One-time (current terminal session):**
```bash
export GOOGLE_CLIENT_ID='your-actual-client-id-here'
export GOOGLE_CLIENT_SECRET='your-actual-client-secret-here'
export OAUTHLIB_INSECURE_TRANSPORT='true'
```

#### **Option B: Permanent (.env file):**
```bash
# Create .env file
cat > .env << EOF
GOOGLE_CLIENT_ID=your-actual-client-id-here
GOOGLE_CLIENT_SECRET=your-actual-client-secret-here
OAUTHLIB_INSECURE_TRANSPORT=true
FLASK_SECRET_KEY=dev-secret-key-change-in-production
EOF

# Load .env file
export $(grep -v '^#' .env | xargs)
```

#### **Option C: For production (systemd/service):**
Add to your service file:
```
Environment="GOOGLE_CLIENT_ID=your-id"
Environment="GOOGLE_CLIENT_SECRET=your-secret"
Environment="OAUTHLIB_INSECURE_TRANSPORT=false"  # Use HTTPS in production
```

### **Step 3: Start the Application**

```bash
cd /Users/siyang/flask_auth_app

# Activate virtual environment
source venv/bin/activate

# Start with original app.py (has Flask-Dance)
python app.py
```

### **Step 4: Test Google OAuth**

1. **Open browser:** `http://localhost:5000`
2. **Click:** "Sign in with Google"
3. **You should be redirected** to Google's OAuth page
4. **Sign in** with your Google account
5. **Grant permissions** to the app
6. **You should be redirected back** to your dashboard

## **🔧 Troubleshooting:**

### **Common Issues & Solutions:**

#### **1. "Invalid redirect_uri" error**
- **Cause:** Redirect URI not configured in Google Cloud Console
- **Fix:** Add both URIs to Google Cloud Console:
  - `http://localhost:5000/login/google/authorized`
  - `http://127.0.0.1:5000/login/google/authorized`

#### **2. "Client ID not found" error**
- **Cause:** Wrong Client ID or environment variable not set
- **Fix:** Verify Client ID and set environment variables correctly

#### **3. "This app isn't verified" warning**
- **Cause:** App is in testing mode
- **Fix:** Add your email as a test user in OAuth consent screen

#### **4. Template errors with "google.login"**
- **Cause:** Wrong endpoint name in templates
- **Fix:** All templates now use `url_for('google.login')` (correct)

#### **5. Port 5000 already in use**
- **Cause:** Another app using port 5000
- **Fix:** Change port in `app.py` or kill existing process

## **📁 File Structure:**

```
flask_auth_app/
├── app.py                    # Original app with Flask-Dance Google OAuth
├── app_clean.py              # Clean version (simplified, no Google OAuth)
├── templates/
│   ├── landing.html          # Has Google OAuth button
│   ├── signin_local.html     # Has Google OAuth button
│   ├── signup_local.html     # Has Google OAuth button
│   └── landing_simple.html   # Simple version (no Google OAuth)
├── users.db                  # Database
├── .env.example              # Environment variables template
└── GOOGLE_OAUTH_SETUP.md     # Original setup guide
```

## **⚡ Quick Start Commands:**

```bash
# 1. Set environment variables
export GOOGLE_CLIENT_ID='your-id'
export GOOGLE_CLIENT_SECRET='your-secret'
export OAUTHLIB_INSECURE_TRANSPORT='true'

# 2. Start the app
cd /Users/siyang/flask_auth_app
source venv/bin/activate
python app.py

# 3. Open in browser
open http://localhost:5000
```

## **🔒 Security Notes:**

1. **Never commit** `.env` file or credentials to git
2. **Use HTTPS** in production (set `OAUTHLIB_INSECURE_TRANSPORT=false`)
3. **Change Flask secret key** in production
4. **Use environment variables** not hardcoded credentials
5. **Regularly rotate** OAuth credentials

## **📞 Need Help?**

If you encounter issues:

1. Check Google Cloud Console configuration
2. Verify environment variables are set
3. Check application logs for errors
4. Ensure port 5000 is available
5. Test with different Google account

---

**✅ Google OAuth is now fully restored and ready for configuration!**