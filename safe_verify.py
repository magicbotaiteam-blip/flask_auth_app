#!/usr/bin/env python3
"""
SAFE Telegram Verification - No API Calls
Absolutely safe to run while OpenClaw agent is active
"""

import os
import json
import sqlite3
from datetime import datetime

def safe_check():
    """Perform safe checks without API calls"""
    print("=" * 60)
    print("SAFE TELEGRAM VERIFICATION")
    print("(No API calls - safe with OpenClaw)")
    print("=" * 60)
    
    # 1. Check database
    print("\n1. DATABASE CHECK:")
    if os.path.exists('users.db'):
        print("   ✅ Database exists")
        
        try:
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            
            # Check bots table
            cursor.execute("SELECT COUNT(*) FROM bots WHERE token IS NOT NULL")
            bot_count = cursor.fetchone()[0]
            print(f"   ✅ Found {bot_count} bot(s) in database")
            
            # Get bot info (without token details)
            cursor.execute("SELECT name, messaging FROM bots LIMIT 1")
            bot = cursor.fetchone()
            if bot:
                print(f"   ✅ Bot name: {bot[0]}")
                print(f"   ✅ Messaging: {bot[1]}")
            
            # Check for webhook configuration
            cursor.execute("SELECT COUNT(*) FROM bots WHERE webhook_url IS NOT NULL AND webhook_url != ''")
            webhook_count = cursor.fetchone()[0]
            print(f"   ✅ {webhook_count} bot(s) with webhook configured")
            
            conn.close()
        except Exception as e:
            print(f"   ⚠️  Database error: {e}")
    else:
        print("   ❌ Database not found")
    
    # 2. Check configuration files
    print("\n2. CONFIGURATION FILES:")
    config_files = [
        'app.py',
        'app_with_telegram_api.py', 
        'telegram_bot_api.py',
        'bot_services.py'
    ]
    
    for file in config_files:
        if os.path.exists(file):
            size = os.path.getsize(file)
            print(f"   ✅ {file} ({size} bytes)")
        else:
            print(f"   ⚠️  {file} (not found)")
    
    # 3. Check for webhook endpoints in Flask app
    print("\n3. WEBHOOK ENDPOINT CHECK:")
    flask_files = ['app.py', 'app_with_telegram_api.py']
    webhook_found = False
    
    for file in flask_files:
        if os.path.exists(file):
            try:
                with open(file, 'r') as f:
                    content = f.read()
                    if 'webhook' in content.lower():
                        print(f"   ✅ {file} contains webhook code")
                        webhook_found = True
                    else:
                        print(f"   ⚠️  {file} has no webhook code")
            except:
                print(f"   ❌ Could not read {file}")
    
    # 4. Verification steps
    print("\n4. VERIFICATION STEPS (manual):")
    steps = [
        "Send message to your bot (@nb_openclaw_ssy_bot)",
        "Watch OpenClaw agent console/output",
        "Look for 'Received message' or similar output",
        "Check if bot replies (if auto-reply configured)",
        "Verify in OpenClaw logs if available"
    ]
    
    for i, step in enumerate(steps, 1):
        print(f"   {i}. {step}")
    
    # 5. Test message suggestions
    print("\n5. TEST MESSAGE SUGGESTIONS:")
    test_messages = [
        "Hello",
        "Test",
        "/start",
        "How are you?",
        f"Test at {datetime.now().strftime('%H:%M:%S')}"
    ]
    
    print("   Send these exact messages:")
    for msg in test_messages:
        print(f"   • \"{msg}\"")
    
    # 6. Create verification report
    print("\n6. VERIFICATION REPORT:")
    report = {
        "timestamp": datetime.now().isoformat(),
        "database_exists": os.path.exists('users.db'),
        "bot_count": bot_count if 'bot_count' in locals() else 0,
        "webhook_configured": webhook_found,
        "config_files_checked": config_files,
        "verification_steps": steps,
        "test_messages": test_messages,
        "notes": "This is a safe check with no API calls - will not interfere with OpenClaw agent"
    }
    
    filename = "safe_verification_report.json"
    with open(filename, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"   📄 Report saved to: {filename}")
    
    print("\n" + "=" * 60)
    print("✅ SAFE VERIFICATION COMPLETE")
    print("=" * 60)
    
    print("\n📋 MANUAL VERIFICATION PROCESS:")
    print("   1. Keep OpenClaw agent running")
    print("   2. Send test messages to your bot")
    print("   3. Monitor OpenClaw console for output")
    print("   4. Check if messages are processed")
    print("   5. Verify bot replies (if configured)")
    
    print("\n⚠️  TROUBLESHOOTING:")
    print("   • No output: Check OpenClaw configuration")
    print("   • No replies: Check bot auto-reply settings")
    print("   • Errors: Check logs and configuration")
    
    print("\n🔧 For API testing (requires stopping OpenClaw):")
    print("   1. Stop OpenClaw agent")
    print("   2. Run: python3 test_webhook_endpoint.py")
    print("   3. Run: python3 test_webhook_integration.py")
    print("   4. Restart OpenClaw agent")

if __name__ == "__main__":
    safe_check()