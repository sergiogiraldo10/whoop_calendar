from typing import Optional
from urllib.parse import quote

import requests

CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def exchange_code(client_id: str, client_secret: str, code: str, redirect_uri: str) -> dict:
    res = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    res.raise_for_status()
    return res.json()


def get_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    """Google refresh tokens don't rotate, so callers just keep the access token for one run."""
    res = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )
    res.raise_for_status()
    return res.json()["access_token"]


def upsert_event(access_token: str, calendar_id: str, event: dict) -> None:
    """
    Idempotent create-or-update keyed on extendedProperties.private.whoopRecordId,
    so the Worker's webhook handler and this reconciliation job can safely
    process the same WHOOP record without creating duplicate events.
    """
    whoop_record_id = event["extendedProperties"]["private"]["whoopRecordId"]
    existing_id = _find_event_id(access_token, calendar_id, whoop_record_id)
    encoded_calendar_id = quote(calendar_id, safe="")
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    if existing_id:
        url = f"{CALENDAR_API_BASE}/calendars/{encoded_calendar_id}/events/{existing_id}"
        res = requests.patch(url, headers=headers, json=event)
    else:
        url = f"{CALENDAR_API_BASE}/calendars/{encoded_calendar_id}/events"
        res = requests.post(url, headers=headers, json=event)
    res.raise_for_status()


def _find_event_id(access_token: str, calendar_id: str, whoop_record_id: str) -> Optional[str]:
    encoded_calendar_id = quote(calendar_id, safe="")
    res = requests.get(
        f"{CALENDAR_API_BASE}/calendars/{encoded_calendar_id}/events",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"privateExtendedProperty": f"whoopRecordId={whoop_record_id}"},
    )
    res.raise_for_status()
    items = res.json().get("items", [])
    return items[0]["id"] if items else None
