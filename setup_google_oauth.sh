#!/bin/bash

echo "========================================="
echo "Google OAuth Setup Helper"
echo "========================================="

# Check current environment variables
echo "Current Google OAuth configuration:"
echo "-----------------------------------------"

if [ -z "$GOOGLE_CLIENT_ID" ] || [ "$GOOGLE_CLIENT_ID" = "your-google-client-id" ]; then
    echo "❌ GOOGLE_CLIENT_ID is not set or is using default value"
else
    echo "✅ GOOGLE_CLIENT_ID is set: ${GOOGLE_CLIENT_ID:0:20}..."
fi

if [ -z "$GOOGLE_CLIENT_SECRET" ] || [ "$GOOGLE_CLIENT_SECRET" = "your-google-client-secret" ]; then
    echo "❌ GOOGLE_CLIENT_SECRET is not set or is using default value"
else
    echo "✅ GOOGLE_CLIENT_SECRET is set: ${GOOGLE_CLIENT_SECRET:0:20}..."
fi

echo ""
echo "========================================="
echo "Setup Instructions"
echo "========================================="

echo ""
echo "1. Get Google OAuth Credentials:"
echo "   - Go to: https://console.cloud.google.com/"
echo "   - Create a project or select existing"
echo "   - Go to 'APIs & Services' → 'Credentials'"
echo "   - Click 'Create Credentials' → 'OAuth 2.0 Client ID'"
echo "   - Choose 'Web application'"
echo ""
echo "2. Configure Authorized Redirect URIs:"
echo "   Add these URIs in Google Cloud Console:"
echo "   - http://localhost:5000/login/google/authorized"
echo "   - http://127.0.0.1:5000/login/google/authorized"
echo ""
echo "3. Set Environment Variables:"
echo ""
echo "   Option A: One-time export (for current terminal session):"
echo "   export GOOGLE_CLIENT_ID='your-actual-client-id'"
echo "   export GOOGLE_CLIENT_SECRET='your-actual-client-secret'"
echo "   export OAUTHLIB_INSECURE_TRANSPORT='true'"
echo ""
echo "   Option B: Create .env file (permanent):"
echo "   Create a file named '.env' in the current directory with:"
echo "   GOOGLE_CLIENT_ID=your-actual-client-id"
echo "   GOOGLE_CLIENT_SECRET=your-actual-client-secret"
echo "   OAUTHLIB_INSECURE_TRANSPORT=true"
echo ""
echo "4. Start the application:"
echo "   source venv/bin/activate"
echo "   python app.py"
echo ""
echo "5. Test Google OAuth:"
echo "   - Open: http://localhost:5000"
echo "   - Click 'Sign in with Google'"
echo "   - You should be redirected to Google's login page"
echo ""
echo "========================================="
echo "Quick Test"
echo "========================================="
echo ""
echo "To test if environment variables are set correctly:"
echo "python3 -c \"import os; print('GOOGLE_CLIENT_ID:', os.environ.get('GOOGLE_CLIENT_ID', 'NOT SET')); print('GOOGLE_CLIENT_SECRET:', 'SET' if os.environ.get('GOOGLE_CLIENT_SECRET') and os.environ.get('GOOGLE_CLIENT_SECRET') != 'your-google-client-secret' else 'NOT SET')\""
echo ""
echo "========================================="