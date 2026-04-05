# UXRay

UXRay is a local first UX auditing platform that uses Browser Use agents to navigate websites like real users. It tests products across multiple personas and both desktop and mobile viewports, detects where the experience breaks down, and returns actionable recommendations. When a repository is connected, UXRay also maps issues back to likely source files and generates code grounded fix suggestions.

Read `handoff.md` first before continuing work in a new session.

## What UXRay Does

Most teams can lint code, run tests, and still ship websites that feel confusing, cluttered, or hard to use. UXRay focuses on the layer those tools miss: whether a real person can understand the product, find the main action, and complete key tasks across different audiences and devices.

UXRay lets a builder create a project from a website URL, optionally attach a repository, choose one or more personas, and launch audits. Each selected persona automatically runs on both desktop and mobile. The system gathers behavioral, DOM, layout, and visual evidence, turns that into issue packets, optionally sends those issues through a hosted Fetch.ai evaluation layer, and then generates prioritized recommendations and code grounded suggestions.

## Browser Use First

Browser Use is the core runtime of UXRay. It is the part of the system that actually navigates the site in a real browser, follows task instructions, explores flows, interacts with controls, and produces runtime evidence from real browser usage. UXRay is intentionally Browser Use first. The hosted Fetch layer is optional and happens after raw issue detection. It does not replace Browser Use.

At runtime, UXRay uses Browser Use agents to:

* navigate websites like real users
* explore flows across multiple personas
* run both desktop and mobile viewports automatically
* expose live browser sessions during execution
* produce screenshots, timings, DOM state, and layout evidence for later analysis

Playwright is used alongside the browser runtime to extract DOM state, screenshots, timings, and layout data during the run.

## Core Workflow

1. User creates a project with a hosted URL, GitHub repo, or both
2. UXRay detects likely site type and lets the user optionally describe the intended audience or website purpose
3. User selects one or more personas
4. Each persona automatically runs on both desktop and mobile viewports
5. Browser Use agents navigate the site in real time while the user can watch the sessions live
6. Playwright captures evidence during the run
7. The analyzer converts evidence into issue packets
8. The optional Fetch evaluation layer reviews compiled issues from different audience perspectives
9. GPT-5.4 mini generates recommendation summaries and code grounded fix suggestions
10. Results are stored under the project for later review and comparison

## Current Status

What currently works:

* project creation from a website URL and optional public repository URL
* local frontend and backend development flow
* guest mode for frontend exploration
* Supabase plus GitHub sign in support for authenticated usage
* hosted first Fetch.ai evaluation path through Agentverse plus local relay
* local fallback behavior when some hosted pieces are not configured
* Browser Use centered audit flow and issue generation story

What is partial or conditional:

* real audits require the backend to be reachable
* Vercel hosted frontend can run in guest mode without the backend, but full audits still need backend connectivity
* Fetch.ai evaluation is optional and is marked as skipped until configured
* some durable storage paths depend on optional Supabase storage setup
* live public hosting was not kept up continuously for the submission because of backend cost and uptime concerns tied to the more resource intensive runtime path

**Note:** UXRay was not kept continuously live hosted for the submission due to backend cost constraints and hosting uptime concerns. Because the product depends on a more intensive backend workflow, the focus was on reliably demonstrating the core experience rather than maintaining a permanently live deployment.

## Personas and Audience Model

Personas shape navigation priorities during browser runs and later help prioritize recommendations based on audience impact. They do not determine whether an issue objectively exists.

### First Time Visitor

Focuses on clarity, orientation, and whether the next step is obvious.

### Intent Driven User

Focuses on speed to value, direct task completion, and minimizing friction.

### Trust Evaluator

Focuses on credibility, polish, transparency, and confidence to continue.

### Custom Audience

Uses a user provided lens such as a recruiter, buyer, customer segment, or any audience specific context.

## Hosted Fetch.ai Evaluation Layer

UXRay includes a hosted Fetch.ai evaluation layer that reviews analyzer findings through multiple audience lenses before returning a final recommendation to the backend. This layer is optional and sits after raw issue detection. It does not replace Browser Use. The preferred path is a hosted Agentverse orchestrator plus a local mailbox relay, not a fully local multi terminal setup.

### Fetch Flow

1. UXRay backend posts an evaluation request to the local HTTP relay
2. The local relay signs and submits that request toward the hosted orchestrator
3. The hosted orchestrator dispatches issue review to the specialist audience agents
4. The boss agent evaluates consensus across the specialist opinions
5. The synthesis agent turns that consensus into a final recommendation
6. The hosted orchestrator sends the result back through the mailbox relay agent
7. The local relay returns the stored evaluation payload to UXRay
8. If the mailbox path is unavailable, UXRay can fall back to the ASI path, but that is resilience, not the primary hosted agent workflow

