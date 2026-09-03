from datetime import date, timedelta
from typing import Optional

import requests

# Same Cloudflare KV namespace as token_store.py — keys here are "steps:YYYY-MM-DD",
# written by an Apple Shortcuts automation on the phone POSTing to the Worker's
# /steps endpoint (Apple Health has no cloud API, so this is the bridge).


def _url(account_id: str, namespace_id: str, key: str) -> str:
    return (
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
        f"/storage/kv/namespaces/{namespace_id}/values/{key}"
    )


def get_steps_for_date(account_id: str, namespace_id: str, api_token: str, date_str: str) -> Optional[int]:
    res = requests.get(
        _url(account_id, namespace_id, f"steps:{date_str}"),
        headers={"Authorization": f"Bearer {api_token}"},
    )
    if res.status_code == 404:
        return None
    res.raise_for_status()
    return int(res.text.strip())


def get_trailing_average(
    account_id: str, namespace_id: str, api_token: str, end_date_str: str, days: int
) -> Optional[float]:
    """Average of whatever step data exists for the `days` days ending on end_date_str (inclusive)."""
    end_date = date.fromisoformat(end_date_str)
    values = []
    for i in range(days):
        day_str = (end_date - timedelta(days=i)).isoformat()
        steps = get_steps_for_date(account_id, namespace_id, api_token, day_str)
        if steps is not None:
            values.append(steps)
    return sum(values) / len(values) if values else None
