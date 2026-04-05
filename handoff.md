# UXRay Handoff

## Current Status
Base infrastructure is live under `apps/web` and `apps/api`. The app supports local frontend and backend startup, project creation, persisted SQLite-backed runs, a real Browser Use worker path, polling-based run updates, and a run detail view with analyzer-generated issues, recommendations, artifacts, Browser Use model metadata, and a Fetch.ai evaluation boundary that can call a local orchestrator hook. A sponsor-track Fetch agent scaffold lives in `apps/fetch`. The frontend now also supports GitHub sign-in via Supabase, guest mode, and a seeded demo fallback when the backend is unreachable.

## What Was Completed This Session
- Added a FastAPI backend with project and run endpoints plus local SQLite persistence
- Added an in-process worker that dequeues runs and executes Browser Use audits
- Added a first-pass analyzer that turns Browser Use observations into issues and recommendations
- Added per-run Browser Use model persistence and evaluation status tracking
- Added a Fetch.ai evaluation service boundary that can call a local relay through a shared-secret REST contract
- Added a standalone `apps/fetch` Python app with:
  - shared issue/review/synthesis models
  - legacy local mailbox-first uAgents scaffold
  - hosted Agentverse templates for orchestrator, audience agents, boss, and synthesis
  - a local relay that will target the hosted orchestrator through Agentverse mailbox APIs
  - hosted setup guide for Agentverse + ASI:One deployment
- Added a Next.js frontend with landing page, dashboard, project view, run list, and run detail view
- Added frontend auth plumbing for:
  - Supabase GitHub sign-in
  - guest mode
  - SSR-safe Supabase callback and middleware wiring
  - seeded demo fallback data for Vercel-friendly guest exploration
- Updated project creation UX to treat public repo URLs as optional input and GitHub repo connection as future and optional
- Updated `.gitignore` to exclude local editor, agent, env, runtime, and generated files before pushing to GitHub
- Added backend tests and frontend component tests
- Added root setup docs and `.env.local.example`

## In Progress
- Browser Use prompt/output shape is intentionally narrow and will need iteration once real target sites are exercised
- Artifacts currently store external/live URLs rather than a full local ingestion pipeline
- The hosted Fetch templates are in place, but they still need to be created in Agentverse and wired with live agent addresses and secrets
- The hosted orchestrator no longer exposes `/evaluate`; backend-triggered evaluation now goes through the local relay and mailbox transport
- The frontend is not yet consuming the Fetch WebSocket bridge
- Signed-in frontend auth is wired, but backend persistence is still local SQLite and not yet user-scoped in Supabase/Postgres
- GitHub repo connection is still optional/future; current project records support public repo URLs but not connected repo installs yet

## Blockers
- Browser Use Cloud cannot audit `localhost` directly; local demos need a public tunnel URL
- A Vercel-hosted frontend cannot call your localhost backend directly for other users; live demos need a temporary public tunnel to FastAPI
- Future repo-linked fixes still require auth, GitHub repo access, and the later recommendation layer
- Real hosted Fetch.ai orchestration requires the hosted specialist agents, hosted orchestrator, relay agent identity, and local relay before backend-triggered evaluation works
- This machine only has Python `3.14`, and `uagents 0.24.0` failed here with a Pydantic compatibility error; use Python `3.11` or `3.12` for `apps/fetch`

## Next Priorities
1. Move durable signed-in persistence from local SQLite to Supabase/Postgres and scope projects/runs by authenticated user
2. Add optional GitHub App repo connection flow for signed-in users while keeping website URL and public repo URL inputs first-class
3. Create the hosted specialist agents in Agentverse from `apps/fetch/hosted_templates`, copy their addresses, then deploy the hosted orchestrator
4. Feed relay/orchestrator stage updates into the UXRay run detail UI for live multi-agent status updates
5. Expand the analyzer beyond the current narrow issue taxonomy and support persona/viewport matrices
6. Add OpenAI recommendation generation and code-grounded fix suggestions

## Architecture Notes
- Frontend polling is isolated in `apps/web/lib/hooks.ts` so it can be swapped to SSE later
- Frontend auth now uses Supabase SSR-style browser/server/middleware wiring, but pages are still guest-friendly and do not force login
- If live API requests fail and the user is in guest mode, `apps/web/lib/api.ts` falls back to seeded demo records stored in session storage
- Run orchestration is isolated behind `RunWorker` plus the Browser Use adapter
- Browser Use remains the real runtime; UXRay owns the analyzer and persisted findings
- `BROWSER_USE_MODEL` is a Browser Use Cloud model selector, not a direct Anthropic credential
- Fetch.ai has a dedicated standalone app in `apps/fetch`; the preferred path is now a hosted Agentverse orchestrator behind a local mailbox relay with the same shared-secret `/evaluate` contract
- Only the orchestrator is intended to be public and ASI:One-facing; specialist agents are real uAgents but internal by default
- SQLite lives at `apps/api/data/uxray.db`
- Existing root structure was preserved; implementation was added under `apps/`

