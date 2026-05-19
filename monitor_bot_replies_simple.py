#!/usr/bin/env python3
"""
Simple Bot Reply Monitor
Safest way to monitor bot replies - checks what's already available
"""

import os
import time
import json
from datetime import datetime

def check_available_sources():
    """Check what monitoring sources are available"""
    print("=" * 60)
    print("BOT REPLY MONITOR - SAFE VERSION")
    print("Checks available sources without interfering")
    print("=" * 60)
    
    sources = {}
    
    # 1. Check for log files
    print("\n🔍 Checking for log files...")
    log_locations = [
        os.path.expanduser("~/.openclaw/logs/"),
        "/var/log/openclaw/",
        "./logs/",
        ".",
    ]
    
    log_files = []
    for location in log_locations:
        if os.path.exists(location):
            try:
                files = os.listdir(location)
                for file in files:
                    if file.endswith(('.log', '.txt', '.json')):
                        full_path = os.path.join(location, file)
                        log_files.append(full_path)
            except:
                pass
    
    if log_files:
        print(f"✅ Found {len(log_files)} log files")
        sources['logs'] = log_files[:5]  # First 5 files
    else:
        print("⚠️  No log files found")
    
    # 2. Check database
    print("\n🔍 Checking database...")
    if os.path.exists('users.db'):
        print("✅ Database exists: users.db")
        sources['database'] = 'users.db'
        
        # Quick check for message tables
        import sqlite3
        try:
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            message_tables = [t for t in tables if 'message' in t.lower() or 'chat' in t.lower()]
            if message_tables:
                print(f"✅ Found message tables: {', '.join(message_tables)}")
                sources['message_tables'] = message_tables
            conn.close()
        except:
            print("⚠️  Could not read database")
    else:
        print("⚠️  Database not found")
    
    # 3. Check for output files
    print("\n🔍 Checking for output files...")
    output_files = []
    for file in os.listdir('.'):
        if any(keyword in file.lower() for keyword in ['output', 'result', 'report', 'telegram', 'bot']):
            if file.endswith(('.txt', '.json', '.log', '.csv')):
                output_files.append(file)
    
    if output_files:
        print(f"✅ Found output files: {', '.join(output_files)}")
        sources['output_files'] = output_files
    else:
        print("⚠️  No output files found")
    
    return sources

def monitor_logs(log_files, duration_seconds=60):
    """Monitor log files for bot replies"""
    if not log_files:
        print("\n📭 No log files to monitor")
        return
    
    print(f"\n📊 Monitoring {len(log_files)} log files for {duration_seconds} seconds...")
    print("   Send messages to bot to generate replies")
    print("   Press Ctrl+C to stop early\n")
    
    # Store initial file sizes
    file_sizes = {}
    for log_file in log_files:
        if os.path.exists(log_file):
            file_sizes[log_file] = os.path.getsize(log_file)
    
    start_time = time.time()
    found_replies = []
    
    try:
        while time.time() - start_time < duration_seconds:
            for log_file in log_files:
                if not os.path.exists(log_file):
                    continue
                
                current_size = os.path.getsize(log_file)
                initial_size = file_sizes.get(log_file, 0)
                
                if current_size > initial_size:
                    # Read new content
                    try:
                        with open(log_file, 'r') as f:
                            f.seek(initial_size)
                            new_content = f.read(current_size - initial_size)
                            
                            # Look for bot reply indicators
                            lines = new_content.split('\n')
                            for line in lines:
                                line_lower = line.lower()
                                if any(keyword in line_lower for keyword in [
                                    'bot reply', 'sent message', 'telegram send', 
                                    'sending to', '🤖', 'bot:', 'reply:'
                                ]):
                                    timestamp = datetime.now().strftime('%H:%M:%S')
                                    found_replies.append({
                                        'time': timestamp,
                                        'file': os.path.basename(log_file),
                                        'content': line.strip()[:100]
                                    })
                                    print(f"[{timestamp}] 📨 {os.path.basename(log_file)}: {line.strip()[:80]}...")
                        
                        # Update file size
                        file_sizes[log_file] = current_size
                    except:
                        pass
            
            # Wait before next check
            time.sleep(2)
            
            # Show progress
            elapsed = time.time() - start_time
            if int(elapsed) % 10 == 0 and elapsed > 0:
                remaining = duration_seconds - elapsed
                print(f"   ⏱️  {int(elapsed)}s elapsed, {int(remaining)}s remaining, {len(found_replies)} replies found")
    
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopped by user")
    
    print(f"\n📊 Monitoring complete!")
    print(f"   Found {len(found_replies)} possible bot replies")
    
    # Save results
    if found_replies:
        filename = f"bot_replies_{datetime.now().strftime('%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(found_replies, f, indent=2)
        print(f"   📄 Saved to: {filename}")

def create_test_plan():
    """Create a test plan for monitoring bot replies"""
    print("\n📋 CREATING TEST PLAN...")
    
    test_plan = {
        "test_objective": "Monitor bot replies from OpenClaw agent",
        "test_date": datetime.now().isoformat(),
        "preconditions": [
            "OpenClaw agent is running",
            "Bot is configured to send replies",
            "User can send messages to bot"
        ],
        "test_steps": [
            "1. Start this monitoring script",
            "2. Send test message to @nb_openclaw_ssy_bot",
            "3. Wait for bot reply",
            "4. Check monitoring output for reply evidence",
            "5. Repeat with different test messages"
        ],
        "test_messages": [
            "Hello, please reply",
            "Test message 1",
            "Can you respond?",
            datetime.now().strftime("Test at %H:%M:%S")
        ],
        "expected_results": [
            "Bot replies appear in monitoring output",
            "Replies match test messages",
            "No errors in monitoring"
        ],
        "verification_methods": [
            "Direct observation of monitoring output",
            "Check saved results file",
            "Verify in Telegram app"
        ]
    }
    
    filename = "bot_reply_test_plan.json"
    with open(filename, 'w') as f:
        json.dump(test_plan, f, indent=2)
    
    print(f"✅ Test plan saved to: {filename}")
    return filename

def main():
    """Main function"""
    # Check available sources
    sources = check_available_sources()
    
    if not any(sources.values()):
        print("\n❌ No monitoring sources found!")
        print("\n📋 Manual monitoring steps:")
        print("1. Send message to @nb_openclaw_ssy_bot")
        print("2. Watch OpenClaw agent console directly")
        print("3. Look for 'sending reply' or similar output")
        print("4. Check Telegram app for bot replies")
        return
    
    # Create test plan
    test_plan_file = create_test_plan()
    
    # Monitor logs if available
    if 'logs' in sources:
        monitor_logs(sources['logs'], duration_seconds=120)
    else:
        print("\n📭 No log files to monitor automatically")
        print(f"\n📋 Run the test plan manually:")
        print(f"1. Review: {test_plan_file}")
        print("2. Send test messages to bot")
        print("3. Monitor OpenClaw output directly")
    
    print("\n" + "=" * 60)
    print("✅ Bot Reply Monitoring Complete!")
    print("=" * 60)
    
    print("\n🎯 Key Points:")
    print("• This method is SAFE - doesn't call Telegram API")
    print("• Monitors existing logs/files")
    print("• Won't interfere with OpenClaw agent")
    
    print(f"\n📋 Next steps:")
    print(f"1. Review test plan: {test_plan_file}")
    print("2. Send test messages to bot")
    print("3. Check monitoring output")
    print("4. Verify bot replies in Telegram app")

if __name__ == "__main__":
    main()