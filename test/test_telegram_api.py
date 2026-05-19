#!/usr/bin/env python3
"""
Test the Telegram Bot API endpoints
"""

import requests
import json
import sys

BASE_URL = "http://localhost:5000"

def test_api():
    print("Testing Telegram Bot API")
    print("=" * 60)
    
    # Note: This test requires an active Flask app and logged in user
    # You need to:
    # 1. Start the Flask app: python app_with_telegram_api.py
    # 2. Login via web interface
    # 3. Get your session cookie
    # 4. Update the SESSION_COOKIE below
    
    SESSION_COOKIE = "YOUR_SESSION_COOKIE_HERE"  # Get from browser after login
    
    headers = {
        "Content-Type": "application/json",
        "Cookie": f"session={SESSION_COOKIE}"
    }
    
    print("\n1. Testing API endpoints (will fail without valid session)...")
    
    endpoints = [
        ("GET", "/api/telegram/bot/templates", None),
        ("POST", "/api/telegram/bot/create", {
            "name": "Test Bot",
            "token": "YOUR_BOT_TOKEN_HERE",
            "description": "Test bot created via API"
        }),
    ]
    
    for method, endpoint, data in endpoints:
        print(f"\n{method} {endpoint}")
        print("-" * 40)
        
        try:
            if method == "GET":
                response = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
            elif method == "POST":
                response = requests.post(f"{BASE_URL}{endpoint}", 
                                       headers=headers, 
                                       json=data)
            
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"Success: {result.get('success', False)}")
                if result.get('success'):
                    print("✅ API call successful!")
                else:
                    print(f"Error: {result.get('error', 'Unknown error')}")
            elif response.status_code == 401:
                print("❌ Authentication required - need valid session cookie")
            else:
                print(f"Response: {response.text[:200]}...")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")
    
    print("\n" + "=" * 60)
    print("API Documentation:")
    print("=" * 60)
    
    print("\nAvailable endpoints:")
    print("1. Create bot: POST /api/telegram/bot/create")
    print("2. Get bot: GET /api/telegram/bot/{id}")
    print("3. Update bot: PUT /api/telegram/bot/{id}/update")
    print("4. Test bot: POST /api/telegram/bot/{id}/test")
    print("5. Send message: POST /api/telegram/bot/{id}/send")
    print("6. Get updates: GET /api/telegram/bot/{id}/updates")
    print("7. Manage webhook: POST/DELETE /api/telegram/bot/{id}/webhook")
    print("8. Get analytics: GET /api/telegram/bot/{id}/analytics")
    print("9. Manage templates: GET/POST /api/telegram/bot/templates")
    
    print("\n" + "=" * 60)
    print("To use the API:")
    print("1. Start Flask app: python app_with_telegram_api.py")
    print("2. Login via http://localhost:5000")
    print("3. Get session cookie from browser")
    print("4. Update SESSION_COOKIE in this script")
    print("5. Run: python test_telegram_api.py")
    print("=" * 60)

def quick_curl_examples():
    print("\n" + "=" * 60)
    print("Quick curl examples (replace SESSION_COOKIE):")
    print("=" * 60)
    
    examples = [
        ("Create bot", """
curl -X POST http://localhost:5000/api/telegram/bot/create \\
  -H "Content-Type: application/json" \\
  -H "Cookie: session=YOUR_SESSION_COOKIE" \\
  -d '{
    "name": "My Bot",
    "token": "YOUR_BOT_TOKEN",
    "description": "My first bot"
  }'
        """),
        
        ("Send message", """
curl -X POST http://localhost:5000/api/telegram/bot/1/send \\
  -H "Content-Type: application/json" \\
  -H "Cookie: session=YOUR_SESSION_COOKIE" \\
  -d '{
    "chat_id": "123456789",
    "message": "Hello from API!",
    "parse_mode": "HTML"
  }'
        """),
        
        ("Get analytics", """
curl -X GET "http://localhost:5000/api/telegram/bot/1/analytics?days=7" \\
  -H "Cookie: session=YOUR_SESSION_COOKIE"
        """)
    ]
    
    for title, example in examples:
        print(f"\n{title}:")
        print(example)
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    test_api()
    quick_curl_examples()