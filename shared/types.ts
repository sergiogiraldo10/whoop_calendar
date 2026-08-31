export interface WhoopTokens {
  access_token: string;
  refresh_token: string;
  expires_at: number; // epoch ms
}

export interface WhoopWebhookPayload {
  user_id: number;
  id: number;
  type: "workout.updated" | "sleep.updated" | "recovery.updated" | "cycle.updated";
  trace_id: string;
}

export interface WhoopSleep {
  id: number;
  cycle_id: number;
  start: string;
  end: string;
  score_state: string;
  score?: {
    sleep_performance_percentage: number;
    sleep_efficiency_percentage: number;
    respiratory_rate: number;
    stage_summary: {
      total_light_sleep_time_milli: number;
      total_slow_wave_sleep_time_milli: number;
      total_rem_sleep_time_milli: number;
    };
  };
}

export interface WhoopWorkout {
  id: number;
  start: string;
  end: string;
  sport_id: number;
  score_state: string;
  score?: {
    strain: number;
    average_heart_rate: number;
    max_heart_rate: number;
    kilojoule: number;
  };
}

export interface WhoopRecovery {
  cycle_id: number;
  score_state: string;
  score?: {
    recovery_score: number;
    resting_heart_rate: number;
    hrv_rmssd_milli: number;
  };
}

export const EVENT_COLOR = {
  SLEEP: "9", // Blueberry
  WORKOUT: "2", // Sage
} as const;

export const WHOOP_RECORD_ID_KEY = "whoopRecordId";
