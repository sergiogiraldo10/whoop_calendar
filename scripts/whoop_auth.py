"""One-time interactive WHOOP OAuth setup. Run locally, never in CI.

Usage: python -m scripts.whoop_auth
"""

import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, quote, urlparse

from dotenv import load_dotenv

from whoop_sync.token_store import RestKVTokenStore
from whoop_sync.whoop_client import exchange_code

load_dotenv()


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


CLIENT_ID = _required("WHOOP_CLIENT_ID")
CLIENT_SECRET = _required("WHOOP_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("WHOOP_REDIRECT_URI", "http://localhost:8787/callback")
CF_ACCOUNT_ID = _required("CF_ACCOUNT_ID")
CF_API_TOKEN = _required("CF_API_TOKEN")
CF_NAMESPACE_ID = _required("CF_KV_NAMESPACE_ID")

SCOPES = "read:recovery read:cycles read:sleep read:workout read:profile offline"


def _build_auth_url() -> str:
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "state": str(uuid.uuid4()),
    }
    query = "&".join(f"{k}={quote(v, safe='')}" for k, v in params.items())
    return f"https://api.prod.whoop.com/oauth/oauth2/auth?{query}"


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
            RestKVTokenStore(CF_ACCOUNT_ID, CF_NAMESPACE_ID, CF_API_TOKEN).set_whoop_tokens(tokens)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"WHOOP auth complete - tokens saved to Cloudflare KV. You can close this tab.")
            print("\nWHOOP tokens saved to Cloudflare KV.")
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

    port = urlparse(REDIRECT_URI).port or 8787
    server = HTTPServer(("localhost", port), CallbackHandler)
    print(f"\nWaiting for redirect on {REDIRECT_URI} ...")
    server.serve_forever()


if __name__ == "__main__":
    main()
