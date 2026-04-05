from __future__ import annotations

import json
import re

import httpx

from app.schemas import AnalysisIssue, EvaluationResult


class FetchEvaluationService:
    def __init__(
        self,
        enabled: bool,
        agent_url: str | None,
        api_key: str | None,
        timeout_seconds: float = 45.0,
        asi_api_key: str | None = None,
        asi_model: str = "asi1-mini",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.enabled = enabled
        self.agent_url = agent_url
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.asi_api_key = asi_api_key or ""
        self.asi_model = asi_model
        self.transport = transport

    def evaluate(
        self,
        project_name: str,
        project_url: str,
        issues: list[AnalysisIssue],
    ) -> EvaluationResult:
        if not self.enabled or not self.agent_url or not self.api_key or not issues:
            return EvaluationResult(status="skipped", evaluations=[], error=None)

        request_payload = {
            "project_name": project_name,
            "project_url": project_url,
            "issues": [
                {
                    "issue_id": f"{issue.issue_type}:{index}",
                    "issue_title": issue.title,
                    "route": issue.route,
                    "persona": "default_user",
                    "viewport": "desktop",
                    "issue_type": issue.issue_type,
                    "severity": issue.severity,
                    "evidence": issue.evidence,
                    "screenshot_summary": issue.summary,
                    "dom_snippet": "",
                    "custom_audience": None,
                }
                for index, issue in enumerate(issues, start=1)
            ],
        }

        relay_result = self._evaluate_via_relay(request_payload)
        if relay_result.status == "completed":
            return relay_result

        if self.asi_api_key:
            fallback_result = self._evaluate_via_asi(request_payload)
            if fallback_result.status == "completed":
                return fallback_result
            if relay_result.error and fallback_result.error:
                fallback_result.error = (
                    f"{relay_result.error} Fallback ASI review also failed: {fallback_result.error}"
                )
            return fallback_result

        return relay_result

    def _evaluate_via_relay(self, request_payload: dict) -> EvaluationResult:
        try:
            with httpx.Client(
                transport=self.transport,
                timeout=self.timeout_seconds,
            ) as client:
                response = client.post(
                    self.agent_url,
                    json={
                        "api_key": self.api_key,
                        "payload_json": json.dumps(request_payload),
                    },
                )
            response.raise_for_status()
            body = response.json()
            if body.get("status") != "completed":
                return EvaluationResult(
                    status="failed",
                    evaluations=[],
                    error=body.get("error") or "Relay did not return a completed response.",
                )
            response_payload = body.get("response_json")
            if not response_payload:
                return EvaluationResult(
                    status="failed",
                    evaluations=[],
                    error="Relay completed without a response_json payload.",
                )
            parsed = json.loads(response_payload)
            return self._map_recommendations(parsed, source="fetch_ai_orchestrator")
        except httpx.TimeoutException:
            return EvaluationResult(
                status="failed",
                evaluations=[],
                error=(
                    "Timed out waiting for the local Fetch relay after "
                    f"{int(self.timeout_seconds)} seconds."
                ),
            )
        except Exception as exc:
            return EvaluationResult(status="failed", evaluations=[], error=str(exc))

    def _evaluate_via_asi(self, request_payload: dict) -> EvaluationResult:
        prompt = (
            "You are UXRay's Fetch.ai fallback reviewer. Read the UX issues and return strict JSON with the shape "
            "{\"recommendations\":[{\"issue_title\":string,\"final_priority\":string,"
            "\"audience_impact_summary\":string,\"merged_rationale\":string}]}. "
            "Use final_priority values of critical, high, medium, or low. Keep recommendations concise and implementation-oriented.\n\n"
            f"{json.dumps(request_payload)}"
        )
        payload = {
            "model": self.asi_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You synthesize UX issue severity and priority across likely user audiences. "
                        "Return only valid JSON that matches the requested schema."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.asi_api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(
                transport=self.transport,
                timeout=min(self.timeout_seconds, 60.0),
            ) as client:
                response = client.post(
                    "https://api.asi1.ai/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            parsed = self._parse_json_payload(content)
            return self._map_recommendations(parsed, source="fetch_ai_asi_fallback")
        except Exception as exc:
            return EvaluationResult(status="failed", evaluations=[], error=str(exc))

    def _map_recommendations(self, parsed: dict, *, source: str) -> EvaluationResult:
        return EvaluationResult(
            status="completed",
            evaluations=[
                {
                    "issue_title": recommendation["issue_title"],
                    "audience": "multi_agent_synthesis",
                    "priority": recommendation["final_priority"],
                    "impact_summary": recommendation["audience_impact_summary"],
                    "rationale": recommendation["merged_rationale"],
                    "source": source,
                    "status": "completed",
                }
                for recommendation in parsed.get("recommendations", [])
            ],
            error=None,
        )

    def _parse_json_payload(self, content: str) -> dict:
        stripped = content.strip()
        fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, re.DOTALL)
        if fenced_match:
            stripped = fenced_match.group(1).strip()
        else:
            start = stripped.find("{")
            end = stripped.rfind("}")
            if start != -1 and end != -1 and end >= start:
                stripped = stripped[start : end + 1]
        return json.loads(stripped)
