#!/usr/bin/env python3
"""
Quick test to see if the app starts
"""

import subprocess
import time
import os
import signal

print("Testing if app starts...")
print("=" * 60)

# Start the app in background
proc = subprocess.Popen(
    ["python", "app_complete_with_groups.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

# Wait a bit for startup
time.sleep(2)

# Check if process is still running
if proc.poll() is None:
    print("✅ App started successfully!")
    print("\nApp should be running at: http://localhost:5000")
    
    # Read some output
    try:
        stdout, stderr = proc.communicate(timeout=1)
        if stdout:
            print("\nApp output:")
            print("-" * 40)
            print(stdout[:500])
    except subprocess.TimeoutExpired:
        pass
    
    # Kill the process
    proc.terminate()
    proc.wait()
    print("\n✅ Test completed - app starts without errors")
else:
    # Process exited, read error
    stdout, stderr = proc.communicate()
    print("❌ App failed to start")
    print("\nError output:")
    print("-" * 40)
    print(stderr)
    
print("=" * 60)