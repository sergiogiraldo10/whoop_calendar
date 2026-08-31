from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def is_target_local_hour(target_hour: int, tz_name: str = "America/New_York") -> bool:
    """
    GitHub Actions cron is UTC-only and doesn't shift for daylight saving, but
    the target run time (11:00 America/New_York) does. The workflow schedules
    two UTC cron triggers (one for EST, one for EDT); this guard lets only the
    one that currently matches New York's actual offset proceed, so we don't
    double-run around the DST boundary.
    """
    now = datetime.now(ZoneInfo(tz_name))
    return now.hour == target_hour


def ny_date_range(days_ago: int) -> tuple[str, str]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days_ago)
    return _iso(start), _iso(end)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")
