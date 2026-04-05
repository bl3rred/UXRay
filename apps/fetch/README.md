# UXRay Fetch Agents

This app contains the Fetch.ai sponsor-track evaluation layer for UXRay.

The preferred path is now:
- **Agentverse Hosted Agents**
- one public orchestrator
- six hosted specialist agents
- local relay calls from UXRay FastAPI into Agentverse mailbox APIs, targeting the hosted orchestrator by signed envelope
- ASI:One used as the public demo and explanation surface
- ACP-compatible templates for every hosted agent

The current local mailbox runner code still exists, but it is now a legacy fallback. The hosted path is the one to use for judging and live demos.

## What lives here

- `uxray_fetch/`
  - shared models
  - deterministic audience, boss, and synthesis logic
  - legacy local runner implementation
- `hosted_templates/`
  - paste-ready hosted agent code for Agentverse
  - ACP-compatible templates for orchestrator and specialists
- `.env.example`
  - the hosted secret contract you should mirror into Agentverse
- `.env.local-runners.example`
  - legacy local runner envs if you still need them
- `HOSTED_SETUP.md`
  - step-by-step guide for deploying the hosted agents and testing through ASI:One
- `uxray_fetch/relay_agent.py`
  - minimal mailbox-connected relay agent scaffold for obtaining a dedicated relay `agent1...` identity
  - includes the local `port=8000` and `endpoint=http://127.0.0.1:8000/submit` settings Agentverse mailbox expects

## Hosted-first setup

Use the hosted setup guide:

- [HOSTED_SETUP.md](/C:/Users/rfarr/Desktop/uxray/apps/fetch/HOSTED_SETUP.md)

The code you will paste into Agentverse Hosted Agents is in:

- [hosted_templates](/C:/Users/rfarr/Desktop/uxray/apps/fetch/hosted_templates)

## FastAPI backend contract

The UXRay backend still uses the same shared-secret + `payload_json` contract, but it should point to the local relay instead of the hosted agent directly.

Set these in the root `.env.local` once your hosted orchestrator and relay agent exist:

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

Run the relay locally:

```powershell
py apps/fetch/run_relay.py
```

On Windows, use the launcher above instead of raw `uvicorn`. It switches the relay to the selector event-loop policy before startup so local shutdowns do not spam the Proactor socket-reset traceback.

Create a relay mailbox agent identity once:

```powershell
Set-Location apps/fetch
py -m uxray_fetch.relay_agent
```

Keep that mailbox relay agent process running while you want the hosted orchestrator path to work. The local HTTP relay alone is not enough; the hosted orchestrator needs the mailbox-connected relay agent to stay active in Agentverse so it has somewhere to reply.

## ASI:One role

ASI:One is the public demo and explanation surface for the orchestrator.

Chosen behavior:
- deterministic evaluation still comes from UXRay's own logic
- ASI:One is used to rephrase and explain the final synthesized result
- the backend does **not** route normal evaluations through ASI:One; backend-triggered evaluation uses Agentverse mailbox transport

This keeps product behavior stable and easier to debug while avoiding unsupported hosted REST decorators and unreliable chat-based RPC routing.

Hosted specialist agents are also ACP-compatible now so Agentverse setup is smoother, but they still only explain their own lens or role. The orchestrator remains the only full workflow entry point.

## Legacy local runners

If you still want the old mailbox-first local setup:
- use Python `3.11` or `3.12`
- copy `.env.local-runners.example` to `.env`
- run the `uxray_fetch.runners.*` modules from separate terminals

That path is still useful for local experimentation, but it is no longer the primary demo plan.
