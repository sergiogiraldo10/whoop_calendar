# WHOOP → Google Calendar sync

Syncs WHOOP sleep and workout data into your existing Google Calendar (color-coded via
`colorId`, no secondary calendars), backstopped by a daily reconciliation job (real-time
webhook sync is built but not yet registered — see step 9), plus a daily text summary and a
weekly email rollup.

- **Sleep events** → Blueberry (colorId 9)
- **Workout events** → Sage (colorId 2), title includes the sport when known (e.g. "Workout
  (Pickleball)")

## Architecture

This repo mixes two runtimes for a reason: Cloudflare Workers are JS/TS-native (Python on
Workers is beta/Pyodide-based with real limitations), while the scheduled jobs have no such
constraint, so they're Python.

- **`worker/`** (TypeScript) — Cloudflare Worker with two routes:
  - `POST /webhook` — receives WHOOP's webhook, verifies its HMAC signature, upserts the
    corresponding calendar event.
  - `POST /steps` — receives daily step counts from an Apple Shortcuts automation on your
    phone (Apple Health has no cloud API, so this is the bridge), authenticated via a shared
    secret header, stored in the same KV namespace as the WHOOP tokens.
  - Its own copy of the client logic lives in `shared/`.
- **`whoop_sync/`** (Python) — WHOOP client, Google Calendar/Gmail clients, mappers, token
  store, steps store — imported by the jobs and auth scripts below.
- **`jobs/`** (Python), each run via GitHub Actions cron:
  - `reconcile.py` — backstops missed webhooks by re-syncing the last 3 days of WHOOP data
    to the calendar. Idempotent, so it's harmless to run on any schedule.
  - `daily_text.py` — emails a summary of last night's sleep (time asleep, restorative sleep,
    minutes awake, sleep score), recovery score with its green/yellow/red band, hours
    exercised, and yesterday's steps vs. a trailing 7-day average (steps only appear once the
    Apple Shortcut is set up).
  - `weekly_rollup.py` — weekly averages (recovery, sleep, strain) emailed, deduped via a
    "last sent" marker in Cloudflare KV so GitHub's scheduling delays can't cause a double-send.
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

**Design lesson learned the hard way**: none of the scheduled jobs gate their behavior on the
wall-clock time at execution — GitHub Actions can delay a scheduled run by hours, so checking
"is it currently 11am?" inside the job silently skips real work when a run lands late. Instead,
`reconcile.py` relies on its upsert being idempotent (safe to run anytime), and
`weekly_rollup.py`/future non-idempotent jobs dedup via state stored in Cloudflare KV, not time.

## One-time setup

1. **WHOOP developer app** — create one at developer.whoop.com. Note the client ID/secret, and
   under the app's scope settings enable `read:recovery`, `read:cycles`, `read:sleep`,
   `read:workout`, `read:profile`, `offline` (WHOOP rejects requesting a scope that isn't
   explicitly enabled on the app). Set its redirect URI to match whatever you put in
   `WHOOP_REDIRECT_URI` below.

