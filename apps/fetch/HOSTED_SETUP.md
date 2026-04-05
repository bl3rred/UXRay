# UXRay Hosted Fetch Setup

This guide is for deploying the Fetch.ai layer as **Agentverse Hosted Agents** and then wiring the UXRay backend to the hosted orchestrator through the local mailbox relay.

Docs used as source of truth:
- Agentverse Hosted Agents and Build Tab: `https://docs.agentverse.ai/documentation/create-agents/hosted-agents`
- Enable Chat Protocol: `https://docs.agentverse.ai/documentation/getting-started/enable-chat-protocol`
- Agentverse MCP notes on hosted secrets and ASI:One examples: `https://docs.agentverse.ai/documentation/advanced-usages/agentverse-mcp`
- ASI:One developer docs: `https://docs.asi1.ai/documentation/getting-started/overview`

## 1. What you need before you start

Required:
- Agentverse account
- one shared secret string for `UXRay backend <-> hosted orchestrator`
- Agentverse API key for the local mailbox relay

Important:
- `FETCH_EVALUATION_API_KEY` / `UXRAY_FETCH_SHARED_SECRET` should be a plain random shared secret, not an Agentverse JWT or API credential
- `AGENTVERSE_API_KEY` is the only env var that should hold your Agentverse API key

You do **not** need to keep the hosted agent secrets in the repo. Hosted Agents ignore repo `.env` files at runtime. Add secrets directly in Agentverse.

## 2. Create these hosted agents

Create seven hosted agents in Agentverse:

1. `uxray_orchestrator_agent`
2. `uxray_first_time_visitor_agent`
3. `uxray_intent_driven_agent`
4. `uxray_trust_evaluator_agent`
5. `uxray_custom_audience_agent`
6. `uxray_boss_agent`
7. `uxray_synthesis_agent`

Use the files in `hosted_templates/` as the code for each agent.

## 3. Deploy order

Deploy in this order:

1. first-time visitor agent
2. intent-driven agent
3. trust evaluator agent
4. custom audience agent
5. boss agent
6. synthesis agent
7. orchestrator agent

After each specialist deploys, copy its public address or hosted agent ID from Agentverse. You will need those for the orchestrator secrets.
If you already deployed the orchestrator before the mailbox backend protocol change, redeploy it from the current template so the backend protocol manifest includes the response model.

## 4. Secrets to add in Agentverse

### Specialist agents

The specialist, boss, and synthesis agents do not need extra secrets for the first hosted pass.

### Orchestrator agent

Add these Agentverse secrets to the orchestrator:

```text
UXRAY_FETCH_SHARED_SECRET=<shared-secret>
ASI_ONE_API_KEY=<your-asi-one-api-key>
UXRAY_FETCH_ASI_REPHRASE_ENABLED=true
UXRAY_FETCH_ASI_MODEL=asi1-mini
UXRAY_FETCH_ORCHESTRATOR_NAME=uxray_orchestrator_agent
UXRAY_FETCH_FIRST_TIME_VISITOR_AGENT_ADDRESS=<copied-address>
UXRAY_FETCH_INTENT_DRIVEN_AGENT_ADDRESS=<copied-address>
UXRAY_FETCH_TRUST_EVALUATOR_AGENT_ADDRESS=<copied-address>
UXRAY_FETCH_CUSTOM_AUDIENCE_AGENT_ADDRESS=<copied-address>
UXRAY_FETCH_BOSS_AGENT_ADDRESS=<copied-address>
UXRAY_FETCH_SYNTHESIS_AGENT_ADDRESS=<copied-address>
UXRAY_FETCH_ORCHESTRATOR_TIMEOUT_SECONDS=20
```

## 5. Enable ACP / ASI:One compatibility

All hosted templates are ACP-compatible now.

Recommended setup:

1. Enable Chat Protocol / ACP for all seven hosted agents
2. Make the orchestrator the primary public/discoverable UXRay entry point
3. Keep specialist metadata quieter, even though they are ACP-capable
4. Use the orchestrator in demos, docs, and judge walkthroughs

