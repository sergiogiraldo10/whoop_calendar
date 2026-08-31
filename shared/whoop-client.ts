import type { TokenStore } from "./token-store.js";
import type { WhoopSleep, WhoopTokens, WhoopWorkout } from "./types.js";

const API_BASE = "https://api.prod.whoop.com/developer/v2";
const TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token";

export interface WhoopCredentials {
  clientId: string;
  clientSecret: string;
}

async function refreshWhoopTokens(creds: WhoopCredentials, refreshToken: string): Promise<WhoopTokens> {
  const res = await fetch(TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: creds.clientId,
      client_secret: creds.clientSecret,
      grant_type: "refresh_token",
      refresh_token: refreshToken,
    }),
  });
  if (!res.ok) {
    throw new Error(`WHOOP token refresh failed: ${res.status} ${await res.text()}`);
  }
  const body = (await res.json()) as { access_token: string; refresh_token: string; expires_in: number };
  return {
    access_token: body.access_token,
    refresh_token: body.refresh_token,
    expires_at: Date.now() + body.expires_in * 1000,
  };
}

/**
 * Returns a valid access token, refreshing and persisting to the shared KV
 * store if expired. WHOOP refresh tokens rotate on every use — this always
 * writes the new pair back to the store immediately after refreshing. The
 * same KV namespace is also read/written by the Python reconcile/rollup jobs,
 * so this is the single source of truth that avoids a refresh race between them.
 */
export async function getValidWhoopAccessToken(store: TokenStore, creds: WhoopCredentials): Promise<string> {
  const tokens = await store.getWhoopTokens();
  if (!tokens) {
    throw new Error("No WHOOP tokens in store — run `python -m scripts.whoop_auth` first.");
  }
  const EXPIRY_SKEW_MS = 60_000;
  if (tokens.expires_at - EXPIRY_SKEW_MS > Date.now()) {
    return tokens.access_token;
  }
  const refreshed = await refreshWhoopTokens(creds, tokens.refresh_token);
  await store.setWhoopTokens(refreshed);
  return refreshed.access_token;
}

export async function verifyWebhookSignature(
  rawBody: string,
  timestamp: string,
  signature: string,
  clientSecret: string,
): Promise<boolean> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(clientSecret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const mac = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(timestamp + rawBody));
  const expected = btoa(String.fromCharCode(...new Uint8Array(mac)));
  return expected === signature;
}

async function getJson<T>(path: string, accessToken: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) {
    throw new Error(`WHOOP API request failed (${path}): ${res.status} ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

export function getSleep(id: number, accessToken: string): Promise<WhoopSleep> {
  return getJson(`/activity/sleep/${id}`, accessToken);
}

export function getWorkout(id: number, accessToken: string): Promise<WhoopWorkout> {
  return getJson(`/activity/workout/${id}`, accessToken);
}
