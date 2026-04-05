from __future__ import annotations

import os
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("BROWSER_USE_API_KEY", "test-key")

from app.config import AppConfig
from app.main import create_app
from app.schemas import AdapterObservation, AdapterRunResult, RecommendationRecord
from app.services.repo_builder import RepoPreviewResult


class FakeSupabaseAuthService:
    def __init__(self) -> None:
        self.tokens: dict[str, dict[str, str | None]] = {}
        self.enabled = True

    def close(self) -> None:
        return None

    def register(self, token: str, user_id: str, email: str | None = None) -> None:
        self.tokens[token] = {"id": user_id, "email": email}

    def get_user(self, access_token: str):
        payload = self.tokens.get(access_token)
        if payload is None:
            return None
        return type(
            "AuthenticatedUser",
            (),
            {"id": payload["id"], "email": payload["email"]},
        )()


class FakeBrowserUseAdapter:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.invalid_output_personas: set[str] = set()
        self.salvaged_personas: set[str] = set()

    async def execute_run(
        self,
        run_id: str,
        project_name: str,
        project_url: str,
        model: str,
        progress_callback: Callable[[dict[str, Any]], None],
        *,
        persona_key: str,
        custom_audience: str | None = None,
    ) -> AdapterRunResult:
        self.calls.append(
            {
                "run_id": run_id,
                "project_name": project_name,
                "project_url": project_url,
                "model": model,
                "persona_key": persona_key,
                "custom_audience": custom_audience,
            }
        )

        if persona_key in self.invalid_output_personas:
            raise RuntimeError(
                "Browser Use returned invalid structured output after 3 attempts and no salvageable evidence was available."
            )

        result_mode = "salvaged" if persona_key in self.salvaged_personas else "structured"

        progress_callback(
            {
                "summary": f"{persona_key.replace('_', ' ')}: submitting Browser Use cloud run request",
                "type": "assistant",
                "screenshot_url": None,
            }
        )
        progress_callback(
            {
                "summary": "Opening project homepage",
                "type": "assistant",
                "screenshot_url": None,
            }
        )
        time.sleep(0.05)
        progress_callback(
            {
                "summary": "Inspecting signup and primary CTA",
                "type": "tool",
                "screenshot_url": "https://example.com/live-step.png",
            }
        )

        return AdapterRunResult(
            result_mode=result_mode,
            live_url=f"https://browser-use.example/live-session/{persona_key}",
            final_url=f"{project_url.rstrip('/')}/{persona_key}",
            summary=(
                f"{persona_key} recovered fallback persona evidence from streamed Browser Use progress."
                if result_mode == "salvaged"
                else f"{persona_key} found meaningful UX friction along the journey."
            ),
            observations=[
                AdapterObservation(
                    route="/signup",
                    title="Primary signup CTA appears disabled",
                    description=f"{persona_key} saw weak CTA feedback after click.",
                    severity="high",
                    evidence=[
                        "Button visually stayed in disabled state after click",
                        "No inline loading or success feedback was shown",
                    ],
                    screenshot_url="https://example.com/signup-cta.png",
                    personas=[persona_key],
                ),
                AdapterObservation(
                    route="/pricing",
                    title="Pricing navigation is easy to miss",
                    description=f"{persona_key} saw low contrast on the path to pricing.",
                    severity="medium",
                    evidence=[
                        "Low contrast header link",
                        "Secondary action visually competes with pricing entry point",
                    ],
                    screenshot_url=None,
                    personas=[persona_key],
                ),
            ],
            artifacts=[
                {
                    "kind": "live_url",
                    "label": f"{persona_key} live session",
                    "path_or_url": f"https://browser-use.example/live-session/{persona_key}",
                }
            ],
            messages=[
                {"summary": "Opening project homepage", "type": "assistant"},
                {"summary": "Inspecting signup and primary CTA", "type": "tool"},
            ],
        )


