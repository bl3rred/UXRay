import asyncio
from pathlib import Path
import uuid
import time

from app.db import SQLiteStore
from app.schemas import AdapterRunResult, AnalysisIssue, RecommendationRecord
from app.services.queue import RunWorker


class _LiveUrlAdapter:
    async def execute_run(
        self,
        *,
        run_id: str,
        project_name: str,
        project_url: str,
        model: str,
        progress_callback,
        persona_key: str,
        custom_audience: str | None = None,
    ) -> AdapterRunResult:
        await asyncio.sleep(0)
        return AdapterRunResult(
            live_url=f"https://browser-use.example/live-session/{persona_key}",
            final_url=f"{project_url.rstrip('/')}/{persona_key}",
            summary=f"{persona_key} completed.",
            observations=[],
            artifacts=[],
            messages=[],
        )


class _DisabledEvaluator:
    enabled = False


class _DisabledSourceReviewer:
    enabled = False


class _UnusedRepoBuilder:
    def close(self) -> None:
        return None


class _UnusedTunnelManager:
    def expose(self, local_url: str) -> str:
        return local_url

    def close(self) -> None:
        return None


class _RateLimitedThenSuccessfulSourceReviewer:
    enabled = True

    def __init__(self) -> None:
        self.calls = 0

    def review(self, *, project_name: str, repo_path: str, framework: str, issues):
        self.calls += 1
        if self.calls == 1:
            return type(
                "SourceReviewResult",
                (),
                {
                "status": "failed",
                    "error": "Gemini source review is currently rate limited (429).",
                    "recommendations": [],
                },
            )()
        return type(
            "SourceReviewResult",
            (),
            {
                "status": "completed",
                "error": None,
                "recommendations": [
                    RecommendationRecord(
                        id="",
                        title="Add stronger CTA confirmation",
                        summary="The repo still needs more explicit async feedback states.",
                        likely_fix="Update the CTA component so loading and success states are obvious.",
                        source="source_review_gpt",
                    )
                ],
            },
        )()


def test_execute_persona_runs_promotes_first_live_url_to_run_detail() -> None:
    test_root = Path("apps/api/data/test-runtime") / uuid.uuid4().hex
    test_root.mkdir(parents=True, exist_ok=True)
    store = SQLiteStore(test_root / "uxray.db")
    store.init_db()

    project = store.create_project(
        name="UXRay Demo",
        url="https://example.com",
        repo_url=None,
        owner_id=None,
        guest_session_id="guest_session",
    )
    run = store.create_run(project.id, browser_use_model="claude-sonnet-4.6")

    worker = RunWorker(
        store=store,
        adapter=_LiveUrlAdapter(),
        evaluator=_DisabledEvaluator(),
        repo_builder=_UnusedRepoBuilder(),
        tunnel_manager=_UnusedTunnelManager(),
        source_reviewer=_DisabledSourceReviewer(),
    )

    asyncio.run(
        worker._execute_persona_runs(
            run_id=run.id,
            project_name=project.name,
            project_url=project.url or "https://example.com",
            model="claude-sonnet-4.6",
            persona_specs=[("first_time_visitor", "First-time visitor")],
            custom_audience=None,
            parent_progress_callback=lambda payload: (
                store.update_run_live_url(run.id, payload["live_url"])
                if payload.get("live_url")
                else None
            ),
        )
    )

    detail = store.get_run_detail(
        run.id,
        owner_id=None,
        guest_session_id="guest_session",
    )

    assert detail is not None
    assert detail.live_url == "https://browser-use.example/live-session/first_time_visitor"


def test_source_review_rate_limit_queues_one_retry_and_then_completes() -> None:
    test_root = Path("apps/api/data/test-runtime") / uuid.uuid4().hex
    test_root.mkdir(parents=True, exist_ok=True)
    store = SQLiteStore(test_root / "uxray.db")
    store.init_db()

    project = store.create_project(
        name="UXRay Demo",
        url="https://example.com",
        repo_url="https://github.com/example/repo",
        owner_id=None,
        guest_session_id="guest_session",
    )
    run = store.create_run(
        project.id,
        browser_use_model="claude-sonnet-4.6",
        repo_build_requested=True,
        source_review_requested=True,
    )
    reviewer = _RateLimitedThenSuccessfulSourceReviewer()
    worker = RunWorker(
        store=store,
        adapter=_LiveUrlAdapter(),
        evaluator=_DisabledEvaluator(),
        repo_builder=_UnusedRepoBuilder(),
        tunnel_manager=_UnusedTunnelManager(),
        source_reviewer=reviewer,
        source_review_queue_retry_attempts=1,
        source_review_retry_delay_seconds=0.01,
        sleep_fn=lambda seconds: None,
    )

    worker._spawn_source_review_enrichment(
        run_id=run.id,
        project_name=project.name,
        preview=type(
            "RepoPreviewResult",
            (),
            {
                "preview_url": "http://127.0.0.1:4100",
                "log_path": "test.log",
                "repo_path": "apps/web",
                "framework": "next",
            },
        )(),
        analysis=type(
            "AnalysisCarrier",
            (),
            {
                "issues": [
                    AnalysisIssue(
                        issue_type="cta_feedback",
                        title="Primary signup CTA appears disabled",
                        summary="The button stayed disabled after click.",
                        severity="high",
                        route="/signup",
                        evidence=["No feedback shown"],
                        confidence=0.9,
                    )
                ]
            },
        )(),
    )

    deadline = time.time() + 1.0
    detail = None
    while time.time() < deadline:
        detail = store.get_run_detail(
            run.id,
            owner_id=None,
            guest_session_id="guest_session",
        )
        if detail and detail.source_review_status == "completed":
            break
        time.sleep(0.01)

    assert detail is not None
    assert reviewer.calls == 2
    assert detail.source_review_status == "completed"
    assert any(recommendation.source == "source_review_gpt" for recommendation in detail.recommendations)


def test_fail_run_terminalizes_pending_source_review() -> None:
    test_root = Path("apps/api/data/test-runtime") / uuid.uuid4().hex
    test_root.mkdir(parents=True, exist_ok=True)
    store = SQLiteStore(test_root / "uxray.db")
    store.init_db()

    project = store.create_project(
        name="UXRay Demo",
        url=None,
        repo_url="https://github.com/example/repo",
        owner_id=None,
        guest_session_id="guest_session",
    )
    run = store.create_run(
        project.id,
        browser_use_model="claude-sonnet-4.6",
        repo_build_requested=True,
        source_review_requested=True,
    )

    store.fail_run(run.id, "Repo preview failed before Browser Use started.")

    detail = store.get_run_detail(run.id, owner_id=None, guest_session_id="guest_session")

    assert detail is not None
    assert detail.status == "failed"
    assert detail.evaluation_status == "failed"
    assert detail.source_review_status == "skipped"
    assert detail.source_review_error == "Run failed before source review could start."
