"""
Instagram / Meta Graph API setup.
Gets a long-lived access token for posting Reels.

Run: python auth/instagram_auth.py
Then follow the printed instructions.
"""

import sys
import webbrowser

try:
    import requests
except ImportError:
    print("Run: pip install requests")
    sys.exit(1)


def exchange_for_long_lived_token(short_token: str, app_id: str, app_secret: str) -> dict:
    """Exchange a short-lived token (1hr) for a long-lived token (60 days)."""
    url = "https://graph.facebook.com/v19.0/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": short_token,
    }
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def get_instagram_user_id(access_token: str) -> str:
    """Get your Instagram Business account user ID."""
    url = "https://graph.facebook.com/v19.0/me/accounts"
    params = {"access_token": access_token, "fields": "instagram_business_account,name"}
    response = requests.get(url, params=params, timeout=30)
    data = response.json()

    pages = data.get("data", [])
    if not pages:
        print("No Facebook pages found. Your Instagram account must be a Business or Creator account linked to a Facebook Page.")
        return None

    for page in pages:
        ig = page.get("instagram_business_account", {})
        if ig.get("id"):
            print(f"  Found Instagram account: {ig['id']} (linked to Facebook page: {page['name']})")
            return ig["id"]

    print("No Instagram Business account found linked to your Facebook pages.")
    return None


def main():
    print("""
============================================================
Instagram Reels API Setup — Step by Step
============================================================

REQUIREMENTS (before you start):
  → Your Instagram account must be a Business or Creator account
  → It must be linked to a Facebook Page
  → You need a Meta Developer account

STEP 1 — Create a Meta Developer app
  → Go to: https://developers.facebook.com/apps
  → Click "Create App"
  → Type: Business
  → Add the "Instagram Graph API" product

STEP 2 — Get a short-lived access token
  → In your app dashboard → Tools → Graph API Explorer
  → Select your app from the dropdown
  → Click "Generate Access Token"
  → Select permissions: instagram_content_publish, instagram_basic, pages_read_engagement
  → Authorize and copy the token

STEP 3 — Run this script to exchange for a long-lived token
""")

    app_id = input("Paste your Meta App ID: ").strip()
    app_secret = input("Paste your Meta App Secret: ").strip()
    short_token = input("Paste your short-lived access token: ").strip()

    print("\nExchanging for long-lived token...")
    try:
        result = exchange_for_long_lived_token(short_token, app_id, app_secret)
        long_token = result.get("access_token")
        expires_in = result.get("expires_in", 0)
        days = round(expires_in / 86400)
        print(f"Got long-lived token (expires in {days} days)")
    except Exception as e:
        print(f"Token exchange failed: {e}")
        print("Make sure your App ID, App Secret, and short-lived token are correct.")
        sys.exit(1)

    print("\nLooking up your Instagram Business account ID...")
    ig_user_id = get_instagram_user_id(long_token)

    print("\n" + "=" * 60)
    print("SUCCESS — Instagram auth complete!")
    print("=" * 60)
    print("\nAdd these to Railway:\n")
    print(f"  INSTAGRAM_ACCESS_TOKEN={long_token}")
    if ig_user_id:
        print(f"  INSTAGRAM_USER_ID={ig_user_id}")
    else:
        print("  INSTAGRAM_USER_ID=<find your IG business account ID manually>")
    print("""
NOTE: Long-lived tokens expire in ~60 days.
To refresh before expiry, run this script again with the same long-lived token as input.

ALSO NEEDED: Instagram requires videos to be at a public URL before uploading.
Set up Cloudflare R2 (free) or any S3-compatible storage, then set:
  CDN_UPLOAD_URL=https://your-upload-endpoint.com/upload
  CDN_API_KEY=your-key-if-needed
============================================================
""")


if __name__ == "__main__":
    main()
