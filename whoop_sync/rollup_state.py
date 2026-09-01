from datetime import datetime, timezone

import requests

# Separate KV entry from token_store.py's "whoop_tokens" — tracks when the
# weekly rollup email last went out, so a GitHub Actions scheduling delay that
# pushes both DST-covering cron triggers into the same day can't send it twice.
KV_KEY = "weekly_rollup_last_sent"
MIN_DAYS_BETWEEN_SENDS = 6


def _url(account_id: str, namespace_id: str) -> str:
    return (
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
        f"/storage/kv/namespaces/{namespace_id}/values/{KV_KEY}"
    )


def already_sent_this_week(account_id: str, namespace_id: str, api_token: str) -> bool:
    res = requests.get(_url(account_id, namespace_id), headers={"Authorization": f"Bearer {api_token}"})
    if res.status_code == 404:
        return False
    res.raise_for_status()
    last_sent = datetime.fromisoformat(res.text.strip())
    return (datetime.now(timezone.utc) - last_sent).days < MIN_DAYS_BETWEEN_SENDS


def mark_sent(account_id: str, namespace_id: str, api_token: str) -> None:
    res = requests.put(
        _url(account_id, namespace_id),
        headers={"Authorization": f"Bearer {api_token}"},
        data=datetime.now(timezone.utc).isoformat(),
    )
    res.raise_for_status()
