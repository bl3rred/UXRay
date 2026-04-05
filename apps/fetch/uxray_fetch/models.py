from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


Severity = Literal["high", "medium", "low"]
Priority = Literal["critical", "high", "medium", "low"]
ConsensusLevel = Literal["high", "medium", "low"]
OrchestrationStatus = Literal["completed", "failed"]


class IssuePacket(BaseModel):
    issue_id: str
    issue_title: str
    route: str
    persona: str
    viewport: str
    issue_type: str
    severity: Severity
    evidence: list[str] = Field(default_factory=list)
    screenshot_summary: str
    dom_snippet: str
    custom_audience: str | None = None


class AudienceReview(BaseModel):
    correlation_id: str
    issue_id: str
    agent_name: str
    audience: str
    impact_score: int = Field(ge=1, le=10)
    priority_score: int = Field(ge=1, le=10)
    fix_direction: str
    rationale: str
    round_number: int = Field(ge=1, le=2, default=1)


class BossReview(BaseModel):
    correlation_id: str
    issue_id: str
    consensus_level: ConsensusLevel
    main_conflict: str | None = None
    rebuttal_required: bool = False
    rebuttal_request: str | None = None
    summary: str


class SynthesizedRecommendation(BaseModel):
    issue_id: str
    issue_title: str
    final_priority: Priority
    audience_impact_summary: str
    merged_rationale: str
    recommended_fix_direction: str
    gpt_handoff_string: str
    consensus_level: ConsensusLevel


class EvaluateIssuesRequest(BaseModel):
    project_name: str
    project_url: str
    issues: list[IssuePacket] = Field(default_factory=list)


class EvaluateIssuesResponse(BaseModel):
    status: OrchestrationStatus
    recommendations: list[SynthesizedRecommendation] = Field(default_factory=list)
    error: str | None = None


class BackendEvaluateEnvelope(BaseModel):
    session: str
    api_key: str
    payload_json: str


class BackendEvaluateResponseEnvelope(BaseModel):
    session: str
    status: OrchestrationStatus
    response_json: str = ""
    error: str | None = None


class BridgeEvent(BaseModel):
    stage: str
    correlation_id: str
    issue_id: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