Important distinction:
- ACP compatibility is enabled on every agent to satisfy Agentverse setup and direct-chat support
- the orchestrator is still the main product entry point
- specialists only explain their own lens or role and point users back to the orchestrator for the full workflow

## 6. Create a dedicated relay mailbox agent

Create one dedicated mailbox-connected relay agent identity. The simplest path is the local scaffold:

```powershell
Set-Location apps/fetch
py -m uxray_fetch.relay_agent
```

Use Python `3.11` or `3.12` for this step. Copy the printed `agent1...` address, connect it to Agentverse mailbox, and use that address as `FETCH_RELAY_AGENT_ADDRESS`.

## 7. Run the local relay and point UXRay backend at it

Once the orchestrator is deployed, copy its public agent address from Agentverse and set your root `.env.local`:

```powershell
FETCH_EVALUATION_ENABLED=true
FETCH_EVALUATION_AGENT_URL=http://127.0.0.1:8100/evaluate
FETCH_EVALUATION_API_KEY=<same-value-as-UXRAY_FETCH_SHARED_SECRET>
FETCH_EVALUATION_TIMEOUT_SECONDS=20
AGENTVERSE_API_KEY=<your-agentverse-api-key>
FETCH_RELAY_AGENT_ADDRESS=<relay-agent-address>
FETCH_RELAY_ORCHESTRATOR_ADDRESS=<hosted-orchestrator-address>
ASI_ONE_API_KEY=<optional>
```

The backend and hosted orchestrator should share the same `FETCH_EVALUATION_API_KEY` / `UXRAY_FETCH_SHARED_SECRET` value. `AGENTVERSE_API_KEY` is separate and only used by the local relay.

Start the relay locally:

```powershell
py -m uvicorn uxray_fetch.relay:app --host 127.0.0.1 --port 8100 --app-dir apps/fetch
```

## 8. First direct hosted test

Before using the full UXRay app, hit the local relay with one issue packet.

You can base the request body on:
- [hosted_templates/issue_packet_example.json](/C:/Users/rfarr/Desktop/uxray/apps/fetch/hosted_templates/issue_packet_example.json)

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8100/evaluate `
  -ContentType 'application/json' `
  -Body '{
    "api_key":"<shared-secret>",
    "payload_json":"{\"project_name\":\"UXRay Demo\",\"project_url\":\"https://example.com\",\"issues\":[{\"issue_id\":\"issue_1\",\"issue_title\":\"Primary CTA appears disabled\",\"route\":\"/signup\",\"persona\":\"first_time_visitor\",\"viewport\":\"desktop\",\"issue_type\":\"cta_feedback\",\"severity\":\"high\",\"evidence\":[\"No loading state\",\"No success feedback\"],\"screenshot_summary\":\"CTA looks disabled after click\",\"dom_snippet\":\"<button disabled>Start free</button>\",\"custom_audience\":null}]}"
  }'
```

Expected result:
- HTTP success
- response body with `status: completed`
- one synthesized recommendation in `response_json`

## 9. First UXRay integration test

After the direct test passes:

1. run the FastAPI backend locally
2. create a project in UXRay
3. start a run
4. wait for Browser Use and analyzer completion
5. confirm the Fetch evaluation section becomes `completed`
6. open the run detail page and verify the synthesized evaluation renders

## 10. First ASI:One test

After the orchestrator is public and ACP-enabled:

1. open the orchestrator agent in Agentverse
2. launch `Chat with Agent` or use ASI:One Agentic mode
3. send either:
   - a JSON `IssuePacket`
   - or a follow-up question such as `why was this prioritized?`

Expected behavior:
- structured prioritization still comes from UXRay's deterministic logic
- explanation text is rephrased through ASI:One

## 10. If something fails

Check these first:
- specialist addresses copied correctly into orchestrator secrets
- shared secret matches the backend `FETCH_EVALUATION_API_KEY`
- relay agent address is a real mailbox-connected `agent1...` identity you own
- Agentverse API key is valid for signing, submitting, and reading the relay agent mailbox
- ACP enabled on all hosted agents
- orchestrator timeout is not too low for multi-agent round trips
