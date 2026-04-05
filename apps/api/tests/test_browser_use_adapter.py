from __future__ import annotations

import asyncio
import tempfile
import uuid
from pathlib import Path
from types import ModuleType, SimpleNamespace

import httpx
import pytest

from app.adapters.browser_use import BrowserUseAdapter


def test_browser_use_adapter_streams_messages_and_persists_assets(
    monkeypatch,
) -> None:
    tmp_path = Path(tempfile.mkdtemp())
    progress_events: list[dict[str, str | None]] = []

    class FakeRun:
        def __init__(self) -> None:
            self.session_id = None
            self.result = None
            self._timeout = None
            self._interval = None
            self._sessions = SimpleNamespace(get=self._get_session)

        async def _get_session(self, session_id: str):
            assert session_id == "session_123"
            return SimpleNamespace(live_url="https://browser-use.example/live")

        def __aiter__(self):
            async def iterator():
                self.session_id = "session_123"
                yield SimpleNamespace(
                    summary="Opened homepage and started navigating to pricing",
                    type="tool",
                    screenshot_url="https://example.com/home.png",
                    hidden=False,
                )
                yield SimpleNamespace(
                    summary="Reviewed cart flow for trust friction",
                    type="assistant",
                    screenshot_url=None,
                    hidden=False,
                )
                yield SimpleNamespace(
                    summary="",
                    type="tool",
                    screenshot_url="https://example.com/ignored.png",
                    hidden=False,
                )
                self.result = SimpleNamespace(
                    live_url="https://browser-use.example/live",
                    screenshot_url="https://example.com/final.png",
                    recording_urls=["https://example.com/recording.mp4"],
                    output=SimpleNamespace(
                        final_url="https://example.com/cart",
                        summary="Multi-page audit complete.",
                        observations=[
                            SimpleNamespace(
                                route="/cart",
                                title="Trust copy is easy to miss",
                                description="Users can miss reassurance content during checkout.",
                                severity="medium",
                                evidence=["Trust copy appears below the fold"],
                                screenshot_url="https://example.com/cart.png",
                            )
                        ],
                    ),
                )

            return iterator()

    class FakeAsyncBrowserUse:
        def __init__(self) -> None:
            self.run_calls: list[dict[str, object]] = []

        def run(self, **_: object):
            self.run_calls.append(_)
            return FakeRun()

    async def fake_persist(
        self: BrowserUseAdapter,
        source_url: str | None,
        run_id: str,
        persona_key: str,
        prefix: str,
        index: int,
    ) -> str | None:
        if not source_url:
            return None
        return f"browser-use/{run_id}/{persona_key}/{prefix}-{index:03d}.png"

    browser_use_sdk_module = ModuleType("browser_use_sdk")
    browser_use_sdk_v3_module = ModuleType("browser_use_sdk.v3")
    fake_client = FakeAsyncBrowserUse()
    browser_use_sdk_v3_module.AsyncBrowserUse = lambda: fake_client
    monkeypatch.setitem(__import__("sys").modules, "browser_use_sdk", browser_use_sdk_module)
    monkeypatch.setitem(__import__("sys").modules, "browser_use_sdk.v3", browser_use_sdk_v3_module)
    monkeypatch.setattr(BrowserUseAdapter, "_persist_remote_asset", fake_persist)

    adapter = BrowserUseAdapter(
        api_key="browser-use-key",
        model="claude-sonnet-4.6",
        artifacts_dir=tmp_path,
        run_timeout_seconds=240,
    )
    result = asyncio.run(
        adapter.execute_run(
            run_id="run_123",
            project_name="UXRay Demo",
            project_url="https://example.com",
            model="claude-sonnet-4.6",
            progress_callback=progress_events.append,
            persona_key="trust_evaluator",
        )
    )

    assert result.live_url == "https://browser-use.example/live"
    assert result.final_url == "https://example.com/cart"
    assert result.result_mode == "structured"
    assert result.observations[0].screenshot_url == "browser-use/run_123/trust_evaluator/observation-001.png"
    assert result.observations[0].personas == ["trust_evaluator"]
    assert result.artifacts == [
        {
            "kind": "live_url",
            "label": "Trust evaluator live session",
            "path_or_url": "https://browser-use.example/live",
        },
        {
            "kind": "screenshot",
            "label": "Trust evaluator final session screenshot",
            "path_or_url": "browser-use/run_123/trust_evaluator/session-001.png",
        },
        {
            "kind": "screenshot",
            "label": "Trust evaluator progress evidence 1: Opened homepage and started navigating to pricing",
            "path_or_url": "browser-use/run_123/trust_evaluator/progress-001.png",
        },
        {
            "kind": "recording",
            "label": "Trust evaluator recording 1",
            "path_or_url": "https://example.com/recording.mp4",
        },
    ]
    assert result.messages == [
        {
            "summary": "Opened homepage and started navigating to pricing",
            "type": "tool",
            "screenshot_url": "browser-use/run_123/trust_evaluator/progress-001.png",
            "live_url": None,
        },
        {
            "summary": "Reviewed cart flow for trust friction",
            "type": "assistant",
            "screenshot_url": None,
            "live_url": None,
        },
    ]
    assert progress_events == [
        {
            "summary": "Trust evaluator mission: Audit like a skeptical evaluator focused on credibility, reassurance, policy visibility, and conversion hesitation.",
            "type": "system",
            "screenshot_url": None,
            "live_url": None,
        },
        {
            "summary": "Trust evaluator: submitting Browser Use cloud run request",
            "type": "system",
            "screenshot_url": None,
            "live_url": None,
        },
        {
            "summary": "Trust evaluator: Browser Use run is capped at 240 seconds.",
            "type": "system",
            "screenshot_url": None,
            "live_url": None,
        },
        {
            "summary": "Trust evaluator: Browser Use live session is available.",
            "type": "system",
            "screenshot_url": None,
            "live_url": "https://browser-use.example/live",
        },
        {
            "summary": "Opened homepage and started navigating to pricing",
            "type": "tool",
            "screenshot_url": "browser-use/run_123/trust_evaluator/progress-001.png",
            "live_url": None,
        },
        {
            "summary": "Reviewed cart flow for trust friction",
            "type": "assistant",
            "screenshot_url": None,
            "live_url": None,
        },
    ]
    assert fake_client.run_calls[0]["keep_alive"] is False
    assert str(fake_client.run_calls[0]["task"]).startswith("Persona: Trust evaluator.")


