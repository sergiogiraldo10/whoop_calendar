import time
from typing import Optional

import requests

API_BASE = "https://api.prod.whoop.com/developer/v2"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
EXPIRY_SKEW_MS = 60_000


def exchange_code(client_id: str, client_secret: str, code: str, redirect_uri: str) -> dict:
    return _request_tokens(
        client_id,
        client_secret,
        {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
    )


def _refresh_tokens(client_id: str, client_secret: str, refresh_token: str) -> dict:
    return _request_tokens(
        client_id,
        client_secret,
        {"grant_type": "refresh_token", "refresh_token": refresh_token},
    )


def _request_tokens(client_id: str, client_secret: str, params: dict) -> dict:
    res = requests.post(
        TOKEN_URL,
        data={"client_id": client_id, "client_secret": client_secret, **params},
    )
    res.raise_for_status()
    body = res.json()
    return {
        "access_token": body["access_token"],
        "refresh_token": body["refresh_token"],
        "expires_at": time.time() * 1000 + body["expires_in"] * 1000,
    }


def get_valid_access_token(store, client_id: str, client_secret: str) -> str:
    """Refreshes and persists to the shared KV store if expired (see token_store.py)."""
    tokens = store.get_whoop_tokens()
    if not tokens:
        raise RuntimeError("No WHOOP tokens in store — run `python -m scripts.whoop_auth` first.")
    if tokens["expires_at"] - EXPIRY_SKEW_MS > time.time() * 1000:
        return tokens["access_token"]
    refreshed = _refresh_tokens(client_id, client_secret, tokens["refresh_token"])
    store.set_whoop_tokens(refreshed)
    return refreshed["access_token"]


def _get_json(path: str, access_token: str, params: Optional[dict] = None) -> dict:
    res = requests.get(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bearer {access_token}"},
        params=params,
    )
    res.raise_for_status()
    return res.json()


def get_sleep(record_id: int, access_token: str) -> dict:
    return _get_json(f"/activity/sleep/{record_id}", access_token)


def get_workout(record_id: int, access_token: str) -> dict:
    return _get_json(f"/activity/workout/{record_id}", access_token)


def _list_collection(path: str, access_token: str, start: str, end: str) -> list:
    records = []
    next_token = None
    while True:
        params = {"start": start, "end": end, "limit": 25}
        if next_token:
            params["nextToken"] = next_token
        page = _get_json(path, access_token, params)
        records.extend(page["records"])
        next_token = page.get("next_token")
        if not next_token:
            break
    return records


def list_sleep(access_token: str, start: str, end: str) -> list:
    return _list_collection("/activity/sleep", access_token, start, end)


def list_workouts(access_token: str, start: str, end: str) -> list:
    return _list_collection("/activity/workout", access_token, start, end)


def list_recovery(access_token: str, start: str, end: str) -> list:
    return _list_collection("/recovery", access_token, start, end)
