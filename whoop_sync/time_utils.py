from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")


def ny_date_range(days_ago: int) -> tuple[str, str]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days_ago)
    return _iso(start), _iso(end)


def ny_yesterday_date() -> str:
    return (datetime.now(NY_TZ).date() - timedelta(days=1)).isoformat()


def ny_calendar_day_utc_range(date_str: str) -> tuple[str, str]:
    """UTC start/end for one America/New_York calendar day (e.g. all of "yesterday" locally)."""
    day = date.fromisoformat(date_str)
    start_local = datetime(day.year, day.month, day.day, tzinfo=NY_TZ)
    end_local = start_local + timedelta(days=1)
    return _iso(start_local.astimezone(timezone.utc)), _iso(end_local.astimezone(timezone.utc))


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")
