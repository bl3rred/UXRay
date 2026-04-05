from pathlib import Path
import uuid

from app.db import SQLiteStore
from app.schemas import AnalysisIssue, AnalysisResult


def test_run_detail_falls_back_to_first_screenshot_artifact() -> None:
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

    store.complete_run(
        run.id,
        live_url=None,
        final_url="https://example.com/final",
        target_url="https://example.com",
        target_source="site",
        summary="Completed run.",
        analysis=AnalysisResult(
            issues=[
                AnalysisIssue(
                    issue_type="cta_feedback",
                    title="Primary signup CTA appears disabled",
                    summary="The CTA did not confirm progress after click.",
                    severity="high",
                    route="/signup",
                    evidence=["No visible feedback after click"],
                    confidence=0.92,
                    personas=["first_time_visitor"],
                    screenshot_url=None,
                )
            ],
            recommendations=[],
            artifacts=[
                {
                    "kind": "screenshot",
                    "label": "Session capture",
                    "path_or_url": "https://example.com/persisted-artifact.png",
                }
            ],
        ),
        evaluation_status="skipped",
        evaluation_error=None,
        source_review_status="skipped",
        source_review_error=None,
    )

    detail = store.get_run_detail(
        run.id,
        owner_id=None,
        guest_session_id="guest_session",
    )

    assert detail is not None
    assert detail.issues[0].screenshot_url == "https://example.com/persisted-artifact.png"
