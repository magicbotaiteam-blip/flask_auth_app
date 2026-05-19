# Magic Bot AI - Flask Authentication App

A Flask web application with Google OAuth 2.0 authentication and bot management system.

## Features

- **Google OAuth 2.0 Authentication**: Secure login with Google accounts
- **User Management**: Automatic user registration on first login
- **Bots Management**: Create, read, update, and delete AI bots
- **Responsive UI**: Modern, AI-themed interface with Bootstrap 5
- **Database**: SQLite with user-bot associations

## New Bots Management Features

### 1. **User-Bot Association**
- Each bot is associated with the user who created it
- Users can only see and manage their own bots
- Secure database relationships with foreign keys

### 2. **My Bots Page** (`/my-bots`)
- Lists all bots created by the current user
- Shows bot details: name, email, organization, messaging apps
- Provides edit and delete actions for each bot
- Empty state with call-to-action for first-time users

### 3. **Bot Registration/Edit Page** (`/register-bot`)
- Single page for both creating new bots and editing existing ones
- Form validation with required fields
- Delete functionality with confirmation
- Backend storage (replaces localStorage)

### 4. **Navigation Integration**
- "My bots" link in the AI dropdown menu
- Consistent navigation across all pages
- Fixed dropdown hover issues

## Database Schema

### Users Table
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    provider_id TEXT NOT NULL UNIQUE,
    username TEXT NOT NULL,
    email TEXT
);
```

### Bots Table
```sql
CREATE TABLE bots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    email TEXT,
    organization TEXT,
    messaging TEXT,
    token TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);
```

## Installation

1. **Clone and setup virtual environment:**
```bash
cd flask_auth_app
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Set up Google OAuth credentials:**
   - Create a project in Google Cloud Console
   - Enable Google+ API
   - Create OAuth 2.0 credentials
   - Add authorized redirect URI: `http://localhost:5000/login/google/authorized`

3. **Set environment variables:**
```bash
export GOOGLE_CLIENT_ID="your-client-id"
export GOOGLE_CLIENT_SECRET="your-client-secret"
```

4. **Run the application:**
```bash
python app.py
```

5. **Access the application:** `http://localhost:5000`

## Routes

- `/` - Dashboard (requires authentication)
- `/landing` - Landing page (public)
- `/signin` - Redirect to Google OAuth
- `/my-bots` - List user's bots (requires authentication)
- `/register-bot` - Create new bot (requires authentication)
- `/register-bot/<bot_id>` - Edit existing bot (requires authentication)
- `/bot/save` - Save bot data (POST, requires authentication)
- `/bot/delete/<bot_id>` - Delete bot (requires authentication)
- `/logout` - Logout and clear session

## Security Features

- **OAuth 2.0**: No password storage
- **Session Management**: Flask sessions with secret key
- **User Isolation**: Users can only access their own bots
- **CSRF Protection**: Form submissions require authentication
- **Input Validation**: Required fields and data sanitization

## UI Improvements

- **Fixed Dropdown Menus**: No more disappearing hover issues
- **Consistent Design**: Same navigation across all pages
- **Responsive Layout**: Works on mobile and desktop
- **Empty States**: Helpful messages for first-time users
- **Flash Messages**: User feedback for actions

## Testing

1. **Sign in with Google**
2. **Navigate to "My bots"** from the AI dropdown menu
3. **Create a new bot** using "Register New Bot"
4. **Edit an existing bot** by clicking "Edit"
5. **Delete a bot** with confirmation
6. **Verify user isolation** by checking database

## Future Enhancements

1. **Bot API Integration**: Connect to actual bot services
2. **Bot Analytics**: Usage statistics and monitoring
3. **Team Collaboration**: Share bots with team members
4. **Export/Import**: Backup and restore bot configurations
5. **Advanced Search**: Filter and search through bots
6. **Bot Templates**: Pre-configured bot setups

## Troubleshooting

### Common Issues:

1. **Google OAuth not working:**
   - Check environment variables
   - Verify redirect URI in Google Cloud Console
   - Ensure `OAUTHLIB_INSECURE_TRANSPORT` is set for local development

2. **Database issues:**
   - Check `users.db` file permissions
   - Verify table creation on startup
   - Check foreign key constraints

3. **Dropdown menu issues:**
   - JavaScript console for errors
   - CSS conflicts with Bootstrap
   - Hover delay timing

### Logs:
- Check Flask debug output in terminal
- Review browser console for JavaScript errors
- Examine database with SQLite browser

## License

MIT License - See LICENSE file for details.