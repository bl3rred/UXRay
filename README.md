# UXRay

Read [handoff.md](/C:/Users/rfarr/Desktop/uxray/handoff.md) first before continuing work in a new session.

## Local Run

Create a root `.env.local` first. An example is provided in [.env.local.example](/C:/Users/rfarr/Desktop/uxray/.env.local.example).

`BROWSER_USE_MODEL` is the model Browser Use Cloud should use for the run. It does not mean UXRay needs your own Anthropic API key. If you omit it, the backend defaults to `claude-sonnet-4.6`.

### Frontend
```powershell
pnpm.cmd install
pnpm.cmd --dir apps/web dev
```

### Backend
```powershell
py -m pip install -r apps/api/requirements.txt
py -m uvicorn app.main:app --reload --app-dir apps/api
```

## Supabase + GitHub Sign-In Setup

The frontend now supports:
- `Sign in with GitHub` through Supabase Auth
- `Continue as guest` with session-only demo state

To activate the signed-in path, you need this from your side:

1. Create a Supabase project.
2. Copy the project URL and publishable key into `.env.local`:
```powershell
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_xxx
```
3. In Supabase, open `Authentication -> Providers -> GitHub`.
4. Copy the callback URL shown there. It will look like:
```text
https://<project-ref>.supabase.co/auth/v1/callback
```
5. In GitHub Developer Settings, create a new OAuth App:
   - Homepage URL:
     - local: `http://localhost:3000`
     - production: your Vercel domain later
   - Authorization callback URL:
     - the Supabase callback URL from step 4
6. Copy the GitHub OAuth `Client ID` and `Client Secret` into the Supabase GitHub provider config and save it.
7. In Supabase `Authentication -> URL Configuration`, set:
   - `Site URL` to your main app URL
   - additional redirect URLs for local and Vercel preview flows

Important:
- The GitHub `Client ID` in Supabase must be the actual OAuth App client ID from GitHub, not your email address.
- If GitHub sends you to a 404 and the authorize URL contains `client_id=<your-email>`, your Supabase GitHub provider config is wrong.
- The GitHub OAuth App callback URL must be the Supabase callback URL, not your Next.js `/auth/callback` route.

Recommended redirect URLs:
```text
http://localhost:3000/**
https://<your-production-domain>/**
https://*-<your-vercel-team-or-account>.vercel.app/**
```

The app-side PKCE callback route is `/auth/callback`. Supabase handles the provider callback, and the Next.js route completes the session exchange.

If you do not configure Supabase yet, the app still works in guest mode.

Current persistence behavior:
- GitHub login itself does not require any custom app table in Supabase.
- Signed-in UXRay data is now scoped to the authenticated Supabase user on the backend, while guest data stays tied to the guest session header.
- If you want to prepare the equivalent user-owned schema in Supabase Postgres for the later migration off local SQLite, use [user_owned_projects_runs.sql](/C:/Users/rfarr/Desktop/uxray/supabase/sql/user_owned_projects_runs.sql).

## Git setup notes

- This repo stores text files with LF in git. On Windows, Git may warn that `LF will be replaced by CRLF`; that warning is expected and does not block staging by itself.
- The real publish blocker is generated runtime output. Keep repo-builder smoke output untracked, especially anything under `apps/api/data/manual-repo-build-test/`.
- If `git add .` fails, check for accidentally generated runtime folders before changing line-ending settings.

## Durable Screenshot / Artifact Storage

For more reliable demo persistence across login/logout and backend restarts, you can store audit screenshots in a public Supabase Storage bucket instead of only relying on local backend files.

1. Run [public_artifacts_bucket.sql](/C:/Users/rfarr/Desktop/uxray/supabase/sql/public_artifacts_bucket.sql) in the Supabase SQL editor.
2. Add these backend-only env vars to the root `.env.local`:
```powershell
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>
SUPABASE_STORAGE_BUCKET=uxray-artifacts
```
3. Restart the FastAPI backend.

Behavior:
- when storage is configured, persisted Browser Use screenshots/artifacts are uploaded to the Supabase bucket and saved as public URLs
- if storage upload fails or is not configured, UXRay falls back to the local artifact directory so audits still complete

