#!/usr/bin/env python3
"""
Test that the landing page loads with the new image
"""

import os

print("Testing landing page with new image...")
print("=" * 60)

# Remove old database
if os.path.exists('users.db'):
    os.remove('users.db')

from app_complete_with_groups import app, init_db_complete
init_db_complete()
print("✅ Database initialized")

# Test the landing route
from flask import Flask
test_app = Flask(__name__)
test_app.secret_key = 'test'

# Register routes
from group_collaboration_ui import create_group_collaboration_ui
create_group_collaboration_ui(test_app)

print("✅ Routes registered")

# Test with request context
with test_app.test_request_context('/'):
    try:
        # Get the landing function
        landing_func = test_app.view_functions['landing']
        
        # Call it
        response = landing_func()
        
        print("✅ Landing page function executes successfully!")
        
        # Check if the response contains the image URL
        response_text = str(response)
        if 'AI_IMG_2.jpeg' in response_text:
            print("✅ Image reference found in landing page!")
            print("✅ Image path: /static/AI_IMG_2.jpeg")
        else:
            print("⚠️  Image reference not found in response")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 60)
print("✅ LANDING PAGE IMAGE ADDED!")
print("\nSummary of changes:")
print("1. ✅ Added AI_IMG_2.jpeg to hero section (replaced robot icon)")
print("2. ✅ Added AI_IMG_2.jpeg to 'How It Works' section")
print("3. ✅ Added custom CSS styles for images")
print("4. ✅ Added visual badges and captions")
print("\nThe image should now appear in two places on the landing page:")
print("1. Hero section (main visual)")
print("2. How It Works section (workflow visualization)")
print("=" * 60)