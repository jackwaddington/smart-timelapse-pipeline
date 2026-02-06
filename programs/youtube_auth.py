#!/usr/bin/env python3
"""
YouTube OAuth Authentication Script

Run this once to authenticate with YouTube. Supports headless mode for Pi.

Usage:
    python3 youtube_auth.py              # Interactive mode (opens browser)
    python3 youtube_auth.py --headless   # Headless mode (prints URL to visit)
    python3 youtube_auth.py --test       # Test if credentials are valid
"""

import sys
import json
import argparse
from pathlib import Path

# Add parent directory to path for imports
SCRIPT_PATH = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_PATH.parent
CONF_DIR = PROJECT_ROOT / "conf"

# Default paths
CLIENT_SECRETS_FILE = CONF_DIR / "client_secrets.json"
CREDENTIALS_FILE = CONF_DIR / "youtube_credentials.json"

# YouTube API scopes
SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube.readonly'
]


def check_dependencies():
    """Check if required packages are installed."""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        return True
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("\nInstall required packages with:")
        print("  pip3 install google-api-python-client google-auth-oauthlib google-auth-httplib2")
        return False


def authenticate_interactive():
    """Run OAuth flow with browser (for machines with display)."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not CLIENT_SECRETS_FILE.exists():
        print(f"ERROR: Client secrets file not found: {CLIENT_SECRETS_FILE}")
        print("Download it from Google Cloud Console and place it there.")
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_SECRETS_FILE),
        scopes=SCOPES
    )

    credentials = flow.run_local_server(port=0)
    save_credentials(credentials)
    print(f"\nCredentials saved to: {CREDENTIALS_FILE}")
    print("YouTube authentication successful!")
    return credentials


def authenticate_headless():
    """Run OAuth flow without browser (for headless Pi)."""
    from google_auth_oauthlib.flow import Flow

    if not CLIENT_SECRETS_FILE.exists():
        print(f"ERROR: Client secrets file not found: {CLIENT_SECRETS_FILE}")
        print("Download it from Google Cloud Console and place it there.")
        sys.exit(1)

    # Use the out-of-band redirect URI for manual code entry
    OOB_REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'

    flow = Flow.from_client_secrets_file(
        str(CLIENT_SECRETS_FILE),
        scopes=SCOPES,
        redirect_uri=OOB_REDIRECT_URI
    )

    # Generate URL for user to visit
    auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')

    print("\n" + "="*60)
    print("YOUTUBE AUTHENTICATION")
    print("="*60)
    print("\n1. Visit this URL in any browser:\n")
    print(auth_url)
    print("\n2. Sign in and authorize the application")
    print("3. Copy the authorization code shown after authorization")
    print("4. Paste the code below:\n")

    code = input("Authorization code: ").strip()

    try:
        flow.fetch_token(code=code)
        credentials = flow.credentials
        save_credentials(credentials)
        print(f"\nCredentials saved to: {CREDENTIALS_FILE}")
        print("YouTube authentication successful!")
        return credentials
    except Exception as e:
        print(f"\nError: {e}")
        print("Make sure you copied the entire authorization code.")
        sys.exit(1)


def save_credentials(credentials):
    """Save credentials to JSON file."""
    CONF_DIR.mkdir(exist_ok=True)

    creds_data = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': list(credentials.scopes)
    }

    with open(CREDENTIALS_FILE, 'w') as f:
        json.dump(creds_data, f, indent=2)


def load_credentials():
    """Load and refresh credentials from file."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    if not CREDENTIALS_FILE.exists():
        return None

    with open(CREDENTIALS_FILE, 'r') as f:
        creds_data = json.load(f)

    credentials = Credentials(
        token=creds_data['token'],
        refresh_token=creds_data['refresh_token'],
        token_uri=creds_data['token_uri'],
        client_id=creds_data['client_id'],
        client_secret=creds_data['client_secret'],
        scopes=creds_data['scopes']
    )

    # Refresh if expired
    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            save_credentials(credentials)
            print("Credentials refreshed successfully.")
        except Exception as e:
            print(f"Failed to refresh credentials: {e}")
            return None

    return credentials


def test_credentials():
    """Test if credentials are valid by making an API call."""
    from googleapiclient.discovery import build

    credentials = load_credentials()
    if not credentials:
        print("No credentials found. Run authentication first.")
        return False

    try:
        youtube = build('youtube', 'v3', credentials=credentials)
        # Try to get channel info
        request = youtube.channels().list(part='snippet', mine=True)
        response = request.execute()

        if response.get('items'):
            channel = response['items'][0]['snippet']
            print(f"\nAuthenticated as: {channel['title']}")
            print(f"Channel ID: {response['items'][0]['id']}")
            print("\nCredentials are valid and working!")
            return True
        else:
            print("Could not get channel info. Check permissions.")
            return False

    except Exception as e:
        print(f"Error testing credentials: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='YouTube OAuth Authentication')
    parser.add_argument('--headless', action='store_true',
                        help='Headless mode (no browser, prints URL)')
    parser.add_argument('--test', action='store_true',
                        help='Test if credentials are valid')
    args = parser.parse_args()

    if not check_dependencies():
        sys.exit(1)

    if args.test:
        success = test_credentials()
        sys.exit(0 if success else 1)

    # Check if already authenticated
    if CREDENTIALS_FILE.exists():
        print(f"Existing credentials found at: {CREDENTIALS_FILE}")
        response = input("Re-authenticate? (y/N): ").strip().lower()
        if response != 'y':
            print("Testing existing credentials...")
            if test_credentials():
                return
            print("\nCredentials invalid. Re-authenticating...")

    if args.headless:
        authenticate_headless()
    else:
        authenticate_interactive()

    # Test the new credentials
    print("\nTesting credentials...")
    test_credentials()


if __name__ == "__main__":
    main()
