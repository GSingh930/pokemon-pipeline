"""
TikTok auth setup — prints step-by-step instructions for getting
your TikTok Content Posting API access token.

TikTok's API requires manual approval, so this script just guides you through it.

Run: python auth/tiktok_auth.py
"""

print("""
============================================================
TikTok API Setup — Step by Step
============================================================

TikTok requires manual app approval for the Content Posting API.
This takes 1-3 business days. Here's the exact process:

STEP 1 — Create a TikTok Developer account
  → Go to: https://developers.tiktok.com
  → Click "Log in" and use your TikTok account
  → Complete developer registration

STEP 2 — Create an app
  → Go to: https://developers.tiktok.com/apps
  → Click "Create app"
  → App name: anything (e.g. "Pokemon Shorts Bot")
  → Platform: Web
  → Category: Entertainment

STEP 3 — Request the Content Posting API scope
  → Inside your app, go to "Manage" → "Scopes"
  → Find "Content Posting API"
  → Request access — fill out the use case form
  → Wait for approval (1-3 business days)
  → You'll get an email when approved

STEP 4 — Get your access token (after approval)
  → In your app dashboard → "Manage" → "API credentials"
  → Copy your Client Key and Client Secret
  → Use TikTok's OAuth flow to get a user access token:

    POST https://open.tiktokapis.com/v2/oauth/token/
    Body:
      client_key=YOUR_CLIENT_KEY
      client_secret=YOUR_CLIENT_SECRET
      code=AUTH_CODE (from OAuth redirect)
      grant_type=authorization_code
      redirect_uri=YOUR_REDIRECT_URI

  → The response includes access_token — save this as:
    TIKTOK_ACCESS_TOKEN=...

SHORTCUT (for testing):
  → In the TikTok developer portal, under your app
  → "API Explorer" → you can generate a test access token
  → This token lasts 24 hours — good for initial testing

IMPORTANT NOTES:
  → Access tokens expire. Set up token refresh using the refresh_token.
  → Your app must post from the TikTok account that authorized it.
  → The Content Posting API posts as "private" by default until your
    app is verified. Set TIKTOK_PRIVACY=SELF_ONLY for testing.

============================================================
Once you have your token, set in Railway:
  TIKTOK_ACCESS_TOKEN=your_token_here
  TIKTOK_ENABLED=true
============================================================
""")
