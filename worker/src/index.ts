import { getGoogleAccessToken, upsertEvent } from "../../shared/calendar-client.js";
import { mapSleepToEvent, mapWorkoutToEvent } from "../../shared/mappers.js";
import { WorkerKVTokenStore } from "../../shared/token-store.js";
import type { WhoopWebhookPayload } from "../../shared/types.js";
import { getSleep, getValidWhoopAccessToken, getWorkout, verifyWebhookSignature } from "../../shared/whoop-client.js";

export interface Env {
  WHOOP_TOKENS: KVNamespace;
  WHOOP_CLIENT_ID: string;
  WHOOP_CLIENT_SECRET: string;
  GOOGLE_CLIENT_ID: string;
  GOOGLE_CLIENT_SECRET: string;
  GOOGLE_REFRESH_TOKEN: string;
  CALENDAR_ID: string;
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    if (request.method !== "POST" || new URL(request.url).pathname !== "/webhook") {
      return new Response("Not found", { status: 404 });
    }

    const rawBody = await request.text();
    const signature = request.headers.get("X-WHOOP-Signature") ?? "";
    const timestamp = request.headers.get("X-WHOOP-Signature-Timestamp") ?? "";

    const valid = await verifyWebhookSignature(rawBody, timestamp, signature, env.WHOOP_CLIENT_SECRET);
    if (!valid) {
      return new Response("Invalid signature", { status: 401 });
    }

    const payload = JSON.parse(rawBody) as WhoopWebhookPayload;

    // Ack immediately — WHOOP expects a fast response — and do the real work after.
    ctx.waitUntil(processWebhook(payload, env));
    return new Response("ok", { status: 200 });
  },
};

async function processWebhook(payload: WhoopWebhookPayload, env: Env): Promise<void> {
  if (payload.type !== "sleep.updated" && payload.type !== "workout.updated") {
    return;
  }

  const tokenStore = new WorkerKVTokenStore(env.WHOOP_TOKENS);
  const whoopAccessToken = await getValidWhoopAccessToken(tokenStore, {
    clientId: env.WHOOP_CLIENT_ID,
    clientSecret: env.WHOOP_CLIENT_SECRET,
  });

  const event =
    payload.type === "sleep.updated"
      ? mapSleepToEvent(await getSleep(payload.id, whoopAccessToken))
      : mapWorkoutToEvent(await getWorkout(payload.id, whoopAccessToken));

  const googleAccessToken = await getGoogleAccessToken(
    { clientId: env.GOOGLE_CLIENT_ID, clientSecret: env.GOOGLE_CLIENT_SECRET },
    env.GOOGLE_REFRESH_TOKEN,
  );

  await upsertEvent(googleAccessToken, env.CALENDAR_ID, event);
}