def test_browser_use_adapter_tolerates_expired_screenshots(monkeypatch) -> None:
    tmp_path = Path(tempfile.mkdtemp())
    progress_events: list[dict[str, str | None]] = []

    class FakeRun:
        def __init__(self) -> None:
            self.session_id = None
            self.result = None
            self._timeout = None
            self._interval = None
            self._sessions = SimpleNamespace(get=self._get_session)

        async def _get_session(self, session_id: str):
            assert session_id == "session_404"
            return SimpleNamespace(live_url="https://browser-use.example/live-404")

        def __aiter__(self):
            async def iterator():
                self.session_id = "session_404"
                yield SimpleNamespace(
                    summary="Opened homepage",
                    type="tool",
                    screenshot_url="https://example.com/missing-progress.png",
                    hidden=False,
                )
                self.result = SimpleNamespace(
                    live_url="https://browser-use.example/live-404",
                    screenshot_url="https://example.com/missing-final.png",
                    recording_urls=[],
                    output=SimpleNamespace(
                        final_url="https://example.com/signup",
                        summary="Audit complete despite missing screenshots.",
                        observations=[
                            SimpleNamespace(
                                route="/signup",
                                title="CTA hesitation",
                                description="Screenshot URL expired before persistence.",
                                severity="medium",
                                evidence=["CTA feedback is weak"],
                                screenshot_url="https://example.com/missing-observation.png",
                            )
                        ],
                    ),
                )

            return iterator()

    class FakeAsyncBrowserUse:
        def run(self, **_: object):
            return FakeRun()

    async def failing_persist(
        self: BrowserUseAdapter,
        source_url: str | None,
        run_id: str,
        persona_key: str,
        prefix: str,
        index: int,
    ) -> str | None:
        if not source_url:
            return None
        request = httpx.Request("GET", source_url)
        response = httpx.Response(404, request=request)
        raise httpx.HTTPStatusError("Not found", request=request, response=response)

    browser_use_sdk_module = ModuleType("browser_use_sdk")
    browser_use_sdk_v3_module = ModuleType("browser_use_sdk.v3")
    browser_use_sdk_v3_module.AsyncBrowserUse = FakeAsyncBrowserUse
    monkeypatch.setitem(__import__("sys").modules, "browser_use_sdk", browser_use_sdk_module)
    monkeypatch.setitem(__import__("sys").modules, "browser_use_sdk.v3", browser_use_sdk_v3_module)
    monkeypatch.setattr(BrowserUseAdapter, "_persist_remote_asset", failing_persist)

    adapter = BrowserUseAdapter(
        api_key="browser-use-key",
        model="claude-sonnet-4.6",
        artifacts_dir=tmp_path,
        run_timeout_seconds=240,
    )
    result = asyncio.run(
        adapter.execute_run(
            run_id="run_404",
            project_name="UXRay Demo",
            project_url="https://example.com",
            model="claude-sonnet-4.6",
            progress_callback=progress_events.append,
            persona_key="first_time_visitor",
        )
    )

    assert result.summary == "Audit complete despite missing screenshots."
    assert result.result_mode == "structured"
    assert result.observations[0].screenshot_url is None
    assert all(artifact["kind"] != "screenshot" for artifact in result.artifacts)
    assert any(
        event["summary"] == "First-time visitor: Screenshot capture expired or was unavailable (404) while saving progress evidence."
        for event in progress_events
    )
    assert any(
        event["summary"] == "First-time visitor: Screenshot capture expired or was unavailable (404) while saving observation evidence."
        for event in progress_events
    )


