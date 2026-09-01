from datetime import datetime

from whoop_sync.calendar_client import get_access_token
from whoop_sync.config import load_job_config
from whoop_sync.gmail_client import send_email
from whoop_sync.rollup_state import already_sent_this_week, mark_sent
from whoop_sync.time_utils import ny_date_range
from whoop_sync.token_store import RestKVTokenStore
from whoop_sync.whoop_client import get_valid_access_token, list_recovery, list_sleep, list_workouts

KILOJOULE_TO_CALORIE = 4.184


def _average(values: list) -> float:
    return sum(values) / len(values) if values else 0.0


def main() -> None:
    config = load_job_config()
    if not config.to_email:
        print("TO_EMAIL not set — nothing to send, skipping.")
        return

    # Two cron triggers a day cover both DST offsets, and GitHub can delay a
    # scheduled run by hours, so we can't gate on wall-clock time like
    # reconcile.py's idempotent upsert doesn't need to. Sending email/SMS is a
    # real side effect, so dedup on "already sent this week" instead.
    if already_sent_this_week(config.cf_account_id, config.cf_namespace_id, config.cf_api_token):
        print("Already sent this week's rollup — skipping.")
        return

    token_store = RestKVTokenStore(config.cf_account_id, config.cf_namespace_id, config.cf_api_token)
    whoop_access_token = get_valid_access_token(token_store, config.whoop_client_id, config.whoop_client_secret)

    start, end = ny_date_range(7)
    sleeps = list_sleep(whoop_access_token, start, end)
    workouts = list_workouts(whoop_access_token, start, end)
    recoveries = list_recovery(whoop_access_token, start, end)

    scored_recoveries = [r for r in recoveries if r.get("score")]
    avg_recovery = _average([r["score"]["recovery_score"] for r in scored_recoveries])
    avg_resting_hr = _average([r["score"]["resting_heart_rate"] for r in scored_recoveries])
    avg_hrv = _average([r["score"]["hrv_rmssd_milli"] for r in scored_recoveries])

    scored_sleeps = [s for s in sleeps if s.get("score")]
    avg_sleep_perf = _average([s["score"]["sleep_performance_percentage"] for s in scored_sleeps])

    scored_workouts = [w for w in workouts if w.get("score")]
    total_strain = sum(w["score"]["strain"] for w in scored_workouts)
    total_calories = round(sum(w["score"]["kilojoule"] for w in scored_workouts) / KILOJOULE_TO_CALORIE)

    summary_lines = [
        f"Week of {_fmt_date(start)} - {_fmt_date(end)}",
        "",
        f"Avg recovery: {avg_recovery:.1f}%",
        f"Avg resting HR: {avg_resting_hr:.1f} bpm",
        f"Avg HRV: {avg_hrv:.1f} ms",
        f"Avg sleep performance: {avg_sleep_perf:.1f}%",
        "",
        f"Workouts: {len(workouts)}  Total strain: {total_strain:.1f}  Total calories: {total_calories}",
    ]
    summary_text = "\n".join(summary_lines)

    google_access_token = get_access_token(
        config.google_client_id, config.google_client_secret, config.google_refresh_token
    )
    send_email(google_access_token, config.to_email, "WHOOP Weekly Rollup", summary_text)

    if config.to_sms_gateway:
        sms_text = f"WHOOP week: recovery {avg_recovery:.1f}%, sleep {avg_sleep_perf:.1f}%, {len(workouts)} workouts"
        send_email(google_access_token, config.to_sms_gateway, "", sms_text)

    mark_sent(config.cf_account_id, config.cf_namespace_id, config.cf_api_token)
    print("Weekly rollup sent.")


def _fmt_date(iso_str: str) -> str:
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).strftime("%m/%d/%Y")


if __name__ == "__main__":
    main()