## API / Schema Changes
- Added `POST /projects`, `GET /projects`, `GET /projects/{project_id}`
- Added `POST /projects/{project_id}/runs`, `GET /projects/{project_id}/runs`, `GET /runs/{run_id}`
- Added persisted entities for projects, runs, issues, recommendations, artifacts, progress events, and evaluations
- Added Browser Use adapter output normalization and analyzer output schema
- Added run metadata for `browser_use_model` and `evaluation_status`
- Added a local Fetch evaluation contract using `payload_json` plus API key body auth for hackathon-speed integration

## Files Touched
- `apps/api/app/main.py`
- `apps/api/app/db.py`
- `apps/api/app/adapters/browser_use.py`
- `apps/api/app/services/analyzer.py`
- `apps/api/app/services/evaluation.py`
- `apps/api/app/services/queue.py`
- `apps/fetch/README.md`
- `apps/fetch/.env.example`
- `apps/fetch/.env.local-runners.example`
- `apps/fetch/HOSTED_SETUP.md`
- `apps/fetch/hosted_templates/`
- `apps/fetch/pyproject.toml`
- `apps/fetch/uxray_fetch/`
- `apps/web/app/page.tsx`
- `apps/web/app/layout.tsx`
- `apps/web/app/login/page.tsx`
- `apps/web/app/auth/callback/route.ts`
- `apps/web/app/auth/auth-code-error/page.tsx`
- `apps/web/app/app/layout.tsx`
- `apps/web/app/app/page.tsx`
- `apps/web/app/app/projects/[projectId]/page.tsx`
- `apps/web/app/app/runs/[runId]/page.tsx`
- `apps/web/components/auth-entry-panel.tsx`
- `apps/web/components/dashboard-shell.tsx`
- `apps/web/components/project-form.tsx`
- `apps/web/components/project-overview.tsx`
- `apps/web/components/project-sidebar.tsx`
- `apps/web/components/run-detail-panel.tsx`
- `apps/web/components/run-view.tsx`
- `apps/web/lib/api.ts`
- `apps/web/lib/auth.tsx`
- `apps/web/lib/browser-session.ts`
- `apps/web/lib/demo-data.ts`
- `apps/web/lib/supabase.ts`
- `apps/web/lib/supabase-server.ts`
- `apps/web/lib/supabase-middleware.ts`
- `apps/web/middleware.ts`
- `apps/web/tests/auth-entry-panel.test.tsx`
- `apps/web/tests/demo-data.test.ts`
- `apps/web/tests/project-form.test.tsx`
- `README.md`
- `.env.local.example`
- `.gitignore`

## How To Run
- Frontend: `pnpm.cmd install`
- Frontend: `pnpm.cmd --dir apps/web dev`
- Backend: `py -m pip install -r apps/api/requirements.txt`
- Backend: `py -m uvicorn app.main:app --reload --app-dir apps/api`
- Fetch hosted setup: follow `apps/fetch/HOSTED_SETUP.md`, create the hosted agents in Agentverse, create/connect the relay mailbox agent, then run the local relay and point backend env vars at `http://127.0.0.1:8100/evaluate`
- Relay: `py -m uvicorn uxray_fetch.relay:app --host 127.0.0.1 --port 8100 --app-dir apps/fetch`
- Tests: `$env:PYTHONPATH='apps/api'; py -m pytest apps/api/tests -q -p no:tmpdir -p no:cacheprovider`
- Fetch tests: `py -m pytest apps/fetch/tests -q -p no:tmpdir -p no:cacheprovider`
- Web tests: `pnpm.cmd --dir apps/web test`
- Web build: `pnpm.cmd --dir apps/web build`
- Local backend tunnel: `cloudflared tunnel --url http://localhost:8000`
- Local target-site tunnel for Browser Use: `cloudflared tunnel --url http://localhost:3000`

## Known Issues
- Browser Use output formatting may need prompt tuning on real customer sites
- Backend test command disables pytest temp/cache plugins because of this machine's sandboxed temp-directory restrictions
- The README uses direct `py -m pip` installation because local `venv` creation failed on this Python `3.14` environment
- Fetch.ai evaluation reports `skipped` unless the hosted orchestrator is deployed and `FETCH_EVALUATION_*` env vars are set locally
- `apps/fetch` compiles and its pure tests pass on Python `3.14`, but live uAgents execution still requires Python `3.11` or `3.12`
- Supabase sign-in will not work until you add the Supabase URL/publishable key and enable the GitHub provider in your Supabase project
- Current signed-in frontend sessions are real, but backend ownership and durable cloud persistence are not implemented yet

## Notes For Next Session
- Start by exercising one real project URL with the configured Browser Use key and inspect the stored run output
- If run quality is weak, tune the Browser Use task prompt and tighten analyzer classification before adding more surfaces
- When ready for live Fetch demos, create the hosted agents from `apps/fetch/hosted_templates`, copy the agent addresses into the orchestrator secrets, then run the local relay and enable the backend evaluation env vars locally
- The frontend is now Vercel-friendly for guest/demo exploration; for live judge demos with real audits, tunnel the local FastAPI backend and point `NEXT_PUBLIC_API_BASE_URL` at that public URL
- Finish the auth story by moving durable signed-in project/run ownership into Supabase/Postgres and then layering optional GitHub App repo connections on top
