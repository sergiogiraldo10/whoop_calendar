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
  STEPS_INGEST_SECRET: string;
}

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const path = new URL(request.url).pathname;

    if (request.method === "POST" && path === "/steps") {
      return handleStepsIngest(request, env);
    }

    if (request.method !== "POST" || path !== "/webhook") {
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

/** Called by an Apple Shortcuts personal automation on the phone — not by WHOOP or Google. */
async function handleStepsIngest(request: Request, env: Env): Promise<Response> {
  if (request.headers.get("X-Steps-Secret") !== env.STEPS_INGEST_SECRET) {
    return new Response("Unauthorized", { status: 401 });
  }

  const body = (await request.json()) as { date?: string; steps?: number };
  if (!body.date || !DATE_RE.test(body.date) || typeof body.steps !== "number") {
    return new Response("Expected JSON body { date: 'YYYY-MM-DD', steps: number }", { status: 400 });
  }

  await env.WHOOP_TOKENS.put(`steps:${body.date}`, String(Math.round(body.steps)));
  return new Response("ok", { status: 200 });
}

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