### Hosted Agents

#### `uxray_orchestrator_agent`

Primary Fetch.ai coordination agent for UXRay. It accepts an issue packet, fans work out to the specialist audience agents, collects their judgments, sends the combined result through boss review and synthesis, and returns the final recommendation path back to UXRay.

Agentverse profile: [uxray_orchestrator_agent](https://agentverse.ai/agents/details/agent1qdmxcxuh7yqnylqh3yq469spuv9m9alsf2a9zv5gvqypf0kqx52njyyfm0y/profile)

#### `uxray_first_time_visitor_agent`

Audience specialist that judges issues from a new user perspective. It focuses on orientation, clarity, messaging comprehension, and whether the next step is obvious for someone seeing the experience for the first time.

Agentverse profile: [uxray_first_time_visitor_agent](https://agentverse.ai/agents/details/agent1qf94pffvtkrmzea0sckhzefs46rkm6nhznpngmc3c34vwevhse44uvcwcdm/profile)

#### `uxray_intent_driven_agent`

Audience specialist that judges issues from a goal driven perspective. It focuses on speed to value, CTA clarity, path efficiency, and friction on the shortest route to completing a task.

Agentverse profile: [uxray_intent_driven_agent](https://agentverse.ai/agents/details/agent1q2pcaheuk4v38us6qwz322mmvw762vxhz7mvu2gcu5pcwmz2n56nu05nqhg/profile)

#### `uxray_trust_evaluator_agent`

Audience specialist that judges issues from a skeptical buyer or evaluator perspective. It focuses on credibility, reassurance, support visibility, trust cues, and hesitation around conversion.

Agentverse profile: [uxray_trust_evaluator_agent](https://agentverse.ai/agents/details/agent1qf6wwrjcgth40ddftxnnvv5gtktx0twm54u8ejh6cvxqcredpyyc5xz9q5t/profile)

#### `uxray_custom_audience_agent`

Audience specialist for a user defined lens. It applies the same review structure as the core specialists, but tailors the judgment to the custom audience context provided by UXRay.

Agentverse profile: [uxray_custom_audience_agent](https://agentverse.ai/agents/details/agent1q023pe7rzeka0fngr00kskwqfajse7z9wzlf27vh033tafudf00hwrzre8p/profile)

#### `uxray_boss_agent`

Decision gate that reviews the specialist opinions and determines whether an issue has strong, mixed, or weak agreement before final recommendation synthesis.

Agentverse profile: [uxray_boss_agent](https://agentverse.ai/agents/details/agent1qfnm567yvg6vhgd8p5wnmxuy4ny7wduw2qmgld7wvl9ung2hmmsxysvdh42/profile)

#### `uxray_synthesis_agent`

Final recommendation agent that converts the issue packet plus specialist and boss signals into a concise, implementation oriented recommendation. This is the last step in the hosted Fetch review chain before UXRay stores the result.

Agentverse profile: [uxray_synthesis_agent](https://agentverse.ai/agents/details/agent1qvpvz663lx4rgarnck9rljlfvavz7u7kavtqf6c9jrzsjdtm020pj99a5j2/profile)

#### `uxray_mailbox_relay_agent`

Mailbox connected return path agent used by the local relay stack. It is not a specialist reviewer. It exists so the hosted orchestrator has a live Agentverse mailbox address to send results back to.

Agentverse profile: [uxray_mailbox_relay_agent](https://agentverse.ai/agents/details/agent1qdm5l0n32p9v4cm6mfl3hplc4f6dk7jwyt852rm3lj2v4yr0pdfkjhva98a/profile)

### Local Relay Infrastructure

#### `uxray_fetch.relay`

Local HTTP relay service that signs the backend request, submits it to Agentverse, polls the mailbox relay agent for the response, and hands the result back to the FastAPI app. Treat this as infrastructure, not as a hosted evaluation agent.

## Local Setup

Create a root `.env.local` first. An example is provided in `.env.local.example`. `BROWSER_USE_MODEL` controls which model Browser Use Cloud should use for the run. It does not mean UXRay requires your own Anthropic API key, and if omitted the backend defaults to `claude-sonnet-4.6`.

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

## Supabase and GitHub Sign In

The frontend supports:

* Sign in with GitHub through Supabase Auth
* Continue as guest with session only demo state

To activate the signed in path:

1. Create a Supabase project
2. Copy the project URL and publishable key into `.env.local`
3. Enable GitHub in Supabase Authentication Providers
4. Use the Supabase callback URL in the GitHub OAuth App
5. Set Site URL and additional redirect URLs in Supabase
6. Keep guest mode as a fallback if Supabase is not configured

Important points:

* The GitHub Client ID in Supabase must be the actual OAuth App client ID, not your email
* The GitHub OAuth callback must be the Supabase callback URL, not the Next.js route directly
* If Supabase is not configured, the app still works in guest mode

## Durable Artifact Storage

For more reliable persistence across login, logout, and backend restarts, UXRay can store audit screenshots and artifacts in a public Supabase Storage bucket instead of only relying on local backend files.

When storage is configured:

* Browser Use screenshots and artifacts upload to Supabase storage and are saved as public URLs
* if upload fails or storage is not configured, UXRay falls back to the local artifact directory so audits still complete

## Vercel Friendly Frontend and Demo Mode

The frontend is set up so it can be deployed to Vercel without also hosting the backend immediately.

Behavior:

* if the backend is reachable, the app uses the real API
* if the backend is not reachable and the user continues as guest, the app falls back to seeded demo data
* signed in flows still render, but real audits require the backend

Important caveat: a Vercel hosted frontend cannot call `http://127.0.0.1:8000` on your machine for judges or external users. For a live demo, `NEXT_PUBLIC_API_BASE_URL` must point at a temporary public tunnel to your local FastAPI server.

Example:

```powershell
cloudflared tunnel --url http://localhost:8000
```

Then set:

```powershell
NEXT_PUBLIC_API_BASE_URL=https://<your-tunnel-subdomain>.trycloudflare.com
```

For local only development:

```powershell
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## Fetch.ai Wiring

The backend has a dedicated evaluation boundary after analyzer findings are produced, and the preferred path is a hosted Agentverse orchestrator plus a local mailbox relay. Use Python `3.11` or `3.12` for `apps/fetch`. Current `uagents` releases are not reliable on Python `3.14`.

To wire the backend into the hosted orchestrator, set:

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

Run the relay with:

```powershell
py apps/fetch/run_relay.py
```

Run the mailbox relay agent with:

```powershell
Set-Location apps/fetch
py -m uxray_fetch.relay_agent
```

Until those are configured, runs still complete normally and the Fetch.ai evaluation stage is marked as `skipped`.

## Demoing Local Targets

Browser Use Cloud cannot audit `localhost` directly. If you want UXRay to audit a local app, expose it with a public tunnel first and then create the UXRay project using that tunneled URL.

```powershell
cloudflared tunnel --url http://localhost:3000
```

## Tech Stack

Frontend:

* Next.js
* TypeScript
* Tailwind CSS
* shadcn/ui

Backend:

* FastAPI

Browser runtime:

* Browser Use

Instrumentation:

* Playwright

Reasoning and recommendations:

* GPT-5.4 mini

Optional evaluation layer:

* Fetch uAgents

Repo analysis:

* GitPython
* ripgrep
* Python subprocess

Persistence:

* SQLite

Artifact storage:

* local filesystem storage, with optional Supabase storage support

Queue:

* in process queue with a strict max concurrency of 4 sessions

## Queue and Run Model

UXRay enforces a strict maximum of 4 active browser sessions at any time. A single project may create more than 4 runs, such as multiple audiences across both desktop and mobile, but any runs beyond the first 4 are queued and started automatically as active sessions finish.

Run statuses:

* `queued`
* `running`
* `completed`
* `failed`

Queue rules:

* FIFO across pending runs
* hard cap of 4 active sessions maximum across the app
* next queued run starts automatically when a slot frees up

## Project Inputs

Projects can currently be created from:

* a website URL
* an optional public repository URL

GitHub account connection is optional. It exists for durable account history and later repo linked workflows, not for the core audit path.

## Handoff and Session Continuity

This repo is meant to preserve continuity across long coding sessions. `handoff.md` should be updated at meaningful milestones so future sessions can recover state quickly without rediscovering everything manually.

The handoff file should summarize:

* what currently works
* what was completed in the session
* what is in progress
* blockers
* next priorities
* architecture notes
* API or schema changes
* files touched
* exact run commands
* known issues
* notes for the next session

The repo should keep this file concise, current, and free of secrets.

## Troubleshooting

A few important caveats already documented in the repo:

* if Git warns that LF will be replaced by CRLF on Windows, that warning alone is expected and does not block staging
* the bigger Git risk is accidentally committing generated runtime output, especially under `apps/api/data/manual-repo-build-test/`
* a hosted frontend without public backend access can still be explored in guest mode, but full audits require the backend
* Browser Use Cloud cannot directly audit `localhost`
* Fetch.ai evaluation is optional and will be skipped when not configured

## Pitch Summary

UXRay uses Browser Use agents to navigate products like real users, find where the experience breaks down across devices and audiences, and turn those findings into actionable UX and code level improvements. Browser Use handles the real web interaction, while the post analysis layer helps prioritize what matters most for the intended audience.
