KILOJOULE_TO_CALORIE = 4.184

EVENT_COLOR = {
    "SLEEP": "9",  # Blueberry
    "WORKOUT": "2",  # Sage
}


def map_sleep_to_event(sleep: dict) -> dict:
    score = sleep.get("score")
    if score:
        stage = score["stage_summary"]
        lines = [
            f"Performance: {score['sleep_performance_percentage']}%",
            f"Efficiency: {score['sleep_efficiency_percentage']}%",
            f"Respiratory rate: {score['respiratory_rate']:.1f} rpm",
            f"Light: {_ms_to_hours(stage['total_light_sleep_time_milli'])}h  "
            f"Deep: {_ms_to_hours(stage['total_slow_wave_sleep_time_milli'])}h  "
            f"REM: {_ms_to_hours(stage['total_rem_sleep_time_milli'])}h",
        ]
    else:
        lines = ["Sleep score not yet available"]

    return {
        "summary": "Sleep",
        "description": "\n".join(lines),
        "start": {"dateTime": sleep["start"]},
        "end": {"dateTime": sleep["end"]},
        "colorId": EVENT_COLOR["SLEEP"],
        "extendedProperties": {"private": {"whoopRecordId": f"sleep_{sleep['id']}"}},
    }


def map_workout_to_event(workout: dict) -> dict:
    score = workout.get("score")
    if score:
        lines = [
            f"Strain: {score['strain']:.1f}",
            f"Avg HR: {score['average_heart_rate']}  Max HR: {score['max_heart_rate']}",
            f"Calories: {round(score['kilojoule'] / KILOJOULE_TO_CALORIE)}",
        ]
    else:
        lines = ["Workout score not yet available"]

    return {
        "summary": "Workout",
        "description": "\n".join(lines),
        "start": {"dateTime": workout["start"]},
        "end": {"dateTime": workout["end"]},
        "colorId": EVENT_COLOR["WORKOUT"],
        "extendedProperties": {"private": {"whoopRecordId": f"workout_{workout['id']}"}},
    }


def _ms_to_hours(ms: float) -> str:
    return f"{ms / 3_600_000:.1f}"
