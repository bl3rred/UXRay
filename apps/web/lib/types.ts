export type RunStatus = "queued" | "running" | "completed" | "failed";
export type Severity = "high" | "medium" | "low";
export type EvaluationStatus =
  | "pending"
  | "running"
  | "completed"
  | "skipped"
  | "failed";
export type RepoBuildStatus =
  | "not_requested"
  | "pending"
  | "running"
  | "completed"
  | "failed";
export type TargetSource = "site" | "repo_preview";

export type ProjectSummary = {
  id: string;
  name: string;
  url: string | null;
  repo_url: string | null;
  created_at: string;
};

export type RunSummary = {
  id: string;
  project_id: string;
  status: RunStatus;
  live_url: string | null;
  target_url: string | null;
  target_source: TargetSource;
  browser_use_model: string;
  evaluation_status: EvaluationStatus;
  evaluation_error: string | null;
  source_review_status: EvaluationStatus;
  source_review_error: string | null;
  repo_build_status: RepoBuildStatus;
  repo_build_error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  custom_audience: string | null;
};

export type ProgressRecord = {
  id: string;
  summary: string;
  type: string;
  created_at: string;
  screenshot_url: string | null;
};

export type IssueRecord = {
  id: string;
  issue_type: string;
  title: string;
  summary: string;
  severity: Severity;
  route: string;
  evidence: string[];
  confidence: number;
  personas: string[];
  screenshot_url: string | null;
};

export type RecommendationRecord = {
  id: string;
  title: string;
  summary: string;
  likely_fix: string;
  source: string;
};

export type ArtifactRecord = {
  id: string;
  kind: string;
  label: string;
  path_or_url: string;
};

export type EvaluationRecord = {
  id: string;
  issue_title: string;
  audience: string;
  priority: string;
  impact_summary: string;
  rationale: string;
  source: string;
  status: EvaluationStatus;
};

export type RunDetail = RunSummary & {
  issues: IssueRecord[];
  recommendations: RecommendationRecord[];
  artifacts: ArtifactRecord[];
  progress: ProgressRecord[];
  evaluations: EvaluationRecord[];
  persona_sessions: PersonaSessionRecord[];
};

export type ProjectDetail = ProjectSummary & {
  runs: RunSummary[];
};

export type ProjectInput = {
  name: string;
  url?: string;
  repo_url?: string;
};

export type RunInput = {
  custom_audience?: string;
};

export type PersonaObservationRecord = {
  id: string;
  route: string;
  title: string;
  description: string;
  severity: Severity;
  evidence: string[];
  screenshot_url: string | null;
};

export type PersonaResultMode = "structured" | "salvaged" | "failed";

export type PersonaSessionRecord = {
  id: string;
  persona_key: string;
  display_label: string;
  mission: string;
  status: RunStatus;
  result_mode?: PersonaResultMode | null;
  live_url: string | null;
  final_url: string | null;
  summary: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  observations: PersonaObservationRecord[];
  progress: ProgressRecord[];
  artifacts: ArtifactRecord[];
};
