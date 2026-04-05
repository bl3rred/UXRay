import json
from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient
from uagents_core.envelope import Envelope
from uagents_core.identity import Identity

import run_relay
from uxray_fetch.relay import RelaySettings, create_app


TEST_RELAY_SEED = "unit-test-relay-seed"
TEST_RELAY_ADDRESS = Identity.from_seed(TEST_RELAY_SEED, 0).address


def build_request_payload() -> dict:
    return {
        "project_name": "UXRay Demo",
        "project_url": "https://example.com",
        "issues": [
            {
                "issue_id": "cta_feedback:1",
                "issue_title": "Primary signup CTA appears disabled",
                "route": "/signup",
                "persona": "default_user",
                "viewport": "desktop",
                "issue_type": "cta_feedback",
                "severity": "high",
                "evidence": ["No feedback shown"],
                "screenshot_summary": "Button stayed disabled after click.",
                "dom_snippet": "",
                "custom_audience": None,
            }
        ],
    }


def build_response_envelope(
    *,
    sender: str,
    target: str,
    session: str,
    protocol_digest: str,
    schema_digest: str,
    payload_json: str,
) -> dict:
    envelope = Envelope(
        version=1,
        sender=sender,
        target=target,
        session=session,
        schema_digest=schema_digest,
        protocol_digest=protocol_digest,
    )
    envelope.encode_payload(payload_json)
    return envelope.model_dump(mode="json")


