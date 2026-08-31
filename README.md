# WHOOP → Google Calendar sync

Syncs WHOOP sleep and workout data into your existing Google Calendar (color-coded via
`colorId`, no secondary calendars) in near-real-time via a WHOOP webhook, backstopped by
a daily reconciliation job, plus a weekly email rollup of recovery/sleep/strain averages.

- **Sleep events** → Blueberry (colorId 9)
- **Workout events** → Sage (colorId 2), matching the existing workout color already used
  on the calendar

## Architecture

This repo mixes two runtimes for a reason: Cloudflare Workers are JS/TS-native (Python on
Workers is beta/Pyodide-based with real limitations), while the scheduled jobs have no such
constraint, so they're Python.

- **`worker/`** (TypeScript) — Cloudflare Worker that receives WHOOP's webhook, verifies its
  HMAC signature, and upserts the corresponding calendar event. Its own copy of the client
  logic lives in `shared/`.
- **`whoop_sync/`** (Python) — WHOOP client, Google Calendar/Gmail clients, mappers, token
  store — imported by the two jobs and the auth scripts below.
- **`jobs/`** (Python) — `reconcile.py` (daily 11am ET, backstops missed webhooks over the
  last 3 days) and `weekly_rollup.py` (weekly averages emailed, plus optional SMS), both run
  via GitHub Actions cron.
- **`scripts/`** (Python) — one-time interactive OAuth setup, run locally only.

Both the Worker and the Python jobs refresh WHOOP's access token, and WHOOP's refresh token
**rotates on every use**. To avoid a race between the two refreshing independently, both
read/write the same Cloudflare KV namespace as the single source of truth (the Worker via its
native KV binding in `shared/token-store.ts`, the jobs via Cloudflare's REST API in
`whoop_sync/token_store.py` — same KV key, `whoop_tokens`, so either side can pick up a token
pair the other just wrote).

Every calendar event is tagged with `extendedProperties.private.whoopRecordId`; upserts look
this up first and patch instead of insert, so the webhook and the reconciliation job can
safely process the same WHOOP record without creating duplicates.

## One-time setup

1. **WHOOP developer app** — create one at developer.whoop.com. Note the client ID/secret.
   Set its redirect URI to `http://localhost:8787/callback` (matches `.env`'s default).

2. **Google Cloud OAuth client** — create one in Google Cloud Console with the
   `https://www.googleapis.com/auth/calendar.events` and `https://www.googleapis.com/auth/gmail.send`
   scopes (narrowest ones that cover everything this app does — no need for the broader
   `.../auth/calendar` scope since we never touch calendar-level settings, only events).
   **Publish the OAuth consent screen to "Production"** — if left in "Testing", Google
   expires the refresh token after 7 days. Redirect URI: `http://localhost:8788/callback`.

3. **Cloudflare account** — create a KV namespace (`wrangler kv namespace create WHOOP_TOKENS`)
   and a scoped API token with KV read/write permission on that namespace. Put the
   namespace ID into `worker/wrangler.toml` and into your `.env`/GitHub secrets as
   `CF_KV_NAMESPACE_ID`.

4. Copy `.env.example` to `.env` and fill in everything you have so far.

5. **Install the Python dependencies** and **run the WHOOP auth script** (writes the initial
   token pair straight into Cloudflare KV):
   ```
   python -m venv .venv && .venv\Scripts\activate   # or source .venv/bin/activate on macOS/Linux
   pip install -r requirements.txt
   python -m scripts.whoop_auth
   ```

6. **Run the Google auth script** (prints a refresh token — this one you store yourself,
   it doesn't rotate):
   ```
   python -m scripts.google_auth
   ```
   Save the printed refresh token as `GOOGLE_REFRESH_TOKEN` in `.env`.

7. **Set GitHub Actions secrets** (repo Settings → Secrets and variables → Actions):
   `WHOOP_CLIENT_ID`, `WHOOP_CLIENT_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
   `GOOGLE_REFRESH_TOKEN`, `CF_ACCOUNT_ID`, `CF_API_TOKEN`, `CF_KV_NAMESPACE_ID`,
   `TO_EMAIL`, optionally `TO_SMS_GATEWAY` (a carrier email-to-SMS address, e.g.
   `5551234567@tmomail.net` — note some carriers, e.g. T-Mobile, have discontinued this).
   Also set the `CALENDAR_ID` repo **variable** (not secret) — use `primary` for your main
   calendar.

8. **Deploy the Worker** (Node + wrangler, only needed for this step):
   ```
   npm install
   npx wrangler secret put WHOOP_CLIENT_ID --config worker/wrangler.toml
   npx wrangler secret put WHOOP_CLIENT_SECRET --config worker/wrangler.toml
   npx wrangler secret put GOOGLE_CLIENT_ID --config worker/wrangler.toml
   npx wrangler secret put GOOGLE_CLIENT_SECRET --config worker/wrangler.toml
   npx wrangler secret put GOOGLE_REFRESH_TOKEN --config worker/wrangler.toml
   npm run worker:deploy
   ```
   Note the deployed URL.

9. **Register the WHOOP webhook** pointing at `<worker-url>/webhook`, subscribed to
   `sleep.updated` and `workout.updated`, in your WHOOP developer app settings.

10. GitHub Actions workflows (`reconcile.yml`, `weekly-rollup.yml`) run automatically on
    their cron schedules once the secrets above are set — no further action needed.

## Local development

- `npm run worker:dev` — run the Worker locally with `wrangler dev` (uses `.dev.vars` for
  secrets, not `.env`).
- `npm run typecheck` — type-check the Worker and `shared/`.
- `python -m jobs.reconcile` / `python -m jobs.weekly_rollup` — run a job once locally
  (automatically reads `.env` via `python-dotenv`).
