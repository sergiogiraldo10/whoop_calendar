"""One-time interactive Google OAuth setup. Run locally, never in CI.

Usage: python -m scripts.google_auth
"""

import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, quote, urlparse

from dotenv import load_dotenv

from whoop_sync.calendar_client import exchange_code

load_dotenv()


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


CLIENT_ID = _required("GOOGLE_CLIENT_ID")
CLIENT_SECRET = _required("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8788/callback")

SCOPES = "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/gmail.send"


def _build_auth_url() -> str:
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",  # forces a refresh_token even on repeat runs
    }
    query = "&".join(f"{k}={quote(v, safe='')}" for k, v in params.items())
    return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        code = parse_qs(urlparse(self.path).query).get("code", [None])[0]
        if not code:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing code param")
            return

        try:
            tokens = exchange_code(CLIENT_ID, CLIENT_SECRET, code, REDIRECT_URI)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Google auth complete - check the terminal. You can close this tab.")
            print("\nSave this as GOOGLE_REFRESH_TOKEN (GitHub Actions secret + `wrangler secret put`):\n")
            print(tokens["refresh_token"])
        except Exception as err:  # noqa: BLE001 - report to terminal, then shut down either way
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"Auth failed - check the terminal for details.")
            print(err)
        finally:
            threading.Thread(target=self.server.shutdown).start()

    def log_message(self, format: str, *args) -> None:  # silence default request logging
        pass


def main() -> None:
    print("Open this URL, approve access, and you'll be redirected back here:\n")
    print(_build_auth_url())
    print(
        "\nNote: your Google Cloud OAuth consent screen must be in 'Production' publishing status,"
        " or this refresh token will expire after 7 days."
    )

    port = urlparse(REDIRECT_URI).port or 8788
    server = HTTPServer(("localhost", port), CallbackHandler)
    print(f"\nWaiting for redirect on {REDIRECT_URI} ...")
    server.serve_forever()


if __name__ == "__main__":
    main()
