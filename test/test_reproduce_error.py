#!/usr/bin/env python3
"""
Test to reproduce the BuildError
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app_fixed import app

def test_landing_page():
    print("Testing landing page rendering...")
    print("=" * 60)
    
    with app.test_client() as client:
        with app.app_context():
            # Try to render the landing template directly
            from flask import render_template, url_for
            
            print("1. Testing url_for('signup_local') in app context:")
            try:
                url = url_for('signup_local')
                print(f"   ✅ url_for('signup_local') = {url}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
            
            print("\n2. Testing url_for('signin_local') in app context:")
            try:
                url = url_for('signin_local')
                print(f"   ✅ url_for('signin_local') = {url}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
            
            print("\n3. Rendering landing.html template:")
            try:
                # Render the template
                rendered = render_template("landing.html", google=True)
                print("   ✅ Template rendered successfully!")
                
                # Check if the problematic line is in the rendered output
                if 'signup_local' in rendered:
                    print("   ✅ 'signup_local' found in rendered template")
                else:
                    print("   ⚠️  'signup_local' NOT found in rendered template")
                    
            except Exception as e:
                print(f"   ❌ Error rendering template: {e}")
                import traceback
                traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("If tests 1 and 2 pass but test 3 fails,")
    print("there's a template rendering issue.")
    print("=" * 60)

if __name__ == "__main__":
    test_landing_page()