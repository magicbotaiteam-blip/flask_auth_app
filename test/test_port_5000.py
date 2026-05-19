#!/usr/bin/env python3
"""
Test if the app can run on port 5000
"""

import socket
import sys
import time

def check_port_available(port):
    """Check if a port is available"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('localhost', port))
        sock.close()
        return True
    except OSError:
        return False

print("Testing port 5000 availability...")
print("=" * 60)

if check_port_available(5000):
    print("✅ Port 5000 is available")
    
    # Try to import and start the app
    try:
        from app_complete_with_groups import app
        
        print("\n✅ App imports successfully")
        print(f"App name: {app.name}")
        
        # Start the app in a way we can test
        import threading
        
        def run_app():
            app.run(debug=False, host='0.0.0.0', port=5000, use_reloader=False)
        
        # Start app in background thread
        thread = threading.Thread(target=run_app, daemon=True)
        thread.start()
        
        # Give it time to start
        time.sleep(2)
        
        # Try to connect
        import requests
        try:
            response = requests.get('http://localhost:5000/landing', timeout=3)
            if response.status_code == 200:
                print("✅ App is running on port 5000")
                print(f"✅ Landing page loaded: {len(response.text)} bytes")
                
                # Check title
                if '<title>Magic Bot AI - Bots Management Platform</title>' in response.text:
                    print("✅ Correct title found")
                else:
                    print("⚠️  Title not as expected")
            else:
                print(f"❌ App returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ Could not connect to app: {e}")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
else:
    print("❌ Port 5000 is not available")
    print("\nProcesses using port 5000:")
    import subprocess
    result = subprocess.run(['lsof', '-i', ':5000'], capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    else:
        print("(No output from lsof)")

print("\n" + "=" * 60)
print("To start the app manually:")
print("  cd /Users/siyang/flask_auth_app")
print("  python app_complete_with_groups.py")
print("\nOr use the startup script:")
print("  ./start_on_port_5000.sh")
print("=" * 60)