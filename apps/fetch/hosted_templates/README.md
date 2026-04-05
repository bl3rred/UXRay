# Hosted Agent Templates

These files are the hosted-first Fetch.ai scaffold for UXRay.

Use each file as the code for one Agentverse Hosted Agent:

- `orchestrator_agent.py`
- `first_time_visitor_agent.py`
- `intent_driven_agent.py`
- `trust_evaluator_agent.py`
- `custom_audience_agent.py`
- `boss_agent.py`
- `synthesis_agent.py`

Deployment order:

1. deploy the four audience agents
2. deploy the boss agent
3. deploy the synthesis agent
4. copy their addresses or IDs
5. deploy the orchestrator with those addresses configured as secrets

All templates are ACP-compatible.

ACP compliance checklist:
- every template registers `@chat_protocol.on_message(ChatMessage)`
- every template registers `@chat_protocol.on_message(ChatAcknowledgement)`
- every chat reply is returned as a fully populated `ChatMessage` with `timestamp`, `msg_id`, and `content`

The orchestrator is still the primary public ACP / ASI:One-facing agent for UXRay.

Notes:
- these templates are intentionally standalone so you can paste them directly into Agentverse
- the orchestrator preserves latest recommendations and traces in agent storage for follow-up chat
- backend-triggered evaluation should go through the local `uxray_fetch.relay` service and Agentverse mailbox transport, not ACP chat and not a hosted `/evaluate` endpoint
- ASI:One is used only to rephrase and explain final outputs, not to change deterministic scoring
- specialist templates can answer direct chat in-role, but they should still redirect users to the orchestrator for the full multi-agent UXRay workflow
