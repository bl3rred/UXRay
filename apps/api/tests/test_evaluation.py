import json

import httpx

from app.schemas import AnalysisIssue
from app.services.evaluation import FetchEvaluationService


def test_fetch_evaluation_service_skips_when_not_configured() -> None:
    service = FetchEvaluationService(
        enabled=False,
        agent_url=None,
        api_key=None,
    )

    result = service.evaluate(
        project_name="UXRay Demo",
        project_url="https://example.com",
        issues=[
            AnalysisIssue(
                issue_type="cta_feedback",
                title="Primary CTA did not respond",
                summary="The button stayed disabled after click.",
                severity="high",
                route="/signup",
                evidence=["No feedback shown"],
                confidence=0.9,
            )
        ],
    )

    assert result.status == "skipped"
    assert result.evaluations == []
    assert result.error is None


def test_fetch_evaluation_service_maps_orchestrator_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["api_key"] == "fetch-key"
        body = {
            "status": "completed",
            "response_json": json.dumps(
                {
                    "status": "completed",
                    "recommendations": [
                        {
                            "issue_id": "cta_feedback:1",
                            "issue_title": "Primary signup CTA appears disabled",
                            "final_priority": "high",
                            "audience_impact_summary": "first time visitor=8/10; intent driven=9/10",
                            "merged_rationale": "Multiple audiences see this as a conversion blocker.",
                            "recommended_fix_direction": "Add a clear loading and success state.",
                            "gpt_handoff_string": "Prioritize CTA feedback on /signup.",
                            "consensus_level": "high",
                        }
                    ],
                }
            ),
        }
        return httpx.Response(200, json=body)

    service = FetchEvaluationService(
        enabled=True,
        agent_url="http://127.0.0.1:8100/evaluate",
        api_key="fetch-key",
        transport=httpx.MockTransport(handler),
    )

    result = service.evaluate(
        project_name="UXRay Demo",
        project_url="https://example.com",
        issues=[
            AnalysisIssue(
                issue_type="cta_feedback",
                title="Primary signup CTA appears disabled",
                summary="The button stayed disabled after click.",
                severity="high",
                route="/signup",
                evidence=["No feedback shown"],
                confidence=0.9,
            )
        ],
    )

    assert result.status == "completed"
    assert result.evaluations[0].priority == "high"
    assert result.evaluations[0].audience == "multi_agent_synthesis"
    assert result.error is None


def test_fetch_evaluation_service_fails_on_transport_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    service = FetchEvaluationService(
        enabled=True,
        agent_url="http://127.0.0.1:8100/evaluate",
        api_key="fetch-key",
        transport=httpx.MockTransport(handler),
    )

    result = service.evaluate(
        project_name="UXRay Demo",
        project_url="https://example.com",
        issues=[
            AnalysisIssue(
                issue_type="cta_feedback",
                title="Primary signup CTA appears disabled",
                summary="The button stayed disabled after click.",
                severity="high",
                route="/signup",
                evidence=["No feedback shown"],
                confidence=0.9,
            )
        ],
    )

    assert result.status == "failed"
    assert "connection refused" in (result.error or "")


def test_fetch_evaluation_service_reports_local_relay_timeout() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    service = FetchEvaluationService(
        enabled=True,
        agent_url="http://127.0.0.1:8100/evaluate",
        api_key="fetch-key",
        timeout_seconds=180,
        transport=httpx.MockTransport(handler),
    )

    result = service.evaluate(
        project_name="UXRay Demo",
        project_url="https://example.com",
        issues=[
            AnalysisIssue(
                issue_type="cta_feedback",
                title="Primary signup CTA appears disabled",
                summary="The button stayed disabled after click.",
                severity="high",
                route="/signup",
                evidence=["No feedback shown"],
                confidence=0.9,
            )
        ],
    )

    assert result.status == "failed"
    assert result.error == "Timed out waiting for the local Fetch relay after 180 seconds."


def test_fetch_evaluation_service_falls_back_to_asi_when_relay_times_out() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "127.0.0.1":
            raise httpx.ReadTimeout("timed out")
        body = {
            "choices": [
                {
                    "message": {
                        "content": "```json\n"
                        + json.dumps(
                            {
                                "recommendations": [
                                    {
                                        "issue_title": "Primary signup CTA appears disabled",
                                        "final_priority": "high",
                                        "audience_impact_summary": "first time visitor=8/10; intent driven=9/10",
                                        "merged_rationale": "Direct ASI fallback still sees this as a conversion blocker.",
                                    }
                                ]
                            }
                        )
                        + "\n```"
                    }
                }
            ]
        }
        return httpx.Response(200, json=body)

    service = FetchEvaluationService(
        enabled=True,
        agent_url="http://127.0.0.1:8100/evaluate",
        api_key="fetch-key",
        asi_api_key="asi-key",
        asi_model="asi1",
        timeout_seconds=180,
        transport=httpx.MockTransport(handler),
    )

    result = service.evaluate(
        project_name="UXRay Demo",
        project_url="https://example.com",
        issues=[
            AnalysisIssue(
                issue_type="cta_feedback",
                title="Primary signup CTA appears disabled",
                summary="The button stayed disabled after click.",
                severity="high",
                route="/signup",
                evidence=["No feedback shown"],
                confidence=0.9,
            )
        ],
    )

    assert result.status == "completed"
    assert result.evaluations[0].source == "fetch_ai_asi_fallback"
    assert result.error is None


def test_fetch_evaluation_service_exposes_relay_failure_reason() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "failed",
                "response_json": "",
                "error": "Timed out waiting for hosted orchestrator response.",
            },
        )

    service = FetchEvaluationService(
        enabled=True,
        agent_url="http://127.0.0.1:8100/evaluate",
        api_key="fetch-key",
        transport=httpx.MockTransport(handler),
    )

    result = service.evaluate(
        project_name="UXRay Demo",
        project_url="https://example.com",
        issues=[
            AnalysisIssue(
                issue_type="cta_feedback",
                title="Primary signup CTA appears disabled",
                summary="The button stayed disabled after click.",
                severity="high",
                route="/signup",
                evidence=["No feedback shown"],
                confidence=0.9,
            )
        ],
    )

    assert result.status == "failed"
    assert result.error == "Timed out waiting for hosted orchestrator response."