2. **Google Cloud OAuth client** — create one in Google Cloud Console with the
   `https://www.googleapis.com/auth/calendar.events` and `https://www.googleapis.com/auth/gmail.send`
   scopes (narrowest ones that cover everything this app does — no need for the broader
   `.../auth/calendar` scope since we never touch calendar-level settings, only events).
   **Publish the OAuth consent screen to "Production"** — if left in "Testing", Google
   expires the refresh token after 7 days. Application type must be **Web application** (not
   Desktop/Android/iOS — those don't issue a client secret). Redirect URI:
   `http://localhost:8788/callback`. If your Google account is on a Workspace org whose admin
   blocks OAuth client secret generation (common on school/work accounts), create this Cloud
   project under a personal Google account instead — the app registration and the account that
   grants consent are independent, so you still authorize it against your real account when
   you run the auth script in step 6.

3. **Cloudflare account** — create a KV namespace (`wrangler kv namespace create WHOOP_TOKENS`)
   and an API token. It needs two permissions on your account: **Workers KV Storage → Edit**
   (used by the Python jobs) and **Workers Scripts → Edit** (needed to deploy the Worker and
   set its secrets in step 8). Put the namespace ID into `worker/wrangler.toml` and into your
   `.env`/GitHub secrets as `CF_KV_NAMESPACE_ID`.

4. Copy `.env.example` to `.env` and fill in everything you have so far, plus make up a random
   value for `STEPS_INGEST_SECRET` (any long random string — it's just a shared password
   between the Worker and your Apple Shortcut, not tied to any account).

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

7. **Set GitHub Actions secrets** (repo Settings → Secrets and variables → Actions → Secrets
   tab): `WHOOP_CLIENT_ID`, `WHOOP_CLIENT_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
   `GOOGLE_REFRESH_TOKEN`, `CF_ACCOUNT_ID`, `CF_API_TOKEN`, `CF_KV_NAMESPACE_ID`, `TO_EMAIL`.
   Also set the `CALENDAR_ID` repo **variable** (Variables tab, not Secrets) — use `primary`
   for your main calendar. Don't use the separate "Environments" feature — these all need to
   be plain repository-level secrets/variables, since the workflows don't declare an environment.

8. **Deploy the Worker** (Node + wrangler, only needed for this step):
   ```
   npm install
   npx wrangler secret put WHOOP_CLIENT_ID --config worker/wrangler.toml
   npx wrangler secret put WHOOP_CLIENT_SECRET --config worker/wrangler.toml
   npx wrangler secret put GOOGLE_CLIENT_ID --config worker/wrangler.toml
   npx wrangler secret put GOOGLE_CLIENT_SECRET --config worker/wrangler.toml
   npx wrangler secret put GOOGLE_REFRESH_TOKEN --config worker/wrangler.toml
   npx wrangler secret put STEPS_INGEST_SECRET --config worker/wrangler.toml
   npm run worker:deploy
   ```
   Note the deployed URL (looks like `https://whoop-calendar-sync.<your-subdomain>.workers.dev`).

9. **Register the WHOOP webhook** pointing at `<worker-url>/webhook`, subscribed to
   `sleep.updated` and `workout.updated`, in your WHOOP developer app settings. Until this is
   done, syncing still works via `reconcile.py`'s cron schedule, just not in near-real-time.

10. **Set up the Apple Shortcut** for step data (see "Apple Shortcuts setup" below). Optional —
    `daily_text.py` runs fine without it, it just omits the steps line.

11. GitHub Actions workflows (`reconcile.yml`, `daily-text.yml`, `weekly-rollup.yml`) run
    automatically on their cron schedules once the secrets above are set — no further action
    needed. Current schedule: `reconcile` and `daily-text` run Tue–Thu 8:15am ET, every other
    day 11am ET; `weekly-rollup` runs Monday ~11am ET. All times are approximate — GitHub can
    delay scheduled runs by hours.

## Apple Shortcuts setup (for step data)

Apple Health has no cloud API, so step data is bridged via a Shortcuts personal automation
that POSTs to the Worker's `/steps` endpoint once a day.

Build a new Shortcut:

1. **Date** — Current Date
2. **Adjust Date** — Subtract 1 Day (this is "yesterday," still carrying today's time-of-day)
3. **Format Date** — Custom format `yyyy-MM-dd`, on the result of step 2 — gives a text string
   like `2026-09-02`. Reused in steps 4 and 8.
4. **Date** — input the text variable from step 3 (converting a plain date string back into a
   Date this way gives midnight of that day) — this is your **start date**.
5. **Adjust Date** — Add 1 Day to the result of step 4 — midnight of *today*, your **end date**.
6. **Find Health Samples** — Sample Type: `Steps`, Filter: **Start Date** → **is in between**
   → the start date (4) and end date (5).
7. **Calculate Statistics** — Operation: `Sum`, on the results of step 6 — yesterday's total steps.
8. **Get Contents of URL**:
   - URL: `<your worker URL>/steps`
   - Method: `POST`
   - Headers: `X-Steps-Secret` → your `STEPS_INGEST_SECRET` value; `Content-Type` → `application/json`
   - Request Body (JSON): `date` → text variable from step 3, `steps` → sum from step 7 (as Number)

Then: Automation tab → **+** → **Create Personal Automation** → **Time of Day** → early
morning, Daily → select this Shortcut → turn **off** "Ask Before Running" so it runs silently.

## Local development

- `npm run worker:dev` — run the Worker locally with `wrangler dev` (uses `.dev.vars` for
  secrets, not `.env`).
- `npm run typecheck` — type-check the Worker and `shared/`.
- `python -m jobs.reconcile` / `python -m jobs.daily_text` / `python -m jobs.weekly_rollup` —
  run a job once locally (automatically reads `.env` via `python-dotenv`).
