"""
get_gmail_token.py — Run this ONCE on your local computer.
Outputs 3 values to paste into Railway env vars.

STEP-BY-STEP:
  1. Go to: https://console.cloud.google.com
  2. Create a new project (call it "GHE Dashboard")
  3. Left sidebar → "APIs & Services" → "Library"
     Search "Gmail API" → click it → click "Enable"
  4. Left sidebar → "APIs & Services" → "Credentials"
  5. Click "Create Credentials" → "OAuth client ID"
  6. Application type: "Desktop app" → Name: "GHE" → Create
  7. Click the download button (⬇) → saves as a .json file
  8. Rename that file to "gmail_credentials.json"
  9. Place it in: C:\\Users\\curti\\Downloads\\First Agentic Workflows\\
 10. Run: python get_gmail_token.py
 11. A browser will open — log in as grayhorizonsenterprise@gmail.com
 12. Click "Allow" (may show a warning — click "Advanced" → "Go to GHE (unsafe)")
 13. Copy the 3 values printed below into Railway → ghe-dashboard → Variables

Install required packages first (run in terminal):
  pip install google-auth-oauthlib google-api-python-client
"""

import json
import os
import sys

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
CREDS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gmail_credentials.json")


def main():
    print("=" * 60)
    print("Gmail OAuth Token Generator — Gray Horizons Enterprise")
    print("=" * 60)
    print()

    if not os.path.exists(CREDS_FILE):
        print(f"ERROR: gmail_credentials.json not found at:")
        print(f"  {CREDS_FILE}")
        print()
        print("Follow steps 1-9 in the file header above, then re-run.")
        sys.exit(1)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("ERROR: Missing packages. Run:")
        print("  pip install google-auth-oauthlib google-api-python-client")
        sys.exit(1)

    print("Opening browser for Google login...")
    print("Log in as: grayhorizonsenterprise@gmail.com")
    print()

    flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)

    with open(CREDS_FILE) as f:
        client_data = json.load(f)

    installed = client_data.get("installed", client_data.get("web", {}))
    client_id     = installed.get("client_id", "")
    client_secret = installed.get("client_secret", "")
    refresh_token = creds.refresh_token

    if not refresh_token:
        print("ERROR: No refresh token received. Make sure you clicked 'Allow'.")
        sys.exit(1)

    print()
    print("=" * 60)
    print("SUCCESS! Add these 5 values to Railway → ghe-dashboard → Variables:")
    print("=" * 60)
    print()
    print(f"GMAIL_CLIENT_ID={client_id}")
    print(f"GMAIL_CLIENT_SECRET={client_secret}")
    print(f"GMAIL_REFRESH_TOKEN={refresh_token}")
    print(f"GHE_EMAIL=grayhorizonsenterprise@gmail.com")
    print(f"CALENDLY_URL=https://calendly.com/grayhorizonsenterprise/30min")
    print()
    print("After adding: Railway will auto-redeploy. Gmail Monitor will show SET on /status.")
    print()

    # Also save to a local file for backup
    out = {
        "GMAIL_CLIENT_ID": client_id,
        "GMAIL_CLIENT_SECRET": client_secret,
        "GMAIL_REFRESH_TOKEN": refresh_token,
        "GHE_EMAIL": "grayhorizonsenterprise@gmail.com",
        "CALENDLY_URL": "https://calendly.com/grayhorizonsenterprise/30min",
    }
    out_file = os.path.join(os.path.dirname(CREDS_FILE), "gmail_env_vars.txt")
    with open(out_file, "w") as f:
        for k, v in out.items():
            f.write(f"{k}={v}\n")
    print(f"(Also saved to: {out_file})")


if __name__ == "__main__":
    main()
