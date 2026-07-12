"""
Box OAuth2 One-Time Setup
=========================
Run this script ONCE from the command line:

    python box_oauth2_setup.py

It will:
  1. Open your browser at the Box authorization URL
  2. You log in and click "Grant access to Box"
  3. Box redirects to http://localhost:8080?code=XXXX
  4. This script catches the code, exchanges it for tokens, and saves
     both access_token and refresh_token into config.json

After that the web app uses the refresh_token permanently — it auto-renews
on every API call and you never need to touch the token again.

IMPORTANT: Your Box App must have http://localhost:8080 as a redirect URI.
  1. Go to https://app.box.com/developers/console
  2. Click your app → Configuration
  3. Under "OAuth 2.0 Redirect URI" add: http://localhost:8080
  4. Save changes, then run this script.
"""

import json
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from boxsdk import OAuth2, Client

# ── Paths ─────────────────────────────────────────────────────────────────────
CONFIG_PATH = Path(__file__).parent / "config.json"
REDIRECT_URI = "http://localhost:8080"

# ── Load config ───────────────────────────────────────────────────────────────
with open(CONFIG_PATH, encoding="utf-8") as f:
    config = json.load(f)

box_cfg       = config["box"]
CLIENT_ID     = box_cfg["client_id"]
CLIENT_SECRET = box_cfg["client_secret"]

# ── Shared state for the local callback server ────────────────────────────────
_auth_code = None


class _CallbackHandler(BaseHTTPRequestHandler):
    """Tiny HTTP handler that captures the ?code= parameter from Box."""

    def do_GET(self):
        global _auth_code
        params = parse_qs(urlparse(self.path).query)
        code   = params.get("code", [None])[0]

        if code:
            _auth_code = code
            body = b"<h2>Authorization successful!</h2><p>You can close this tab.</p>"
            self.send_response(200)
        else:
            body = b"<h2>Error: no code received.</h2><p>Please try again.</p>"
            self.send_response(400)

        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass   # suppress server access logs


def main():
    # ── Step 1: Build the auth URL ─────────────────────────────────────────────
    auth = OAuth2(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        store_tokens=lambda a, r: None,   # placeholder — overwritten after exchange
    )
    auth_url, csrf_token = auth.get_authorization_url(REDIRECT_URI)

    print("=" * 60)
    print("  Box OAuth2 One-Time Setup")
    print("=" * 60)
    print()
    print("  Opening your browser for Box authorization…")
    print("  If the browser does not open, visit this URL manually:")
    print()
    print(f"  {auth_url}")
    print()
    print("  Waiting for Box to redirect back to localhost:8080 …")
    print()

    webbrowser.open(auth_url)

    # ── Step 2: Start local server to catch the redirect ──────────────────────
    server = HTTPServer(("127.0.0.1", 8080), _CallbackHandler)
    server.timeout = 120   # wait up to 2 minutes
    server.handle_request()   # serve exactly one request

    if not _auth_code:
        print("ERROR: No authorization code received. Did you approve access in Box?")
        sys.exit(1)

    # ── Step 3: Exchange the code for access + refresh tokens ─────────────────
    print("  Authorization code received. Exchanging for tokens…")
    access_token, refresh_token = auth.authenticate(_auth_code)

    # ── Step 4: Save both tokens to config.json ───────────────────────────────
    config["box"]["access_token"]  = access_token
    config["box"]["refresh_token"] = refresh_token

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    # ── Step 5: Verify the client works ───────────────────────────────────────
    def _save(a, r):
        config["box"]["access_token"]  = a
        config["box"]["refresh_token"] = r
        with open(CONFIG_PATH, "w", encoding="utf-8") as ff:
            json.dump(config, ff, indent=2)

    auth2  = OAuth2(CLIENT_ID, CLIENT_SECRET,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    store_tokens=_save)
    client = Client(auth2)
    me     = client.user().get()

    print()
    print("=" * 60)
    print("  SUCCESS!")
    print(f"  Logged in as: {me.name} ({me.login})")
    print()
    print("  Permanent refresh token saved to config.json.")
    print("  The web app will now authenticate automatically — forever.")
    print("=" * 60)
    print()
    input("  Press Enter to close this window.")


if __name__ == "__main__":
    main()
