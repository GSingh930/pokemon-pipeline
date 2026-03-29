# -*- coding: utf-8 -*-
"""
YouTube OAuth setup -- run this ONCE locally on your machine.

Usage:
    1. Go to https://console.cloud.google.com
    2. Create a project (or use existing)
    3. Enable "YouTube Data API v3"
    4. Go to APIs & Services > Credentials > Create Credentials > OAuth 2.0 Client ID
    5. Choose "Desktop app" as the application type
    6. Download the JSON file -- save it as client_secrets.json in this folder
    7. Run: python auth/youtube_auth.py
    8. A browser window will open -- log in and approve access
    9. Copy the printed YOUTUBE_TOKEN_JSON value into Railway as an env variable
"""

import io
import json
import sys
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("Missing dependencies. Run:\n  pip install google-auth-oauthlib google-api-python-client")
    sys.exit(1)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
SECRETS_FILE = Path(__file__).parent / "client_secrets.json"
TOKEN_FILE = Path(__file__).parent / "youtube_token.json"


def main():
    if not SECRETS_FILE.exists():
        print(f"""
ERROR: client_secrets.json not found at:
  {SECRETS_FILE}

To fix this:
  1. Go to https://console.cloud.google.com
  2. Select your project > APIs & Services > Credentials
  3. Click "Create Credentials" > OAuth 2.0 Client ID
  4. Application type: Desktop app
  5. Click Download JSON
  6. Rename the downloaded file to: client_secrets.json
  7. Place it in the auth/ folder next to this script
  8. Re-run: python auth/youtube_auth.py
""")
        sys.exit(1)

    print("Found client_secrets.json — starting OAuth flow...")
    print("A browser window will open. Log in with the Google account you want to post from.\n")

    flow = InstalledAppFlow.from_client_secrets_file(str(SECRETS_FILE), SCOPES)
    creds = flow.run_local_server(
        port=8080,
        prompt="consent",
        success_message="Auth complete! You can close this tab and return to the terminal.",
    )

    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes),
    }

    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)

    token_json_str = json.dumps(token_data)

    with open(SECRETS_FILE) as f:
        secrets = json.load(f)
    installed = secrets.get("installed", secrets.get("web", {}))

    print("\n" + "=" * 60)
    print("SUCCESS — YouTube auth complete!")
    print("=" * 60)
    print("\nAdd these 3 variables to Railway:\n")
    print(f"  YOUTUBE_CLIENT_ID={installed.get('client_id', '???')}")
    print(f"  YOUTUBE_CLIENT_SECRET={installed.get('client_secret', '???')}")
    print(f"  YOUTUBE_TOKEN_JSON={token_json_str}")
    print("\n" + "=" * 60)
    print("\nToken also saved locally to: auth/youtube_token.json")


if __name__ == "__main__":
    main()
