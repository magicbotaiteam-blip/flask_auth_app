#!/usr/bin/env python3
"""
Simple script to start the app on port 5000
"""

from app_complete_with_groups import app

if __name__ == "__main__":
    print("Starting Magic Bot AI on port 5000...")
    print("Visit: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)