class FakeRepoBuilder:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []
        self.fail_repos: set[str] = set()

    def ensure_preview(self, *, project_id: str, repo_url: str, progress=None) -> RepoPreviewResult:
        self.calls.append({"project_id": project_id, "repo_url": repo_url})
        if progress:
            progress("Cloning public repository locally.")
            progress("Starting local next preview.")
        if repo_url in self.fail_repos:
            raise RuntimeError("Local repo preview failed.")
        return RepoPreviewResult(
            preview_url="http://127.0.0.1:4100",
            log_path="test-runtime/repo-preview.log",
            repo_path="apps/api/data/test-runtime/repo",
            framework="vite",
        )

    def close(self) -> None:
        return None


class FakeTunnelManager:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail_urls: set[str] = set()

    def expose(self, local_url: str) -> str:
        self.calls.append(local_url)
        if local_url in self.fail_urls:
            raise RuntimeError("Repo preview tunnel failed.")
        return "https://preview.example.trycloudflare.com"

    def close(self) -> None:
        return None


class FakeSourceReviewer:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    @property
    def enabled(self) -> bool:
        return True

    def review(self, *, project_name: str, repo_path: str, framework: str, issues):
        self.calls.append(
            {
                "project_name": project_name,
                "repo_path": repo_path,
                "framework": framework,
                "issue_count": len(issues),
            }
        )
        return type(
            "SourceReviewResult",
            (),
            {
                "status": "completed",
                "error": None,
                "recommendations": [
                    RecommendationRecord(
                        id="",
                        title="Tighten CTA state handling in the repo UI",
                        summary="The source confirms that CTA feedback is under-modeled in the interactive flow.",
                        likely_fix="Update the signup action component to render explicit pending, success, and error states.",
                        source="source_review_gpt",
                    )
                ],
            },
        )()


@pytest.fixture
def fake_adapter() -> FakeBrowserUseAdapter:
    return FakeBrowserUseAdapter()


@pytest.fixture
def fake_auth_service() -> FakeSupabaseAuthService:
    service = FakeSupabaseAuthService()
    service.register("token-user-a", "user_a", "user-a@example.com")
    service.register("token-user-b", "user_b", "user-b@example.com")
    return service


@pytest.fixture
def fake_repo_builder() -> FakeRepoBuilder:
    return FakeRepoBuilder()


@pytest.fixture
def fake_source_reviewer() -> FakeSourceReviewer:
    return FakeSourceReviewer()


@pytest.fixture
def fake_tunnel_manager() -> FakeTunnelManager:
    return FakeTunnelManager()


@pytest.fixture
def client(
    fake_adapter: FakeBrowserUseAdapter,
    fake_auth_service: FakeSupabaseAuthService,
    fake_repo_builder: FakeRepoBuilder,
    fake_tunnel_manager: FakeTunnelManager,
    fake_source_reviewer: FakeSourceReviewer,
) -> TestClient:
    test_root = Path("apps/api/data/test-runtime") / uuid.uuid4().hex
    test_root.mkdir(parents=True, exist_ok=True)
    db_path = test_root / "uxray-test.db"
    artifacts_dir = test_root / "artifacts"
    config = AppConfig(
        db_path=db_path,
        artifacts_dir=artifacts_dir,
        browser_use_api_key="test-key",
        queue_poll_seconds=0.02,
        start_worker=True,
        supabase_url="https://example.supabase.co",
        supabase_publishable_key="sb_publishable_test",
        local_repo_build_root=test_root / "repo-builds",
        source_review_enabled=True,
        source_review_api_key="test-gemini-key",
        source_review_model="gemini-3.1-flash-lite-preview",
    )
    app = create_app(
        config=config,
        adapter=fake_adapter,
        auth_service=fake_auth_service,
        repo_builder=fake_repo_builder,
        tunnel_manager=fake_tunnel_manager,
        source_reviewer=fake_source_reviewer,
    )
    with TestClient(app) as test_client:
        yield test_client
