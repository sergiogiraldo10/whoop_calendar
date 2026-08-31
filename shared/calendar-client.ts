const CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3";
const GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token";

export interface CalendarEvent {
  summary: string;
  description: string;
  start: { dateTime: string };
  end: { dateTime: string };
  colorId: string;
  extendedProperties: { private: Record<string, string> };
}

export interface GoogleCredentials {
  clientId: string;
  clientSecret: string;
}

/** Google refresh tokens don't rotate, so callers just cache the access token in memory per run. */
export async function getGoogleAccessToken(creds: GoogleCredentials, refreshToken: string): Promise<string> {
  const res = await fetch(GOOGLE_TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: creds.clientId,
      client_secret: creds.clientSecret,
      refresh_token: refreshToken,
      grant_type: "refresh_token",
    }),
  });
  if (!res.ok) {
    throw new Error(`Google token refresh failed: ${res.status} ${await res.text()}`);
  }
  const body = (await res.json()) as { access_token: string };
  return body.access_token;
}

/**
 * Idempotent create-or-update keyed on extendedProperties.private.whoopRecordId,
 * so the webhook handler and the daily reconciliation job can safely process
 * the same WHOOP record without creating duplicate events.
 */
export async function upsertEvent(
  accessToken: string,
  calendarId: string,
  event: CalendarEvent,
): Promise<void> {
  const whoopRecordId = event.extendedProperties.private.whoopRecordId;
  const existingId = await findEventIdByWhoopRecordId(accessToken, calendarId, whoopRecordId);

  const url = existingId
    ? `${CALENDAR_API_BASE}/calendars/${encodeURIComponent(calendarId)}/events/${existingId}`
    : `${CALENDAR_API_BASE}/calendars/${encodeURIComponent(calendarId)}/events`;

  const res = await fetch(url, {
    method: existingId ? "PATCH" : "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(event),
  });
  if (!res.ok) {
    throw new Error(`Calendar upsert failed: ${res.status} ${await res.text()}`);
  }
}

async function findEventIdByWhoopRecordId(
  accessToken: string,
  calendarId: string,
  whoopRecordId: string,
): Promise<string | null> {
  const params = new URLSearchParams({
    privateExtendedProperty: `whoopRecordId=${whoopRecordId}`,
  });
  const res = await fetch(`${CALENDAR_API_BASE}/calendars/${encodeURIComponent(calendarId)}/events?${params}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) {
    throw new Error(`Calendar lookup failed: ${res.status} ${await res.text()}`);
  }
  const body = (await res.json()) as { items: { id: string }[] };
  return body.items[0]?.id ?? null;
}
