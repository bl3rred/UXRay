import asyncio
from pathlib import Path
import uuid

from app.db import SQLiteStore
from app.schemas import AdapterRunResult
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