def test_browser_use_adapter_uses_strict_json_fallback_on_third_attempt(monkeypatch) -> None:
    tmp_path = Path(tempfile.mkdtemp())
    progress_events: list[dict[str, str | None]] = []

    class FakeRun:
        def __init__(self, output: object) -> None:
            self.session_id = None
            self.result = None
            self._timeout = None
            self._interval = None
            self._sessions = SimpleNamespace(get=self._get_session)
            self._output = output

        async def _get_session(self, session_id: str):
            assert session_id in {"session_1", "session_2"}
            return SimpleNamespace(live_url="https://browser-use.example/live")

        def __aiter__(self):
            async def iterator():
                self.session_id = "session_1"
                self.result = SimpleNamespace(
                    live_url="https://browser-use.example/live",
                    screenshot_url=None,
                    recording_urls=[],
                    output=self._output,
                )
                if self._output != "Task ended unexpectedly.":
                    self.result.output = SimpleNamespace(
                        final_url="https://example.com/signup",
                        summary="Recovered structured output.",
                        observations=[
                            SimpleNamespace(
                                route="/signup",
                                title="CTA hesitation",
                                description="Recovered after retry.",
                                severity="medium",
                                evidence=["Retry succeeded"],
                                screenshot_url=None,
                            )
                        ],
                    )
                yield SimpleNamespace(
                    summary="Opened homepage",
                    type="tool",
                    screenshot_url=None,
                    hidden=False,
                )

            return iterator()

    class FakeAsyncBrowserUse:
        def __init__(self) -> None:
            self.calls = 0
            self.run_calls: list[dict[str, object]] = []

        def run(self, **_: object):
            self.calls += 1
            self.run_calls.append(_)
            if self.calls < 3:
                return FakeRun("Task ended unexpectedly.")
            return FakeRun({"summary": "Recovered structured output.", "final_url": "https://example.com/signup", "observations": [{"route": "/signup", "title": "CTA hesitation", "description": "Recovered after retry.", "severity": "medium", "evidence": ["Retry succeeded"], "screenshot_url": None}]})

    browser_use_sdk_module = ModuleType("browser_use_sdk")
    browser_use_sdk_v3_module = ModuleType("browser_use_sdk.v3")
    fake_client = FakeAsyncBrowserUse()
    browser_use_sdk_v3_module.AsyncBrowserUse = lambda: fake_client
    monkeypatch.setitem(__import__("sys").modules, "browser_use_sdk", browser_use_sdk_module)
    monkeypatch.setitem(__import__("sys").modules, "browser_use_sdk.v3", browser_use_sdk_v3_module)

    adapter = BrowserUseAdapter(
        api_key="browser-use-key",
        model="claude-sonnet-4.6",
        artifacts_dir=tmp_path,
        run_timeout_seconds=240,
    )
    result = asyncio.run(
        adapter.execute_run(
            run_id="run_retry",
            project_name="UXRay Demo",
            project_url="https://example.com",
            model="claude-sonnet-4.6",
            progress_callback=progress_events.append,
            persona_key="intent_driven",
        )
    )

    assert result.summary == "Recovered structured output."
    assert result.result_mode == "structured"
    assert any(
        event["summary"] == "Intent-driven retrying after invalid Browser Use output."
        for event in progress_events
    )
    assert any(
        event["summary"] == "Intent-driven: retry attempt 2 started."
        for event in progress_events
    )
    assert any(
        event["summary"] == "Intent-driven retrying with strict JSON-only fallback after invalid Browser Use output."
        for event in progress_events
    )
    assert any(
        event["summary"] == "Intent-driven: retry attempt 3 started with strict JSON-only fallback."
        for event in progress_events
    )
    assert "CRITICAL: Return valid JSON only." in str(fake_client.run_calls[2]["task"])