## Vercel-Friendly Frontend

The frontend is set up so you can deploy it to Vercel without also hosting the backend immediately.

- If the backend is reachable, the app uses the real API.
- If the backend is not reachable and the user continues as guest, the app falls back to seeded demo data.
- Signed-in flows still render, but real audits require the backend.

Important: a Vercel-hosted frontend cannot call `http://127.0.0.1:8000` on your machine for judges. Their browser would try to call their own localhost, not yours. For a live demo, point `NEXT_PUBLIC_API_BASE_URL` at a temporary public tunnel to your local FastAPI server.

Example:
```powershell
cloudflared tunnel --url http://localhost:8000
```

Then set:
```powershell
NEXT_PUBLIC_API_BASE_URL=https://<your-tunnel-subdomain>.trycloudflare.com
```

For local-only development you can still keep:
```powershell
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## Project Inputs

Projects can currently be created from:
- a website URL
- an optional public repository URL

GitHub account connection is optional. It is for durable account history and later repo-linked code change workflows, not for the core audit path.

## Browser Use docs

Start with Browser Use Cloud's docs index:
- `https://docs.browser-use.com/cloud/llms.txt`
- `https://docs.browser-use.com/cloud/llms-full.txt`

## Fetch.ai setup

The backend has a dedicated evaluation boundary after analyzer findings are produced, and the preferred path is now a **hosted Agentverse orchestrator plus a local mailbox relay**, not seven local terminals.

Use Python `3.11` or `3.12` for `apps/fetch`. Current `uagents` releases are not reliable on Python `3.14`.

Hosted setup docs:
- [apps/fetch/HOSTED_SETUP.md](/C:/Users/rfarr/Desktop/uxray/apps/fetch/HOSTED_SETUP.md)
- [apps/fetch/hosted_templates](/C:/Users/rfarr/Desktop/uxray/apps/fetch/hosted_templates)

To wire the existing backend into the hosted orchestrator, run the local relay and set:
```powershell
FETCH_EVALUATION_ENABLED=true
FETCH_EVALUATION_AGENT_URL=http://127.0.0.1:8100/evaluate
FETCH_EVALUATION_API_KEY=<local-shared-secret>
FETCH_EVALUATION_TIMEOUT_SECONDS=20
AGENTVERSE_API_KEY=<your-agentverse-api-key>
FETCH_RELAY_AGENT_ADDRESS=<your-relay-agent1-address>
FETCH_RELAY_ORCHESTRATOR_ADDRESS=<your-hosted-orchestrator-address>
ASI_ONE_API_KEY=<optional-for-demo-chat>
```

Relay command:
```powershell
py apps/fetch/run_relay.py
```

Hosted Fetch requires two local processes:
1. the mailbox-connected relay agent from `py -m uxray_fetch.relay_agent`
2. the local HTTP relay from `py apps/fetch/run_relay.py`

Before trusting the hosted path, confirm the configured `FETCH_RELAY_AGENT_ADDRESS` shows as active in Agentverse. If that mailbox relay agent is inactive, UXRay will now skip the long wait and fall back to the ASI path instead of timing out blindly.

Relay mailbox agent setup:
```powershell
Set-Location apps/fetch
py -m uxray_fetch.relay_agent
```

Use [apps/fetch/README.md](/C:/Users/rfarr/Desktop/uxray/apps/fetch/README.md) for the hosted-first overview. The old local mailbox runner setup is now a legacy fallback only.

Until those are configured, runs will complete normally and mark the Fetch.ai evaluation stage as `skipped`.

## Tunnel for local demo targets

Browser Use Cloud cannot audit `localhost` directly. Use a public URL or expose the app you want to audit:

```powershell
cloudflared tunnel --url http://localhost:3000
```

Then create the UXRay project with the tunneled URL.

## Hosted frontend demo mode

If you deploy the frontend to Vercel without exposing the backend publicly, the app can still be explored in guest mode with seeded demo data. Signed-in sessions can still work if Supabase is configured, but real audits still require your local backend to be reachable from the frontend, typically through a temporary tunnel during the live demo.
