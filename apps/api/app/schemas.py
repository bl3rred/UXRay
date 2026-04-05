from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


RunStatus = Literal["queued", "running", "completed", "failed"]
Severity = Literal["high", "medium", "low"]
EvaluationStatus = Literal["pending", "running", "completed", "skipped", "failed"]
PersonaKey = Literal["first_time_visitor", "intent_driven", "trust_evaluator", "custom_audience"]
PersonaResultMode = Literal["structured", "salvaged", "failed"]
RepoBuildStatus = Literal["not_requested", "pending", "running", "completed", "failed"]
TargetSource = Literal["site", "repo_preview"]


class APIEnvelope(BaseModel):
    success: bool = True
    data: Any | None = None
    error: str | None = None


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: HttpUrl | None = None
    repo_url: HttpUrl | None = None

    @model_validator(mode="after")
    def validate_target(self) -> "ProjectCreate":
        if not self.url and not self.repo_url:
            raise ValueError("Either website URL or public repository URL is required.")
        return self


class RunCreate(BaseModel):
    custom_audience: str | None = None


class ProjectSummary(BaseModel):
    id: str
    name: str
    url: str | None
    repo_url: str | None
    created_at: str


class ProgressRecord(BaseModel):
    id: str
    summary: str
    type: str
    created_at: str
    screenshot_url: str | None = None


class IssueRecord(BaseModel):
    id: str
    issue_type: str
    title: str
    summary: str
    severity: Severity
    route: str
    evidence: list[str]
    confidence: float
    personas: list[str] = Field(default_factory=list)
    screenshot_url: str | None = None


class RecommendationRecord(BaseModel):
    id: str
    title: str
    summary: str
    likely_fix: str
    source: str


class ArtifactRecord(BaseModel):
    id: str
    kind: str
    label: str
    path_or_url: str


class RunSummary(BaseModel):
    id: str
    project_id: str
    status: RunStatus
    live_url: str | None = None
    target_url: str | None = None
    local_preview_url: str | None = None
    public_preview_url: str | None = None
    target_source: TargetSource = "site"
    browser_use_model: str
    evaluation_status: EvaluationStatus
    evaluation_error: str | None = None
    source_review_status: EvaluationStatus = "skipped"
    source_review_error: str | None = None
    repo_build_status: RepoBuildStatus = "not_requested"
    repo_build_error: str | None = None
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    error_message: str | None = None
    custom_audience: str | None = None


class EvaluationRecord(BaseModel):
    id: str
    issue_title: str
    audience: str
    priority: str
    impact_summary: str
    rationale: str
    source: str
    status: EvaluationStatus


class RunDetail(RunSummary):
    issues: list[IssueRecord]
    recommendations: list[RecommendationRecord]
    artifacts: list[ArtifactRecord]
    progress: list[ProgressRecord]
    evaluations: list[EvaluationRecord]
    persona_sessions: list["PersonaSessionRecord"] = Field(default_factory=list)


class PersonaObservationRecord(BaseModel):
    id: str
    route: str
    title: str
    description: str
    severity: Severity
    evidence: list[str] = Field(default_factory=list)
    screenshot_url: str | None = None


class PersonaSessionRecord(BaseModel):
    id: str
    persona_key: str
    display_label: str
    mission: str
    status: RunStatus
    result_mode: PersonaResultMode | None = None
    live_url: str | None = None
    final_url: str | None = None
    summary: str | None = None
    error_message: str | None = None
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    observations: list[PersonaObservationRecord] = Field(default_factory=list)
    progress: list[ProgressRecord] = Field(default_factory=list)
    artifacts: list[ArtifactRecord] = Field(default_factory=list)


class ProjectDetail(ProjectSummary):
    runs: list[RunSummary]


class AdapterObservation(BaseModel):
    route: str
    title: str
    description: str
    severity: Severity
    evidence: list[str] = Field(default_factory=list)
    screenshot_url: str | None = None
    personas: list[str] = Field(default_factory=list)


class AdapterRunResult(BaseModel):
    result_mode: Literal["structured", "salvaged"] = "structured"
    live_url: str | None = None
    final_url: str | None = None
    summary: str
    observations: list[AdapterObservation] = Field(default_factory=list)
    artifacts: list[dict[str, str]] = Field(default_factory=list)
    messages: list[dict[str, str | None]] = Field(default_factory=list)


class AnalysisIssue(BaseModel):
    issue_type: str
    title: str
    summary: str
    severity: Severity
    route: str
    evidence: list[str]
    confidence: float
    personas: list[str] = Field(default_factory=list)
    screenshot_url: str | None = None


class AnalysisRecommendation(BaseModel):
    title: str
    summary: str
    likely_fix: str
    source: str = "analyzer"


class AnalysisArtifact(BaseModel):
    kind: str
    label: str
    path_or_url: str


class AnalysisResult(BaseModel):
    issues: list[AnalysisIssue]
    recommendations: list[AnalysisRecommendation]
    artifacts: list[AnalysisArtifact]


class EvaluationItem(BaseModel):
    issue_title: str
    audience: str
    priority: str
    impact_summary: str
    rationale: str
    source: str = "fetch_ai"
    status: EvaluationStatus = "completed"


class EvaluationResult(BaseModel):
    status: EvaluationStatus
    evaluations: list[EvaluationItem] = Field(default_factory=list)
    error: str | None = None


class BrowserUseAuditObservation(BaseModel):
    route: str
    title: str
    description: str
    severity: Severity
    evidence: list[str] = Field(default_factory=list)
    screenshot_url: str | None = None


class BrowserUseAuditOutput(BaseModel):
    summary: str
    final_url: str | None = None
    observations: list[BrowserUseAuditObservation] = Field(default_factory=list)


class BrowserUseMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    summary: str | None = None
    type: str | None = None
    screenshot_url: str | None = None


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class PersonaRunResult(BaseModel):
    persona_key: str
    display_label: str
    mission: str | None = None
    status: RunStatus = "completed"
    result_mode: PersonaResultMode | None = None
    live_url: str | None = None
    final_url: str | None = None
    summary: str | None = None
    error_message: str | None = None
    observations: list[AdapterObservation] = Field(default_factory=list)
    artifacts: list[dict[str, str]] = Field(default_factory=list)


RunDetail.model_rebuild()