def test_browser_use_adapter_salvages_messages_after_exhausting_invalid_output_retries(monkeypatch) -> None:
    tmp_path = Path(tempfile.mkdtemp())
    progress_events: list[dict[str, str | None]] = []

    class FakeRun:
        def __init__(self) -> None:
            self.session_id = None
            self.result = None
            self._timeout = None
            self._interval = None
            self._sessions = SimpleNamespace(get=self._get_session)

        async def _get_session(self, session_id: str):
            return SimpleNamespace(live_url="https://browser-use.example/live")

        def __aiter__(self):
            async def iterator():
                self.session_id = "session_bad"
                self.result = SimpleNamespace(
                    live_url="https://browser-use.example/live",
                    screenshot_url=None,
                    recording_urls=[],
                    output="Task ended unexpectedly.",
                )
                yield SimpleNamespace(
                    summary="Opened pricing page but the signup path stayed blocked behind a looping modal",
                    type="tool",
                    screenshot_url="https://example.com/progress.png",
                    hidden=False,
                )

            return iterator()

    class FakeAsyncBrowserUse:
        def run(self, **_: object):
            return FakeRun()

    async def fake_persist(
        self: BrowserUseAdapter,
        source_url: str | None,
        run_id: str,
        persona_key: str,
        prefix: str,
        index: int,
    ) -> str | None:
        return source_url

    browser_use_sdk_module = ModuleType("browser_use_sdk")
    browser_use_sdk_v3_module = ModuleType("browser_use_sdk.v3")
    fake_client = FakeAsyncBrowserUse()
    browser_use_sdk_v3_module.AsyncBrowserUse = lambda: fake_client
    monkeypatch.setitem(__import__("sys").modules, "browser_use_sdk", browser_use_sdk_module)
    monkeypatch.setitem(__import__("sys").modules, "browser_use_sdk.v3", browser_use_sdk_v3_module)
    monkeypatch.setattr(BrowserUseAdapter, "_persist_remote_asset", fake_persist)

    adapter = BrowserUseAdapter(
        api_key="browser-use-key",
        model="claude-sonnet-4.6",
        artifacts_dir=tmp_path,
        run_timeout_seconds=240,
    )

    result = asyncio.run(
        adapter.execute_run(
            run_id="run_bad",
            project_name="UXRay Demo",
            project_url="https://example.com",
            model="claude-sonnet-4.6",
            progress_callback=progress_events.append,
            persona_key="first_time_visitor",
        )
    )

    assert result.result_mode == "salvaged"
    assert "recovered fallback persona evidence" in result.summary.lower()
    assert len(result.observations) == 1
    assert result.observations[0].route == "/"
    assert result.observations[0].screenshot_url == "https://example.com/progress.png"
    assert any(
        event["summary"]
        == "First-time visitor: salvaging persona evidence from streamed Browser Use progress after invalid structured output."
        for event in progress_events
    )


