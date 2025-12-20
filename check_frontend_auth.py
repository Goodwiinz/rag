#!/usr/bin/env python3
"""Check if frontend has authentication token"""

import os

# Check localStorage path for common browsers
home = os.path.expanduser("~")
browsers = [
    f"{home}/Library/Application Support/Google/Chrome/Default/Local Storage",
    f"{home}/Library/Application Support/Google/Chrome/Profile 1/Local Storage",
    f"{home}/Library/Application Support/Firefox/Profiles",
]

print("Checking for browser localStorage (this won't work directly)...")
print("\nInstead, please check in your browser:")
print("1. Open Developer Tools (F12 or Cmd+Opt+I)")
print("2. Go to Application/Storage tab")
print("3. Check Local Storage for your frontend URL (usually http://localhost:3000)")
print("4. Look for 'access_token' key")

print("\nOr simply check if you're logged in by looking at the frontend UI.")
print("If you see a login form or are redirected to login, you need to log in first.")