def test_relay_maps_completed_mailbox_response() -> None:
    state: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path

        if path == "/v1/almanac/agents/agent1orchestrator":
            return httpx.Response(
                200,
                json={
                    "protocols": ["proto-backend", "proto-chat"],
                    "endpoints": [{"url": "https://agentverse.ai/v1/hosting/submit", "weight": 1}],
                },
            )

        if path == "/v1/almanac/manifests/protocols/proto-backend":
            return httpx.Response(
                200,
                json={
                    "metadata": [{"name": "uxray_hosted_backend_evaluation"}],
                    "interactions": [
                        {
                            "request": "model-request",
                            "responses": ["model-response"],
                        }
                    ],
                },
            )

        if path == "/v1/almanac/manifests/protocols/proto-chat":
            return httpx.Response(
                200,
                json={
                    "metadata": [{"name": "AgentChatProtocol"}],
                    "interactions": [],
                },
            )

        if path == "/v1/hosting/submit":
            payload = Envelope.model_validate_json(request.content.decode("utf-8"))
            state["session"] = str(payload.session)
            assert payload.sender == TEST_RELAY_ADDRESS
            assert payload.target == "agent1orchestrator"
            assert payload.protocol_digest == "proto-backend"
            assert payload.schema_digest == "model-request"
            assert payload.signature is not None
            return httpx.Response(200, json={"status": "submitted"})

        if path == f"/v2/agents/{TEST_RELAY_ADDRESS}/mailbox":
            return httpx.Response(
                200,
                json=[
                    {
                        "uuid": "message-1",
                        "envelope": build_response_envelope(
                            sender="agent1orchestrator",
                            target=TEST_RELAY_ADDRESS,
                            session=state["session"],
                            protocol_digest="proto-backend",
                            schema_digest="model-response",
                            payload_json=json.dumps(
                                {
                                    "session": state["session"],
                                    "status": "completed",
                                    "response_json": json.dumps(
                                        {
                                            "status": "completed",
                                            "recommendations": [
                                                {
                                                    "issue_id": "cta_feedback:1",
                                                    "issue_title": "Primary signup CTA appears disabled",
                                                    "final_priority": "high",
                                                    "audience_impact_summary": "first time visitor=8/10",
                                                    "merged_rationale": "This is a clear conversion blocker.",
                                                    "recommended_fix_direction": "Add loading and success feedback.",
                                                    "gpt_handoff_string": "Prioritize CTA feedback.",
                                                    "consensus_level": "high",
                                                }
                                            ],
                                        }
                                    ),
                                    "error": None,
                                }
                            ),
                        ),
                    }
                ],
            )

        if path == f"/v2/agents/{TEST_RELAY_ADDRESS}/mailbox/message-1":
            return httpx.Response(204)

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    app = create_app(
        settings=RelaySettings(
            shared_secret="fetch-key",
            agentverse_api_key="agentverse-key",
            relay_agent_address=TEST_RELAY_ADDRESS,
            orchestrator_address="agent1orchestrator",
            relay_agent_seed=TEST_RELAY_SEED,
            poll_interval_seconds=0,
        ),
        transport=httpx.MockTransport(handler),
    )
    client = TestClient(app)

    response = client.post(
        "/evaluate",
        json={
            "api_key": "fetch-key",
            "payload_json": json.dumps(build_request_payload()),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    parsed = json.loads(body["response_json"])
    assert parsed["recommendations"][0]["final_priority"] == "high"


def test_relay_rejects_invalid_shared_secret() -> None:
    app = create_app(
        settings=RelaySettings(
            shared_secret="fetch-key",
            agentverse_api_key="agentverse-key",
            relay_agent_address=TEST_RELAY_ADDRESS,
            orchestrator_address="agent1orchestrator",
            relay_agent_seed=TEST_RELAY_SEED,
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/evaluate",
        json={
            "api_key": "wrong",
            "payload_json": json.dumps(build_request_payload()),
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["error"] == "Invalid API key."


def test_relay_accepts_manifest_without_response_digest() -> None:
    state: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path

        if path == "/v1/almanac/agents/agent1orchestrator":
            return httpx.Response(
                200,
                json={
                    "protocols": ["proto-backend"],
                    "endpoints": [{"url": "https://agentverse.ai/v1/hosting/submit", "weight": 1}],
                },
            )

        if path == "/v1/almanac/manifests/protocols/proto-backend":
            return httpx.Response(
                200,
                json={
                    "metadata": [{"name": "uxray_hosted_backend_evaluation"}],
                    "interactions": [{"request": "model-request", "responses": []}],
                },
            )

        if path == "/v1/hosting/submit":
            payload = Envelope.model_validate_json(request.content.decode("utf-8"))
            state["session"] = str(payload.session)
            assert payload.signature is not None
            return httpx.Response(200, json={"status": "submitted"})

        if path == f"/v2/agents/{TEST_RELAY_ADDRESS}/mailbox":
            return httpx.Response(
                200,
                json=[
                    {
                        "uuid": "message-1",
                        "envelope": build_response_envelope(
                            sender="agent1orchestrator",
                            target=TEST_RELAY_ADDRESS,
                            session=state["session"],
                            protocol_digest="proto-backend",
                            schema_digest="model-response-runtime",
                            payload_json=json.dumps(
                                {
                                    "session": state["session"],
                                    "status": "completed",
                                    "response_json": json.dumps(
                                        {
                                            "status": "completed",
                                            "recommendations": [],
                                        }
                                    ),
                                    "error": None,
                                }
                            ),
                        ),
                    }
                ],
            )

        if path == f"/v2/agents/{TEST_RELAY_ADDRESS}/mailbox/message-1":
            return httpx.Response(204)

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    app = create_app(
        settings=RelaySettings(
            shared_secret="fetch-key",
            agentverse_api_key="agentverse-key",
            relay_agent_address=TEST_RELAY_ADDRESS,
            orchestrator_address="agent1orchestrator",
            relay_agent_seed=TEST_RELAY_SEED,
            poll_interval_seconds=0,
        ),
        transport=httpx.MockTransport(handler),
    )
    client = TestClient(app)

    response = client.post(
        "/evaluate",
        json={
            "api_key": "fetch-key",
            "payload_json": json.dumps(build_request_payload()),
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_relay_surfaces_protocol_errors_without_http_500() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/almanac/agents/agent1orchestrator":
            return httpx.Response(200, json={"protocols": [], "endpoints": []})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    app = create_app(
        settings=RelaySettings(
            shared_secret="fetch-key",
            agentverse_api_key="agentverse-key",
            relay_agent_address=TEST_RELAY_ADDRESS,
            orchestrator_address="agent1orchestrator",
            relay_agent_seed=TEST_RELAY_SEED,
            poll_interval_seconds=0,
        ),
        transport=httpx.MockTransport(handler),
    )
    client = TestClient(app)

    response = client.post(
        "/evaluate",
        json={
            "api_key": "fetch-key",
            "payload_json": json.dumps(build_request_payload()),
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert "Could not find published backend protocol" in response.json()["error"]


def test_relay_skips_stale_protocol_manifest_digests() -> None:
    state: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path

        if path == "/v1/almanac/agents/agent1orchestrator":
            return httpx.Response(
                200,
                json={
                    "protocols": ["proto-stale", "proto-backend"],
                    "endpoints": [{"url": "https://agentverse.ai/v1/hosting/submit", "weight": 1}],
                },
            )

        if path == "/v1/almanac/manifests/protocols/proto-stale":
            return httpx.Response(404, json={"detail": "Not found"})

        if path == "/v1/almanac/manifests/protocols/proto-backend":
            return httpx.Response(
                200,
                json={
                    "metadata": [{"name": "uxray_hosted_backend_evaluation"}],
                    "interactions": [
                        {
                            "request": "model-request",
                            "responses": ["model-response"],
                        }
                    ],
                },
            )

        if path == "/v1/hosting/submit":
            payload = Envelope.model_validate_json(request.content.decode("utf-8"))
            state["session"] = str(payload.session)
            assert payload.signature is not None
            return httpx.Response(200, json={"status": "submitted"})

        if path == f"/v2/agents/{TEST_RELAY_ADDRESS}/mailbox":
            return httpx.Response(
                200,
                json=[
                    {
                        "uuid": "message-1",
                        "envelope": build_response_envelope(
                            sender="agent1orchestrator",
                            target=TEST_RELAY_ADDRESS,
                            session=state["session"],
                            protocol_digest="proto-backend",
                            schema_digest="model-response",
                            payload_json=json.dumps(
                                {
                                    "session": state["session"],
                                    "status": "completed",
                                    "response_json": json.dumps(
                                        {
                                            "status": "completed",
                                            "recommendations": [],
                                        }
                                    ),
                                    "error": None,
                                }
                            ),
                        ),
                    }
                ],
            )

        if path == f"/v2/agents/{TEST_RELAY_ADDRESS}/mailbox/message-1":
            return httpx.Response(204)

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    app = create_app(
        settings=RelaySettings(
            shared_secret="fetch-key",
            agentverse_api_key="agentverse-key",
            relay_agent_address=TEST_RELAY_ADDRESS,
            orchestrator_address="agent1orchestrator",
            relay_agent_seed=TEST_RELAY_SEED,
            poll_interval_seconds=0,
        ),
        transport=httpx.MockTransport(handler),
    )
    client = TestClient(app)

    response = client.post(
        "/evaluate",
        json={
            "api_key": "fetch-key",
            "payload_json": json.dumps(build_request_payload()),
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_relay_falls_back_to_mailbox_when_sync_submit_times_out() -> None:
    state: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path

        if path == "/v1/almanac/agents/agent1orchestrator":
            return httpx.Response(
                200,
                json={
                    "protocols": ["proto-backend"],
                    "endpoints": [{"url": "https://agentverse.ai/v1/hosting/submit", "weight": 1}],
                },
            )

        if path == "/v1/almanac/manifests/protocols/proto-backend":
            return httpx.Response(
                200,
                json={
                    "metadata": [{"name": "uxray_hosted_backend_evaluation"}],
                    "interactions": [
                        {
                            "request": "model-request",
                            "responses": ["model-response"],
                        }
                    ],
                },
            )

        if path == "/v1/hosting/submit":
            payload = Envelope.model_validate_json(request.content.decode("utf-8"))
            state["session"] = str(payload.session)
            raise httpx.ReadTimeout("timed out", request=request)

        if path == f"/v2/agents/{TEST_RELAY_ADDRESS}/mailbox":
            return httpx.Response(
                200,
                json=[
                    {
                        "uuid": "message-timeout-fallback",
                        "envelope": build_response_envelope(
                            sender="agent1orchestrator",
                            target=TEST_RELAY_ADDRESS,
                            session=state["session"],
                            protocol_digest="proto-backend",
                            schema_digest="model-response",
                            payload_json=json.dumps(
                                {
                                    "session": state["session"],
                                    "status": "completed",
                                    "response_json": json.dumps(
                                        {
                                            "status": "completed",
                                            "recommendations": [],
                                        }
                                    ),
                                    "error": None,
                                }
                            ),
                        ),
                    }
                ],
            )

        if path == f"/v2/agents/{TEST_RELAY_ADDRESS}/mailbox/message-timeout-fallback":
            return httpx.Response(204)

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    app = create_app(
        settings=RelaySettings(
            shared_secret="fetch-key",
            agentverse_api_key="agentverse-key",
            relay_agent_address=TEST_RELAY_ADDRESS,
            orchestrator_address="agent1orchestrator",
            relay_agent_seed=TEST_RELAY_SEED,
            poll_interval_seconds=0,
            timeout_seconds=2,
            sync_submit_timeout_seconds=0.1,
        ),
        transport=httpx.MockTransport(handler),
    )
    client = TestClient(app)

    response = client.post(
        "/evaluate",
        json={
            "api_key": "fetch-key",
            "payload_json": json.dumps(build_request_payload()),
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_relay_reports_mailbox_timeout_separately() -> None:
    state: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path

        if path == "/v1/almanac/agents/agent1orchestrator":
            return httpx.Response(
                200,
                json={
                    "protocols": ["proto-backend"],
                    "endpoints": [{"url": "https://agentverse.ai/v1/hosting/submit", "weight": 1}],
                },
            )

        if path == "/v1/almanac/manifests/protocols/proto-backend":
            return httpx.Response(
                200,
                json={
                    "metadata": [{"name": "uxray_hosted_backend_evaluation"}],
                    "interactions": [
                        {
                            "request": "model-request",
                            "responses": ["model-response"],
                        }
                    ],
                },
            )

        if path == "/v1/hosting/submit":
            payload = Envelope.model_validate_json(request.content.decode("utf-8"))
            state["session"] = str(payload.session)
            return httpx.Response(200, json={"status": "submitted"})

        if path == f"/v2/agents/{TEST_RELAY_ADDRESS}/mailbox":
            return httpx.Response(200, json=[])

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    app = create_app(
        settings=RelaySettings(
            shared_secret="fetch-key",
            agentverse_api_key="agentverse-key",
            relay_agent_address=TEST_RELAY_ADDRESS,
            orchestrator_address="agent1orchestrator",
            relay_agent_seed=TEST_RELAY_SEED,
            poll_interval_seconds=0,
            timeout_seconds=0.01,
        ),
        transport=httpx.MockTransport(handler),
    )
    client = TestClient(app)

    response = client.post(
        "/evaluate",
        json={
            "api_key": "fetch-key",
            "payload_json": json.dumps(build_request_payload()),
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert "Timed out waiting for mailbox response" in response.json()["error"]


def test_run_relay_sets_selector_policy_on_windows() -> None:
    events: list[str] = []

    class FakeAsyncio:
        class WindowsSelectorEventLoopPolicy:
            pass

        @staticmethod
        def set_event_loop_policy(policy) -> None:
            events.append(policy.__class__.__name__)

    run_relay.configure_event_loop_policy(platform="win32", asyncio_module=FakeAsyncio)

    assert events == ["WindowsSelectorEventLoopPolicy"]


def test_run_relay_starts_uvicorn_with_expected_defaults(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        run_relay,
        "uvicorn",
        SimpleNamespace(run=lambda app, **kwargs: calls.append({"app": app, **kwargs})),
    )

    run_relay.run_relay(host="127.0.0.1", port=8100)

    assert calls == [
        {
            "app": "uxray_fetch.relay:app",
            "host": "127.0.0.1",
            "port": 8100,
            "app_dir": str(run_relay.APP_DIR),
        }
    ]