def test_browser_use_adapter_fails_cleanly_when_no_salvageable_evidence_exists(monkeypatch) -> None:
    tmp_path = Path(tempfile.mkdtemp())
    progress_events: list[dict[str, str | None]] = []

    class FakeRun:
        def __init__(self) -> None:
            self.session_id = None
            self.result = None
            self._timeout = None
            self._interval = None
            self._sessions = SimpleNamespace(get=self._get_session)

        async def _get_session(self, session_id: str):
            return SimpleNamespace(live_url="https://browser-use.example/live")

        def __aiter__(self):
            async def iterator():
                self.session_id = "session_bad"
                self.result = SimpleNamespace(
                    live_url="https://browser-use.example/live",
                    screenshot_url=None,
                    recording_urls=[],
                    output="Task ended unexpectedly.",
                )
                if False:
                    yield SimpleNamespace(summary="ignored", type="tool", screenshot_url=None, hidden=False)

            return iterator()

    class FakeAsyncBrowserUse:
        def run(self, **_: object):
            return FakeRun()

    browser_use_sdk_module = ModuleType("browser_use_sdk")
    browser_use_sdk_v3_module = ModuleType("browser_use_sdk.v3")
    fake_client = FakeAsyncBrowserUse()
    browser_use_sdk_v3_module.AsyncBrowserUse = lambda: fake_client
    monkeypatch.setitem(__import__("sys").modules, "browser_use_sdk", browser_use_sdk_module)
    monkeypatch.setitem(__import__("sys").modules, "browser_use_sdk.v3", browser_use_sdk_v3_module)

    adapter = BrowserUseAdapter(
        api_key="browser-use-key",
        model="claude-sonnet-4.6",
        artifacts_dir=tmp_path,
        run_timeout_seconds=240,
    )

    with pytest.raises(
        RuntimeError,
        match="Browser Use returned invalid structured output after 3 attempts and no salvageable evidence was available.",
    ):
        asyncio.run(
            adapter.execute_run(
                run_id="run_bad",
                project_name="UXRay Demo",
                project_url="https://example.com",
                model="claude-sonnet-4.6",
                progress_callback=progress_events.append,
                persona_key="first_time_visitor",
            )
        )

    assert any(
        event["summary"] == "First-time visitor retrying after invalid Browser Use output."
        for event in progress_events
    )
    assert any(
        event["summary"] == "First-time visitor retrying with strict JSON-only fallback after invalid Browser Use output."
        for event in progress_events
    )


def test_browser_use_adapter_filters_login_wall_observations(monkeypatch) -> None:
    tmp_path = Path(tempfile.mkdtemp())
    progress_events: list[dict[str, str | None]] = []

    class FakeRun:
        def __init__(self) -> None:
            self.session_id = None
            self.result = None
            self._timeout = None
            self._interval = None
            self._sessions = SimpleNamespace(get=self._get_session)

        async def _get_session(self, session_id: str):
            return SimpleNamespace(live_url="https://browser-use.example/live")

        def __aiter__(self):
            async def iterator():
                self.session_id = "session_auth"
                self.result = SimpleNamespace(
                    live_url="https://browser-use.example/live",
                    screenshot_url=None,
                    recording_urls=[],
                    output=SimpleNamespace(
                        final_url="https://example.com/pricing",
                        summary="Audit completed with one real issue and one auth wall.",
                        observations=[
                            SimpleNamespace(
                                route="/login",
                                title="Login required to continue",
                                description="The tool could not continue because credentials were required.",
                                severity="medium",
                                evidence=["Must sign in to continue", "Guest mode blocked the flow"],
                                screenshot_url=None,
                            ),
                            SimpleNamespace(
                                route="/pricing",
                                title="Pricing path is hard to spot",
                                description="The route to pricing is visually weaker than the main hero action.",
                                severity="medium",
                                evidence=["Pricing link is low contrast", "Footer path is easier to find than header path"],
                                screenshot_url=None,
                            ),
                        ],
                    ),
                )
                yield SimpleNamespace(
                    summary="Visited pricing after leaving the login wall",
                    type="tool",
                    screenshot_url=None,
                    hidden=False,
                )

            return iterator()

    class FakeAsyncBrowserUse:
        def run(self, **_: object):
            return FakeRun()

    browser_use_sdk_module = ModuleType("browser_use_sdk")
    browser_use_sdk_v3_module = ModuleType("browser_use_sdk.v3")
    browser_use_sdk_v3_module.AsyncBrowserUse = FakeAsyncBrowserUse
    monkeypatch.setitem(__import__("sys").modules, "browser_use_sdk", browser_use_sdk_module)
    monkeypatch.setitem(__import__("sys").modules, "browser_use_sdk.v3", browser_use_sdk_v3_module)

    adapter = BrowserUseAdapter(
        api_key="browser-use-key",
        model="claude-sonnet-4.6",
        artifacts_dir=tmp_path,
        run_timeout_seconds=240,
    )

    result = asyncio.run(
        adapter.execute_run(
            run_id="run_auth",
            project_name="UXRay Demo",
            project_url="https://example.com",
            model="claude-sonnet-4.6",
            progress_callback=progress_events.append,
            persona_key="first_time_visitor",
        )
    )

    assert result.result_mode == "structured"
    assert len(result.observations) == 1
    assert result.observations[0].title == "Pricing path is hard to spot"


