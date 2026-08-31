from whoop_sync.calendar_client import get_access_token, upsert_event
from whoop_sync.config import load_job_config
from whoop_sync.mappers import map_sleep_to_event, map_workout_to_event
from whoop_sync.time_utils import is_target_local_hour, ny_date_range
from whoop_sync.token_store import RestKVTokenStore
from whoop_sync.whoop_client import get_valid_access_token, list_sleep, list_workouts

TARGET_HOUR = 11  # 11:00 America/New_York


def main() -> None:
    if not is_target_local_hour(TARGET_HOUR):
        print("Not the active DST cron slot for 11:00 America/New_York — skipping.")
        return

    config = load_job_config()
    token_store = RestKVTokenStore(config.cf_account_id, config.cf_namespace_id, config.cf_api_token)

    whoop_access_token = get_valid_access_token(token_store, config.whoop_client_id, config.whoop_client_secret)
    google_access_token = get_access_token(
        config.google_client_id, config.google_client_secret, config.google_refresh_token
    )

    # Look back 3 days so a webhook outage doesn't leave a permanent gap.
    start, end = ny_date_range(3)
    sleeps = list_sleep(whoop_access_token, start, end)
    workouts = list_workouts(whoop_access_token, start, end)

    for sleep in sleeps:
        upsert_event(google_access_token, config.calendar_id, map_sleep_to_event(sleep))
    for workout in workouts:
        upsert_event(google_access_token, config.calendar_id, map_workout_to_event(workout))

    print(f"Reconciled {len(sleeps)} sleep record(s) and {len(workouts)} workout record(s).")


if __name__ == "__main__":
    main()
