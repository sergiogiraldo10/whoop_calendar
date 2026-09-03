from datetime import datetime

from whoop_sync.calendar_client import get_access_token
from whoop_sync.config import load_job_config
from whoop_sync.gmail_client import send_email
from whoop_sync.steps_store import get_steps_for_date, get_trailing_average
from whoop_sync.time_utils import ny_calendar_day_utc_range, ny_date_range, ny_yesterday_date
from whoop_sync.token_store import RestKVTokenStore
from whoop_sync.whoop_client import get_valid_access_token, list_recovery, list_sleep, list_workouts

STEPS_AVERAGE_WINDOW_DAYS = 7


def main() -> None:
    config = load_job_config()
    if not config.to_email and not config.to_sms_gateway:
        print("Neither TO_EMAIL nor TO_SMS_GATEWAY set — nothing to send, skipping.")
        return

    token_store = RestKVTokenStore(config.cf_account_id, config.cf_namespace_id, config.cf_api_token)
    whoop_access_token = get_valid_access_token(token_store, config.whoop_client_id, config.whoop_client_secret)

    # "Last night's" sleep: the most recently completed sleep record, regardless
    # of exactly when the job runs relative to your wake time.
    lookback_start, lookback_end = ny_date_range(2)
    sleeps = list_sleep(whoop_access_token, lookback_start, lookback_end)
    if not sleeps:
        print("No recent sleep record found — skipping daily text.")
        return
    sleep = max(sleeps, key=lambda s: s["end"])

    recoveries = list_recovery(whoop_access_token, lookback_start, lookback_end)
    recovery = next((r for r in recoveries if r.get("cycle_id") == sleep.get("cycle_id")), None)

    yesterday = ny_yesterday_date()
    day_start, day_end = ny_calendar_day_utc_range(yesterday)
    workouts = list_workouts(whoop_access_token, day_start, day_end)

    steps = get_steps_for_date(config.cf_account_id, config.cf_namespace_id, config.cf_api_token, yesterday)
    avg_steps = get_trailing_average(
        config.cf_account_id, config.cf_namespace_id, config.cf_api_token, yesterday, STEPS_AVERAGE_WINDOW_DAYS
    )

    text = _build_text(sleep, recovery, workouts, steps, avg_steps)

    google_access_token = get_access_token(
        config.google_client_id, config.google_client_secret, config.google_refresh_token
    )
    if config.to_sms_gateway:
        send_email(google_access_token, config.to_sms_gateway, "", text)
    if config.to_email:
        send_email(google_access_token, config.to_email, "WHOOP Daily Summary", text)

    print("Daily text sent.")


def _build_text(sleep: dict, recovery: dict, workouts: list, steps, avg_steps) -> str:
    lines = []

    score = sleep.get("score")
    if score:
        stage = score["stage_summary"]
        time_asleep_ms = (
            stage["total_light_sleep_time_milli"]
            + stage["total_slow_wave_sleep_time_milli"]
            + stage["total_rem_sleep_time_milli"]
        )
        restorative_ms = stage["total_slow_wave_sleep_time_milli"] + stage["total_rem_sleep_time_milli"]
        awake_min = round(stage["total_awake_time_milli"] / 60_000)
        lines.append(f"Sleep: {_ms_to_hm(time_asleep_ms)} (score {round(score['sleep_performance_percentage'])}%)")
        lines.append(f"Restorative: {_ms_to_hm(restorative_ms)}  Awake: {awake_min}m")
    else:
        lines.append("Sleep: score not yet available")

    recovery_score = recovery["score"]["recovery_score"] if recovery and recovery.get("score") else None
    if recovery_score is not None:
        lines.append(f"Recovery: {round(recovery_score)}% ({_recovery_band(recovery_score)})")
    else:
        lines.append("Recovery: not yet available")

    total_workout_ms = sum(_duration_ms(w) for w in workouts)
    lines.append(f"Exercise: {total_workout_ms / 3_600_000:.1f}h")

    if steps is not None:
        avg_text = f" (7-day avg {round(avg_steps)})" if avg_steps is not None else ""
        lines.append(f"Steps: {steps}{avg_text}")

    return "\n".join(lines)


def _recovery_band(score: float) -> str:
    if score >= 67:
        return "Green"
    if score >= 34:
        return "Yellow"
    return "Red"


def _duration_ms(workout: dict) -> float:
    start = datetime.fromisoformat(workout["start"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(workout["end"].replace("Z", "+00:00"))
    return (end - start).total_seconds() * 1000


def _ms_to_hm(ms: float) -> str:
    total_minutes = round(ms / 60_000)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}h {minutes}m"


if __name__ == "__main__":
    main()
