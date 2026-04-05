from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any
import re

from app.schemas import (
    AnalysisResult,
    ArtifactRecord,
    EvaluationRecord,
    EvaluationResult,
    IssueRecord,
    PersonaObservationRecord,
    PersonaSessionRecord,
    ProgressRecord,
    ProjectDetail,
    ProjectSummary,
    RecommendationRecord,
    RunDetail,
    RunSummary,
    utc_now_iso,
)


CREATE_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        owner_id TEXT,
        guest_session_id TEXT,
        name TEXT NOT NULL,
        url TEXT NOT NULL,
        repo_url TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS runs (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        status TEXT NOT NULL,
        live_url TEXT,
        target_url TEXT,
        local_preview_url TEXT,
        public_preview_url TEXT,
        target_source TEXT NOT NULL DEFAULT 'site',
        browser_use_model TEXT NOT NULL DEFAULT 'claude-sonnet-4.6',
        evaluation_status TEXT NOT NULL DEFAULT 'pending',
        evaluation_error TEXT,
        source_review_status TEXT NOT NULL DEFAULT 'skipped',
        source_review_error TEXT,
        repo_build_status TEXT NOT NULL DEFAULT 'not_requested',
        repo_build_error TEXT,
        custom_audience TEXT,
        browser_use_session_id TEXT,
        browser_use_task_id TEXT,
        created_at TEXT NOT NULL,
        started_at TEXT,
        completed_at TEXT,
        error_message TEXT,
        final_url TEXT,
        summary TEXT,
        FOREIGN KEY(project_id) REFERENCES projects(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS issues (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        issue_type TEXT NOT NULL,
        title TEXT NOT NULL,
        summary TEXT NOT NULL,
        severity TEXT NOT NULL,
        route TEXT NOT NULL,
        evidence_json TEXT NOT NULL,
        confidence REAL NOT NULL,
        personas_json TEXT NOT NULL DEFAULT '[]',
        screenshot_url TEXT,
        FOREIGN KEY(run_id) REFERENCES runs(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS recommendations (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        title TEXT NOT NULL,
        summary TEXT NOT NULL,
        likely_fix TEXT NOT NULL,
        source TEXT NOT NULL,
        FOREIGN KEY(run_id) REFERENCES runs(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS artifacts (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        label TEXT NOT NULL,
        path_or_url TEXT NOT NULL,
        FOREIGN KEY(run_id) REFERENCES runs(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS progress_events (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        summary TEXT NOT NULL,
        type TEXT NOT NULL,
        created_at TEXT NOT NULL,
        screenshot_url TEXT,
        FOREIGN KEY(run_id) REFERENCES runs(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS evaluations (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        issue_title TEXT NOT NULL,
        audience TEXT NOT NULL,
        priority TEXT NOT NULL,
        impact_summary TEXT NOT NULL,
        rationale TEXT NOT NULL,
        source TEXT NOT NULL,
        status TEXT NOT NULL,
        FOREIGN KEY(run_id) REFERENCES runs(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS persona_sessions (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        persona_key TEXT NOT NULL,
        display_label TEXT NOT NULL,
        mission TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL,
        result_mode TEXT,
        live_url TEXT,
        final_url TEXT,
        summary TEXT,
        error_message TEXT,
        created_at TEXT NOT NULL,
        started_at TEXT,
        completed_at TEXT,
        FOREIGN KEY(run_id) REFERENCES runs(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS persona_observations (
        id TEXT PRIMARY KEY,
        persona_session_id TEXT NOT NULL,
        route TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        severity TEXT NOT NULL,
        evidence_json TEXT NOT NULL,
        screenshot_url TEXT,
        FOREIGN KEY(persona_session_id) REFERENCES persona_sessions(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS persona_progress_events (
        id TEXT PRIMARY KEY,
        persona_session_id TEXT NOT NULL,
        summary TEXT NOT NULL,
        type TEXT NOT NULL,
        created_at TEXT NOT NULL,
        screenshot_url TEXT,
        FOREIGN KEY(persona_session_id) REFERENCES persona_sessions(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS persona_artifacts (
        id TEXT PRIMARY KEY,
        persona_session_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        label TEXT NOT NULL,
        path_or_url TEXT NOT NULL,
        FOREIGN KEY(persona_session_id) REFERENCES persona_sessions(id)
    )
    """,
]


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def _normalized_issue_terms(value: str) -> set[str]:
    return {
        token
        for token in re.sub(r"[^a-z0-9]+", " ", value.lower()).split()
        if len(token) > 2
    }


def _first_screenshot_progress(progress_items: list[ProgressRecord]) -> str | None:
    return next(
        (progress_item.screenshot_url for progress_item in progress_items if progress_item.screenshot_url),
        None,
    )


def _matching_screenshot_artifact(
    artifacts: list[ArtifactRecord],
    issue_title: str,
    issue_terms: set[str],
) -> str | None:
    matching_artifact = next(
        (
            artifact
            for artifact in artifacts
            if artifact.kind == "screenshot"
            and (
                issue_title.lower() in artifact.label.lower()
                or bool(issue_terms & _normalized_issue_terms(artifact.label))
            )
        ),
        None,
    )
    if matching_artifact is not None:
        return matching_artifact.path_or_url
    return next(
        (artifact.path_or_url for artifact in artifacts if artifact.kind == "screenshot"),
        None,
    )


class SQLiteStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def init_db(self) -> None:
        with self.connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            for statement in CREATE_STATEMENTS:
                connection.execute(statement)
            self._ensure_column(
                connection,
                table_name="projects",
                column_name="owner_id",
                column_sql="TEXT",
            )
            self._ensure_column(
                connection,
                table_name="projects",
                column_name="guest_session_id",
                column_sql="TEXT",
            )
            self._ensure_column(
                connection,
                table_name="runs",
                column_name="target_url",
                column_sql="TEXT",
            )
            self._ensure_column(
                connection,
                table_name="runs",
                column_name="local_preview_url",
                column_sql="TEXT",
            )
            self._ensure_column(
                connection,
                table_name="runs",
                column_name="public_preview_url",
                column_sql="TEXT",
            )
            self._ensure_column(
                connection,
                table_name="runs",
                column_name="target_source",
                column_sql="TEXT NOT NULL DEFAULT 'site'",
            )
            self._ensure_column(
                connection,
                table_name="runs",
                column_name="browser_use_model",
                column_sql="TEXT NOT NULL DEFAULT 'claude-sonnet-4.6'",
            )
            self._ensure_column(
                connection,
                table_name="runs",
                column_name="evaluation_status",
                column_sql="TEXT NOT NULL DEFAULT 'pending'",
            )
            self._ensure_column(
                connection,
                table_name="runs",
                column_name="evaluation_error",
                column_sql="TEXT",
            )
            self._ensure_column(
                connection,
                table_name="runs",
                column_name="source_review_status",
                column_sql="TEXT NOT NULL DEFAULT 'skipped'",
            )
            self._ensure_column(
                connection,
                table_name="runs",
                column_name="source_review_error",
                column_sql="TEXT",
            )
            self._ensure_column(
                connection,
                table_name="runs",
                column_name="repo_build_status",
                column_sql="TEXT NOT NULL DEFAULT 'not_requested'",
            )
            self._ensure_column(
                connection,
                table_name="runs",
                column_name="repo_build_error",
                column_sql="TEXT",
            )
            self._ensure_column(
                connection,
                table_name="runs",
                column_name="custom_audience",
                column_sql="TEXT",
            )
            self._ensure_column(
                connection,
                table_name="issues",
                column_name="personas_json",
                column_sql="TEXT NOT NULL DEFAULT '[]'",
            )
            self._ensure_column(
                connection,
                table_name="issues",
                column_name="screenshot_url",
                column_sql="TEXT",
            )
            self._ensure_column(
                connection,
                table_name="persona_sessions",
                column_name="mission",
                column_sql="TEXT NOT NULL DEFAULT ''",
            )
            self._ensure_column(
                connection,
                table_name="persona_sessions",
                column_name="result_mode",
                column_sql="TEXT",
            )
            connection.commit()

    def _ensure_column(
        self,
        connection: sqlite3.Connection,
        table_name: str,
        column_name: str,
        column_sql: str,
    ) -> None:
        existing = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name in existing:
            return
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"
        )

    def _project_scope_clause(
        self,
        owner_id: str | None,
        guest_session_id: str | None,
    ) -> tuple[str, tuple[Any, ...]]:
        if owner_id:
            return "owner_id = ?", (owner_id,)
        if guest_session_id:
            return "guest_session_id = ?", (guest_session_id,)
        return "1 = 0", ()

    def create_project(
        self,
        name: str,
        url: str | None,
        repo_url: str | None,
        *,
        owner_id: str | None,
        guest_session_id: str | None,
    ) -> ProjectSummary:
        project_id = f"project_{uuid.uuid4().hex[:12]}"
        created_at = utc_now_iso()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO projects (id, owner_id, guest_session_id, name, url, repo_url, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (project_id, owner_id, guest_session_id, name, url or "", repo_url, created_at),
            )
            connection.commit()
        return ProjectSummary(
            id=project_id,
            name=name,
            url=url,
            repo_url=repo_url,
            created_at=created_at,
        )

    def list_projects(
        self,
        *,
        owner_id: str | None,
        guest_session_id: str | None,
    ) -> list[ProjectSummary]:
        where_clause, params = self._project_scope_clause(owner_id, guest_session_id)
        with self.connection() as connection:
            rows = connection.execute(
                f"SELECT id, name, url, repo_url, created_at FROM projects WHERE {where_clause} ORDER BY created_at DESC",
                params,
            ).fetchall()
        return [
            ProjectSummary(
                **{
                    **dict(row),
                    "url": dict(row)["url"] or None,
                }
            )
            for row in rows
        ]

    def get_project(
        self,
        project_id: str,
        *,
        owner_id: str | None,
        guest_session_id: str | None,
    ) -> ProjectDetail | None:
        where_clause, params = self._project_scope_clause(owner_id, guest_session_id)
        with self.connection() as connection:
            project = _row_to_dict(
                connection.execute(
                    f"SELECT id, name, url, repo_url, created_at FROM projects WHERE id = ? AND {where_clause}",
                    (project_id, *params),
                ).fetchone()
            )
        if project is None:
            return None
        return ProjectDetail(
            **{**project, "url": project["url"] or None},
            runs=self.list_runs(
                project_id,
                owner_id=owner_id,
                guest_session_id=guest_session_id,
            ),
        )

    def create_run(
        self,
        project_id: str,
        browser_use_model: str,
        repo_build_requested: bool = False,
        custom_audience: str | None = None,
        source_review_requested: bool = False,
    ) -> RunSummary:
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        created_at = utc_now_iso()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO runs (
                    id, project_id, status, target_source, browser_use_model, evaluation_status,
                    source_review_status, repo_build_status, custom_audience, created_at
                )
                VALUES (?, ?, 'queued', 'site', ?, 'pending', ?, ?, ?, ?)
                """,
                (
                    run_id,
                    project_id,
                    browser_use_model,
                    "pending" if source_review_requested else "skipped",
                    "pending" if repo_build_requested else "not_requested",
                    custom_audience,
                    created_at,
                ),
            )
            connection.commit()
        return RunSummary(
            id=run_id,
            project_id=project_id,
            status="queued",
            target_url=None,
            local_preview_url=None,
            public_preview_url=None,
            target_source="site",
            browser_use_model=browser_use_model,
            evaluation_status="pending",
            evaluation_error=None,
            source_review_status="pending" if source_review_requested else "skipped",
            source_review_error=None,
            repo_build_status="pending" if repo_build_requested else "not_requested",
            repo_build_error=None,
            created_at=created_at,
            custom_audience=custom_audience,
        )

    def list_runs(
        self,
        project_id: str,
        *,
        owner_id: str | None,
        guest_session_id: str | None,
    ) -> list[RunSummary]:
        where_clause, params = self._project_scope_clause(owner_id, guest_session_id)
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT id, project_id, status, live_url,
                       target_url, local_preview_url, public_preview_url,
                       COALESCE(target_source, 'site') AS target_source,
                       COALESCE(browser_use_model, 'claude-sonnet-4.6') AS browser_use_model,
                       COALESCE(evaluation_status, 'pending') AS evaluation_status,
                       evaluation_error,
                       COALESCE(source_review_status, 'skipped') AS source_review_status,
                       source_review_error,
                       COALESCE(repo_build_status, 'not_requested') AS repo_build_status,
                       repo_build_error,
                       custom_audience,
                       created_at, started_at, completed_at, error_message
                FROM runs
                WHERE project_id = ?
                  AND EXISTS (
                    SELECT 1 FROM projects
                    WHERE projects.id = runs.project_id
                      AND """
                + where_clause
                + """
                  )
                ORDER BY created_at DESC
                """,
                (project_id, *params),
            ).fetchall()
        return [RunSummary(**dict(row)) for row in rows]

    def get_run_detail(
        self,
        run_id: str,
        *,
        owner_id: str | None,
        guest_session_id: str | None,
    ) -> RunDetail | None:
        where_clause, params = self._project_scope_clause(owner_id, guest_session_id)
        with self.connection() as connection:
            run = _row_to_dict(
                connection.execute(
                    """
                    SELECT id, project_id, status, live_url,
                           target_url, local_preview_url, public_preview_url,
                           COALESCE(target_source, 'site') AS target_source,
                           COALESCE(browser_use_model, 'claude-sonnet-4.6') AS browser_use_model,
                           COALESCE(evaluation_status, 'pending') AS evaluation_status,
                           evaluation_error,
                           COALESCE(source_review_status, 'skipped') AS source_review_status,
                           source_review_error,
                           COALESCE(repo_build_status, 'not_requested') AS repo_build_status,
                           repo_build_error,
                           custom_audience,
                           created_at, started_at, completed_at, error_message
                    FROM runs
                    WHERE id = ?
                      AND EXISTS (
                        SELECT 1 FROM projects
                        WHERE projects.id = runs.project_id
                          AND """
                    + where_clause
                    + """
                      )
                    """,
                    (run_id, *params),
                ).fetchone()
            )
            if run is None:
                return None

            issues = [
                IssueRecord(
                    id=row["id"],
                    issue_type=row["issue_type"],
                    title=row["title"],
                    summary=row["summary"],
                    severity=row["severity"],
                    route=row["route"],
                    evidence=json.loads(row["evidence_json"]),
                    confidence=row["confidence"],
                    personas=json.loads(row["personas_json"] or "[]"),
                    screenshot_url=row["screenshot_url"],
                )
                for row in connection.execute(
                    "SELECT * FROM issues WHERE run_id = ? ORDER BY severity DESC, title ASC",
                    (run_id,),
                ).fetchall()
            ]
            recommendations = [
                RecommendationRecord(**dict(row))
                for row in connection.execute(
                    "SELECT * FROM recommendations WHERE run_id = ? ORDER BY title ASC",
                    (run_id,),
                ).fetchall()
            ]
            artifacts = [
                ArtifactRecord(**dict(row))
                for row in connection.execute(
                    "SELECT * FROM artifacts WHERE run_id = ? ORDER BY label ASC",
                    (run_id,),
                ).fetchall()
            ]
            progress = [
                ProgressRecord(**dict(row))
                for row in connection.execute(
                    """
                    SELECT * FROM progress_events
                    WHERE run_id = ?
                    ORDER BY created_at ASC
                    """,
                    (run_id,),
                ).fetchall()
            ]
            evaluations = [
                EvaluationRecord(**dict(row))
                for row in connection.execute(
                    """
                    SELECT * FROM evaluations
                    WHERE run_id = ?
                    ORDER BY priority ASC, audience ASC
                    """,
                    (run_id,),
                ).fetchall()
            ]
            persona_session_rows = connection.execute(
                """
                SELECT * FROM persona_sessions
                WHERE run_id = ?
                ORDER BY created_at ASC, display_label ASC
                """,
                (run_id,),
            ).fetchall()

            persona_sessions: list[PersonaSessionRecord] = []
            for row in persona_session_rows:
                persona_session_id = row["id"]
                persona_observations = [
                    PersonaObservationRecord(
                        id=observation_row["id"],
                        route=observation_row["route"],
                        title=observation_row["title"],
                        description=observation_row["description"],
                        severity=observation_row["severity"],
                        evidence=json.loads(observation_row["evidence_json"]),
                        screenshot_url=observation_row["screenshot_url"],
                    )
                    for observation_row in connection.execute(
                        """
                        SELECT * FROM persona_observations
                        WHERE persona_session_id = ?
                        ORDER BY title ASC
                        """,
                        (persona_session_id,),
                    ).fetchall()
                ]
                persona_progress = [
                    ProgressRecord(**dict(progress_row))
                    for progress_row in connection.execute(
                        """
                        SELECT id, summary, type, created_at, screenshot_url
                        FROM persona_progress_events
                        WHERE persona_session_id = ?
                        ORDER BY created_at ASC
                        """,
                        (persona_session_id,),
                    ).fetchall()
                ]
                persona_artifacts = [
                    ArtifactRecord(**dict(artifact_row))
                    for artifact_row in connection.execute(
                        """
                        SELECT id, kind, label, path_or_url
                        FROM persona_artifacts
                        WHERE persona_session_id = ?
                        ORDER BY label ASC
                        """,
                        (persona_session_id,),
                    ).fetchall()
                ]
                persona_sessions.append(
                    PersonaSessionRecord(
                        **dict(row),
                        observations=persona_observations,
                        progress=persona_progress,
                        artifacts=persona_artifacts,
                    )
                )
        for issue in issues:
            if issue.screenshot_url:
                continue
            issue_terms = _normalized_issue_terms(f"{issue.title} {issue.summary}")
            for persona in persona_sessions:
                matching_observation = next(
                    (
                        observation
                        for observation in persona.observations
                        if observation.screenshot_url
                        and (
                            (observation.title == issue.title and observation.route == issue.route)
                            or (
                                observation.route == issue.route
                                and bool(
                                    issue_terms
                                    & _normalized_issue_terms(
                                        f"{observation.title} {observation.description}"
                                    )
                                )
                            )
                        )
                    ),
                    None,
                )
                if matching_observation:
                    issue.screenshot_url = matching_observation.screenshot_url
                    break
            if issue.screenshot_url:
                continue
            for persona in persona_sessions:
                persona_progress_screenshot = _first_screenshot_progress(persona.progress)
                if persona_progress_screenshot:
                    issue.screenshot_url = persona_progress_screenshot
                    break
            if issue.screenshot_url:
                continue
            run_progress_screenshot = _first_screenshot_progress(progress)
            if run_progress_screenshot:
                issue.screenshot_url = run_progress_screenshot
                continue
            for persona in persona_sessions:
                persona_artifact_screenshot = _matching_screenshot_artifact(
                    persona.artifacts,
                    issue.title,
                    issue_terms,
                )
                if persona_artifact_screenshot:
                    issue.screenshot_url = persona_artifact_screenshot
                    break
            if issue.screenshot_url:
                continue
            run_artifact_screenshot = _matching_screenshot_artifact(
                artifacts,
                issue.title,
                issue_terms,
            )
            if run_artifact_screenshot:
                issue.screenshot_url = run_artifact_screenshot
        return RunDetail(
            **run,
            issues=issues,
            recommendations=recommendations,
            artifacts=artifacts,
            progress=progress,
            evaluations=evaluations,
            persona_sessions=persona_sessions,
        )

    def claim_next_run(self) -> dict[str, str] | None:
        with self.connection() as connection:
            connection.isolation_level = None
            connection.execute("BEGIN IMMEDIATE")
            run = _row_to_dict(
                connection.execute(
                    """
                    SELECT runs.id AS run_id, runs.project_id,
                           COALESCE(runs.browser_use_model, 'claude-sonnet-4.6') AS browser_use_model,
                           runs.custom_audience,
                           projects.name, projects.url, projects.repo_url
                    FROM runs
                    JOIN projects ON projects.id = runs.project_id
                    WHERE runs.status = 'queued'
                    ORDER BY runs.created_at ASC
                    LIMIT 1
                    """
                ).fetchone()
            )
            if run is None:
                connection.execute("COMMIT")
                return None

            connection.execute(
                """
                UPDATE runs
                SET status = 'running', started_at = ?
                WHERE id = ?
                """,
                (utc_now_iso(), run["run_id"]),
            )
            connection.execute("COMMIT")
        return run

    def get_run_enrichment_context(self, run_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = _row_to_dict(
                connection.execute(
                    """
                    SELECT runs.id AS run_id,
                           runs.target_url,
                           runs.local_preview_url,
                           runs.public_preview_url,
                           runs.target_source,
                           runs.evaluation_status,
                           runs.source_review_status,
                           projects.name AS project_name,
                           projects.repo_url
                    FROM runs
                    JOIN projects ON projects.id = runs.project_id
                    WHERE runs.id = ?
                    """,
                    (run_id,),
                ).fetchone()
            )
            if row is None:
                return None
            issues = [
                IssueRecord(
                    id=issue_row["id"],
                    issue_type=issue_row["issue_type"],
                    title=issue_row["title"],
                    summary=issue_row["summary"],
                    severity=issue_row["severity"],
                    route=issue_row["route"],
                    evidence=json.loads(issue_row["evidence_json"]),
                    confidence=issue_row["confidence"],
                    personas=json.loads(issue_row["personas_json"] or "[]"),
                    screenshot_url=issue_row["screenshot_url"],
                )
                for issue_row in connection.execute(
                    "SELECT * FROM issues WHERE run_id = ? ORDER BY severity DESC, title ASC",
                    (run_id,),
                ).fetchall()
            ]
        row["issues"] = issues
        return row

    def add_progress_event(
        self,
        run_id: str,
        summary: str,
        event_type: str,
        screenshot_url: str | None = None,
    ) -> None:
        event_id = f"progress_{uuid.uuid4().hex[:12]}"
        created_at = utc_now_iso()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO progress_events (id, run_id, summary, type, created_at, screenshot_url)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (event_id, run_id, summary, event_type, created_at, screenshot_url),
            )
            connection.commit()

    def update_run_live_url(self, run_id: str, live_url: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "UPDATE runs SET live_url = ? WHERE id = ?",
                (live_url, run_id),
            )
            connection.commit()

    def create_persona_session(
        self,
        run_id: str,
        persona_key: str,
        display_label: str,
        mission: str,
    ) -> PersonaSessionRecord:
        session_id = f"persona_{uuid.uuid4().hex[:12]}"
        created_at = utc_now_iso()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO persona_sessions (
                    id, run_id, persona_key, display_label, mission, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, 'queued', ?)
                """,
                (session_id, run_id, persona_key, display_label, mission, created_at),
            )
            connection.commit()
        return PersonaSessionRecord(
            id=session_id,
            persona_key=persona_key,
            display_label=display_label,
            mission=mission,
            status="queued",
            created_at=created_at,
        )

    def start_persona_session(self, persona_session_id: str) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE persona_sessions
                SET status = 'running', started_at = ?
                WHERE id = ?
                """,
                (utc_now_iso(), persona_session_id),
            )
            connection.commit()

    def update_persona_session_live_url(self, persona_session_id: str, live_url: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "UPDATE persona_sessions SET live_url = ? WHERE id = ?",
                (live_url, persona_session_id),
            )
            connection.commit()

    def add_persona_progress_event(
        self,
        persona_session_id: str,
        summary: str,
        event_type: str,
        screenshot_url: str | None = None,
    ) -> None:
        event_id = f"persona_progress_{uuid.uuid4().hex[:12]}"
        created_at = utc_now_iso()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO persona_progress_events (id, persona_session_id, summary, type, created_at, screenshot_url)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (event_id, persona_session_id, summary, event_type, created_at, screenshot_url),
            )
            connection.commit()

    def complete_persona_session(
        self,
        persona_session_id: str,
        *,
        result_mode: str | None,
        live_url: str | None,
        final_url: str | None,
        summary: str | None,
        observations: list[dict[str, Any]],
        artifacts: list[dict[str, str]],
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE persona_sessions
                SET status = 'completed',
                    result_mode = ?,
                    live_url = COALESCE(?, live_url),
                    final_url = ?,
                    summary = ?,
                    completed_at = ?
                WHERE id = ?
                """,
                (result_mode, live_url, final_url, summary, utc_now_iso(), persona_session_id),
            )
            for observation in observations:
                connection.execute(
                    """
                    INSERT INTO persona_observations (
                        id, persona_session_id, route, title, description, severity, evidence_json, screenshot_url
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"persona_obs_{uuid.uuid4().hex[:12]}",
                        persona_session_id,
                        observation["route"],
                        observation["title"],
                        observation["description"],
                        observation["severity"],
                        json.dumps(observation["evidence"]),
                        observation.get("screenshot_url"),
                    ),
                )
            for artifact in artifacts:
                connection.execute(
                    """
                    INSERT INTO persona_artifacts (id, persona_session_id, kind, label, path_or_url)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        f"persona_artifact_{uuid.uuid4().hex[:12]}",
                        persona_session_id,
                        artifact.get("kind", "external"),
                        artifact.get("label", "Artifact"),
                        artifact.get("path_or_url", ""),
                    ),
                )
            connection.commit()

    def fail_persona_session(
        self,
        persona_session_id: str,
        error_message: str,
        *,
        live_url: str | None = None,
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE persona_sessions
                SET status = 'failed',
                    result_mode = 'failed',
                    live_url = COALESCE(?, live_url),
                    error_message = ?,
                    completed_at = ?
                WHERE id = ?
                """,
                (live_url, error_message, utc_now_iso(), persona_session_id),
            )
            connection.commit()

    def complete_run(
        self,
        run_id: str,
        live_url: str | None,
        final_url: str | None,
        target_url: str | None,
        local_preview_url: str | None,
        public_preview_url: str | None,
        target_source: str,
        summary: str,
        analysis: AnalysisResult,
        *,
        evaluation_status: str,
        evaluation_error: str | None,
        source_review_status: str,
        source_review_error: str | None,
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE runs
                SET status = 'completed',
                    live_url = COALESCE(?, live_url),
                    target_url = COALESCE(?, target_url),
                    local_preview_url = COALESCE(?, local_preview_url),
                    public_preview_url = COALESCE(?, public_preview_url),
                    target_source = ?,
                    final_url = ?,
                    summary = ?,
                    evaluation_status = ?,
                    evaluation_error = ?,
                    source_review_status = ?,
                    source_review_error = ?,
                    completed_at = ?
                WHERE id = ?
                """,
                (
                    live_url,
                    target_url,
                    local_preview_url,
                    public_preview_url,
                    target_source,
                    final_url,
                    summary,
                    evaluation_status,
                    evaluation_error,
                    source_review_status,
                    source_review_error,
                    utc_now_iso(),
                    run_id,
                ),
            )
            for issue in analysis.issues:
                connection.execute(
                    """
                    INSERT INTO issues (id, run_id, issue_type, title, summary, severity, route, evidence_json, confidence, personas_json, screenshot_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"issue_{uuid.uuid4().hex[:12]}",
                        run_id,
                        issue.issue_type,
                        issue.title,
                        issue.summary,
                        issue.severity,
                        issue.route,
                        json.dumps(issue.evidence),
                        issue.confidence,
                        json.dumps(issue.personas),
                        issue.screenshot_url,
                    ),
                )
            for recommendation in analysis.recommendations:
                connection.execute(
                    """
                    INSERT INTO recommendations (id, run_id, title, summary, likely_fix, source)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"rec_{uuid.uuid4().hex[:12]}",
                        run_id,
                        recommendation.title,
                        recommendation.summary,
                        recommendation.likely_fix,
                        recommendation.source,
                    ),
                )
            for artifact in analysis.artifacts:
                connection.execute(
                    """
                    INSERT INTO artifacts (id, run_id, kind, label, path_or_url)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        f"artifact_{uuid.uuid4().hex[:12]}",
                        run_id,
                        artifact.kind,
                        artifact.label,
                        artifact.path_or_url,
                    ),
                )
            connection.commit()

    def update_evaluation_status(
        self,
        run_id: str,
        evaluation_status: str,
        evaluation_error: str | None = None,
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                "UPDATE runs SET evaluation_status = ?, evaluation_error = ? WHERE id = ?",
                (evaluation_status, evaluation_error, run_id),
            )
            connection.commit()

    def save_evaluations(self, run_id: str, evaluations: EvaluationResult) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM evaluations WHERE run_id = ?", (run_id,))
            for evaluation in evaluations.evaluations:
                connection.execute(
                    """
                    INSERT INTO evaluations (id, run_id, issue_title, audience, priority, impact_summary, rationale, source, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"evaluation_{uuid.uuid4().hex[:12]}",
                        run_id,
                        evaluation.issue_title,
                        evaluation.audience,
                        evaluation.priority,
                        evaluation.impact_summary,
                        evaluation.rationale,
                        evaluation.source,
                        evaluation.status,
                    ),
                )
            connection.commit()

    def add_recommendations(self, run_id: str, recommendations: list[RecommendationRecord]) -> None:
        with self.connection() as connection:
            for recommendation in recommendations:
                connection.execute(
                    """
                    INSERT INTO recommendations (id, run_id, title, summary, likely_fix, source)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"rec_{uuid.uuid4().hex[:12]}",
                        run_id,
                        recommendation.title,
                        recommendation.summary,
                        recommendation.likely_fix,
                        recommendation.source,
                    ),
                )
            connection.commit()

    def update_source_review_status(
        self,
        run_id: str,
        source_review_status: str,
        source_review_error: str | None = None,
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE runs
                SET source_review_status = ?, source_review_error = ?
                WHERE id = ?
                """,
                (source_review_status, source_review_error, run_id),
            )
            connection.commit()

    def update_repo_build_state(
        self,
        run_id: str,
        *,
        repo_build_status: str,
        repo_build_error: str | None,
        target_url: str | None = None,
        local_preview_url: str | None = None,
        public_preview_url: str | None = None,
        target_source: str | None = None,
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE runs
                SET repo_build_status = ?,
                    repo_build_error = ?,
                    target_url = COALESCE(?, target_url),
                    local_preview_url = COALESCE(?, local_preview_url),
                    public_preview_url = COALESCE(?, public_preview_url),
                    target_source = COALESCE(?, target_source)
                WHERE id = ?
                """,
                (
                    repo_build_status,
                    repo_build_error,
                    target_url,
                    local_preview_url,
                    public_preview_url,
                    target_source,
                    run_id,
                ),
            )
            connection.commit()

    def fail_run(self, run_id: str, error_message: str) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE runs
                SET status = 'failed',
                    evaluation_status = CASE
                        WHEN evaluation_status IN ('pending', 'running') THEN 'failed'
                        ELSE evaluation_status
                    END,
                    source_review_status = CASE
                        WHEN source_review_status IN ('pending', 'running') THEN 'skipped'
                        ELSE source_review_status
                    END,
                    source_review_error = CASE
                        WHEN source_review_status IN ('pending', 'running')
                            THEN 'Run failed before source review could start.'
                        ELSE source_review_error
                    END,
                    error_message = ?,
                    completed_at = ?
                WHERE id = ?
                """,
                (error_message, utc_now_iso(), run_id),
            )
            connection.commit()
