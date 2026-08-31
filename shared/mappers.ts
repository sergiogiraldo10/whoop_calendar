import { EVENT_COLOR, WHOOP_RECORD_ID_KEY, type WhoopSleep, type WhoopWorkout } from "./types.js";
import type { CalendarEvent } from "./calendar-client.js";

const KILOJOULE_TO_CALORIE = 4.184;

export function mapSleepToEvent(sleep: WhoopSleep): CalendarEvent {
  const score = sleep.score;
  const lines = score
    ? [
        `Performance: ${score.sleep_performance_percentage}%`,
        `Efficiency: ${score.sleep_efficiency_percentage}%`,
        `Respiratory rate: ${score.respiratory_rate.toFixed(1)} rpm`,
        `Light: ${msToHours(score.stage_summary.total_light_sleep_time_milli)}h  ` +
          `Deep: ${msToHours(score.stage_summary.total_slow_wave_sleep_time_milli)}h  ` +
          `REM: ${msToHours(score.stage_summary.total_rem_sleep_time_milli)}h`,
      ]
    : ["Sleep score not yet available"];

  return {
    summary: "Sleep",
    description: lines.join("\n"),
    start: { dateTime: sleep.start },
    end: { dateTime: sleep.end },
    colorId: EVENT_COLOR.SLEEP,
    extendedProperties: { private: { [WHOOP_RECORD_ID_KEY]: `sleep_${sleep.id}` } },
  };
}

export function mapWorkoutToEvent(workout: WhoopWorkout): CalendarEvent {
  const score = workout.score;
  const lines = score
    ? [
        `Strain: ${score.strain.toFixed(1)}`,
        `Avg HR: ${score.average_heart_rate}  Max HR: ${score.max_heart_rate}`,
        `Calories: ${Math.round(score.kilojoule / KILOJOULE_TO_CALORIE)}`,
      ]
    : ["Workout score not yet available"];

  return {
    summary: "Workout",
    description: lines.join("\n"),
    start: { dateTime: workout.start },
    end: { dateTime: workout.end },
    colorId: EVENT_COLOR.WORKOUT,
    extendedProperties: { private: { [WHOOP_RECORD_ID_KEY]: `workout_${workout.id}` } },
  };
}

function msToHours(ms: number): string {
  return (ms / 3_600_000).toFixed(1);
}
