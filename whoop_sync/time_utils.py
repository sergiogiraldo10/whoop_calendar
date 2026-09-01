from datetime import datetime, timedelta, timezone


def ny_date_range(days_ago: int) -> tuple[str, str]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days_ago)
    return _iso(start), _iso(end)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")
