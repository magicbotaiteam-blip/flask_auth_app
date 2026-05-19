# Google OAuth Setup for Magic Bot AI

## Current Status
✅ **Flask-Dance is installed** (Google OAuth library)
❌ **Google OAuth credentials NOT configured**
⚠️ **Google buttons removed from templates** (to avoid confusion)

## To Enable Google OAuth:

### Step 1: Get Google OAuth Credentials

1. **Go to** [Google Cloud Console](https://console.cloud.google.com/)
2. **Create a new project** or select existing
3. **Enable APIs & Services** → **Library**
4. **Search for** "Google+ API" and enable it
5. **Go to** Credentials → Create Credentials → OAuth 2.0 Client ID
6. **Application type:** Web application
7. **Name:** Magic Bot AI
8. **Authorized redirect URIs:**
   ```
   http://localhost:5000/login/google/authorized
   http://127.0.0.1:5000/login/google/authorized
   ```
9. **Click Create** and copy:
   - **Client ID**
   - **Client Secret**

### Step 2: Configure Credentials

**Option A: Environment Variables** (Recommended)
```bash
export GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com"
export GOOGLE_CLIENT_SECRET="your-client-secret"
```

**Option B: Direct in Code** (Not recommended for production)
Edit `app_complete_with_groups.py` lines 45-46:
```python
google_client_id = "your-client-id.apps.googleusercontent.com"
google_client_secret = "your-client-secret"
```

### Step 3: Restart the Application
```bash
python app_complete_with_groups.py
```

### Step 4: Restore Google Buttons (Optional)
If you want Google buttons in templates, run:
```bash
python restore_google_buttons.py
```

## Testing Google OAuth

1. **Start the app** with credentials configured
2. **Check console output:** Should show "✅ Google OAuth configured"
3. **Go to** `/login/google` - Should redirect to Google login
4. **After login** - Should redirect to index/dashboard

## Troubleshooting

### Common Issues:

1. **"Invalid redirect_uri"**
   - Check authorized redirect URIs in Google Cloud Console
   - Must match exactly: `http://localhost:5000/login/google/authorized`

2. **"Client ID not found"**
   - Verify Client ID is correct
   - Check if Google+ API is enabled

3. **"Scope not authorized"**
   - Make sure scopes are properly requested
   - Check Google Cloud Console → OAuth consent screen

4. **Flask-Dance errors**
   - Reinstall: `pip install flask-dance`
   - Check imports in app_complete_with_groups.py

## Security Notes

1. **Never commit credentials** to version control
2. **Use environment variables** in production
3. **Restrict redirect URIs** to your domains
4. **Regularly rotate** Client Secrets
5. **Monitor usage** in Google Cloud Console

## Development vs Production

### Development (localhost):
```
Authorized redirect URIs:
http://localhost:5000/login/google/authorized
http://127.0.0.1:5000/login/google/authorized
```

### Production (yourdomain.com):
```
Authorized redirect URIs:
https://yourdomain.com/login/google/authorized
```

## Complete Working Example

Once configured, Google OAuth will:
1. Show Google buttons on login/signup pages
2. Redirect to Google for authentication
3. Create user account in database
4. Log user in automatically
5. Handle sessions and logout

## Need Help?

1. Check Flask-Dance documentation: https://flask-dance.readthedocs.io/
2. Google OAuth documentation: https://developers.google.com/identity/protocols/oauth2
3. Magic Bot AI issues on GitHub

Google OAuth is now ready to be configured! 🚀