def test_browser_use_adapter_uploads_assets_to_supabase_when_configured(monkeypatch) -> None:
    tmp_path = Path(tempfile.mkdtemp())

    async def fake_download(
        self: BrowserUseAdapter,
        source_url: str,
    ) -> tuple[bytes, str | None]:
        assert source_url == "https://example.com/final.png"
        return b"image-bytes", "image/png"

    async def fake_upload(
        self: BrowserUseAdapter,
        *,
        object_path: str,
        content: bytes,
        content_type: str | None,
    ) -> str:
        assert object_path == "browser-use/run_storage/trust_evaluator/session-001.png"
        assert content == b"image-bytes"
        assert content_type == "image/png"
        return "https://project.supabase.co/storage/v1/object/public/uxray-artifacts/browser-use/run_storage/trust_evaluator/session-001.png"

    monkeypatch.setattr(BrowserUseAdapter, "_download_remote_asset", fake_download)
    monkeypatch.setattr(BrowserUseAdapter, "_upload_asset_to_supabase", fake_upload)

    adapter = BrowserUseAdapter(
        api_key="browser-use-key",
        model="claude-sonnet-4.6",
        artifacts_dir=tmp_path,
        supabase_url="https://project.supabase.co",
        supabase_service_role_key="service-role",
        supabase_storage_bucket="uxray-artifacts",
    )

    persisted = asyncio.run(
        adapter._persist_remote_asset(
            "https://example.com/final.png",
            "run_storage",
            "trust_evaluator",
            "session",
            1,
        )
    )

    assert (
        persisted
        == "https://project.supabase.co/storage/v1/object/public/uxray-artifacts/browser-use/run_storage/trust_evaluator/session-001.png"
    )


def test_browser_use_adapter_falls_back_to_local_file_when_supabase_upload_fails(monkeypatch) -> None:
    tmp_path = Path("apps/api/data/test-runtime") / uuid.uuid4().hex
    tmp_path.mkdir(parents=True, exist_ok=True)

    async def fake_download(
        self: BrowserUseAdapter,
        source_url: str,
    ) -> tuple[bytes, str | None]:
        assert source_url == "https://example.com/final.png"
        return b"image-bytes", "image/png"

    async def failing_upload(
        self: BrowserUseAdapter,
        *,
        object_path: str,
        content: bytes,
        content_type: str | None,
    ) -> str:
        raise httpx.ConnectError("storage unavailable")

    monkeypatch.setattr(BrowserUseAdapter, "_download_remote_asset", fake_download)
    monkeypatch.setattr(BrowserUseAdapter, "_upload_asset_to_supabase", failing_upload)

    adapter = BrowserUseAdapter(
        api_key="browser-use-key",
        model="claude-sonnet-4.6",
        artifacts_dir=tmp_path,
        supabase_url="https://project.supabase.co",
        supabase_service_role_key="service-role",
        supabase_storage_bucket="uxray-artifacts",
    )

    persisted = asyncio.run(
        adapter._persist_remote_asset(
            "https://example.com/final.png",
            "run_storage",
            "trust_evaluator",
            "session",
            1,
        )
    )

    assert persisted == "browser-use/run_storage/trust_evaluator/session-001.png"
    assert (
        tmp_path / "browser-use" / "run_storage" / "trust_evaluator" / "session-001.png"
    ).read_bytes() == b"image-bytes"
