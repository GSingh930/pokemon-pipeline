# -*- coding: utf-8 -*-
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

print("""
============================================================
TikTok Session ID - How to get it
============================================================

You don't need an API. Just grab your session ID from your browser.

STEPS:
  1. Open Chrome or Edge
  2. Go to https://www.tiktok.com and log in
  3. Press F12 to open Developer Tools
  4. Click "Application" tab (or "Storage" in Firefox)
  5. In the left panel: Cookies > https://www.tiktok.com
  6. Find the cookie named: sessionid
  7. Copy the Value (long string of letters and numbers)

Then set in Railway:
  TIKTOK_SESSION_ID=paste_your_sessionid_here
  TIKTOK_ENABLED=true

That is it. No API approval needed.
============================================================
""")
