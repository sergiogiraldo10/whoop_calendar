from typing import Optional

import requests

# Must match the key the Cloudflare Worker's WorkerKVTokenStore uses
# (shared/token-store.ts) — both read/write the same KV entry.
KV_KEY = "whoop_tokens"


class RestKVTokenStore:
    """
    Reads/writes WHOOP tokens in Cloudflare KV via Cloudflare's REST API.
    WHOOP's refresh token rotates on every use, and both this (GitHub Actions
    jobs) and the Cloudflare Worker's webhook handler refresh independently —
    the shared KV namespace is the single source of truth that keeps them in sync.
    """

    def __init__(self, account_id: str, namespace_id: str, api_token: str):
        self._url = (
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
            f"/storage/kv/namespaces/{namespace_id}/values/{KV_KEY}"
        )
        self._headers = {"Authorization": f"Bearer {api_token}"}

    def get_whoop_tokens(self) -> Optional[dict]:
        res = requests.get(self._url, headers=self._headers)
        if res.status_code == 404:
            return None
        res.raise_for_status()
        return res.json()

    def set_whoop_tokens(self, tokens: dict) -> None:
        res = requests.put(
            self._url,
            headers={**self._headers, "Content-Type": "application/json"},
            json=tokens,
        )
        res.raise_for_status()
