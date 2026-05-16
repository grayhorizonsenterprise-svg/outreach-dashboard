"""
youtube_auth_setup.py — Run this ONCE on your local machine (not Railway).
It opens a browser, you click Allow, and it prints the three env vars
you need to paste into Railway. After that, Railway uploads automatically forever.

Requirements:
  pip install google-auth-oauthlib google-api-python-client

Steps:
  1. Go to console.cloud.google.com → New Project → "ShadowClans"
  2. APIs & Services → Enable → search "YouTube Data API v3" → Enable
  3. APIs & Services → OAuth consent screen → External → fill app name → Save
  4. APIs & Services → Credentials → Create → OAuth 2.0 Client ID
     → Application type: Desktop app → Create → Download JSON
  5. Save that JSON file as client_secrets.json in this folder
  6. Run: python youtube_auth_setup.py
  7. Browser opens → sign in → click Allow
  8. Copy the 3 lines it prints → paste into Railway env vars
"""

import json
import os

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main():
    secrets_file = os.path.join(os.path.dirname(__file__), "client_secrets.json")
    if not os.path.exists(secrets_file):
        print("\n[ERROR] client_secrets.json not found.")
        print("  1. Go to console.cloud.google.com")
        print("  2. Create project → Enable YouTube Data API v3")
        print("  3. Credentials → OAuth 2.0 Client ID → Desktop App → Download JSON")
        print(f"  4. Save as: {secrets_file}")
        return

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("[ERROR] Missing library. Run: pip install google-auth-oauthlib google-api-python-client")
        return

    flow = InstalledAppFlow.from_client_secrets_file(secrets_file, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(secrets_file) as f:
        client_data = json.load(f)

    installed = client_data.get("installed") or client_data.get("web") or {}
    client_id     = installed.get("client_id", "")
    client_secret = installed.get("client_secret", "")
    refresh_token = creds.refresh_token

    print("\n" + "=" * 60)
    print("  ADD THESE 3 ENV VARS TO RAILWAY → outreach-dashboard")
    print("=" * 60)
    print(f"\nYOUTUBE_CLIENT_ID      = {client_id}")
    print(f"YOUTUBE_CLIENT_SECRET  = {client_secret}")
    print(f"YOUTUBE_REFRESH_TOKEN  = {refresh_token}")
    print("\n" + "=" * 60)
    print("  Done. Shadow Clans will auto-upload to YouTube every night.")
    print("=" * 60)


if __name__ == "__main__":
    main()
