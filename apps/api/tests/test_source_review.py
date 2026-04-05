from __future__ import annotations

import json
from pathlib import Path
import uuid

import httpx

from app.schemas import IssueRecord
from app.services.source_review import GeminiSourceReviewService


def test_source_review_skips_when_not_configured() -> None:
    tmp_path = Path("apps/api/data/test-runtime") / uuid.uuid4().hex
    tmp_path.mkdir(parents=True, exist_ok=True)
    service = GeminiSourceReviewService(
        enabled=False,
        api_key=None,
        model="gemini-3.1-flash-lite-preview",
    )

    result = service.review(
        project_name="UXRay Demo",
        repo_path=str(tmp_path),
        framework="vite",
        issues=[],
    )

    assert result.status == "skipped"
    assert result.recommendations == []


def test_source_review_maps_gemini_response() -> None:
    tmp_path = Path("apps/api/data/test-runtime") / uuid.uuid4().hex
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "demo", "scripts": {"dev": "vite"}}),
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.tsx").write_text(
        "export function App() { return <button>Start</button>; }",
        encoding="utf-8",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert request.headers["x-goog-api-key"] == "test-gemini-key"
        assert "gemini-3.1-flash-lite-preview:generateContent" in str(request.url)
        assert payload["generationConfig"]["responseMimeType"] == "application/json"
        assert payload["generationConfig"]["responseSchema"]["type"] == "OBJECT"
        body = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "recommendations": [
                                            {
                                                "title": "Add visible CTA pending state",
                                                "summary": "The main conversion path still lacks obvious request feedback.",
                                                "likely_fix": "Update src/app.tsx so the CTA shows pending and success states.",
                                            }
                                        ]
                                    }
                                )
                            }
                        ]
                    }
                }
            ]
        }
        return httpx.Response(200, json=body)

    service = GeminiSourceReviewService(
        enabled=True,
        api_key="test-gemini-key",
        model="gemini-3.1-flash-lite-preview",
        transport=httpx.MockTransport(handler),
    )

    result = service.review(
        project_name="UXRay Demo",
        repo_path=str(tmp_path),
        framework="vite",
        issues=[
            IssueRecord(
                id="issue_1",
                issue_type="cta_feedback",
                title="Primary CTA did not respond",
                summary="There is no visible request feedback.",
                severity="high",
                route="/signup",
                evidence=["No loading state"],
                confidence=0.9,
                personas=["first_time_visitor"],
                screenshot_url=None,
            )
        ],
    )

    assert result.status == "completed"
    assert result.recommendations[0].source == "source_review_gpt"
    assert "src/app.tsx" in result.recommendations[0].likely_fix


def test_source_review_reports_rate_limit_clearly() -> None:
    tmp_path = Path("apps/api/data/test-runtime") / uuid.uuid4().hex
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "demo", "scripts": {"dev": "vite"}}),
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.tsx").write_text(
        "export function App() { return <button>Start</button>; }",
        encoding="utf-8",
    )

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    service = GeminiSourceReviewService(
        enabled=True,
        api_key="test-gemini-key",
        model="gemini-3.1-flash-lite-preview",
        transport=httpx.MockTransport(handler),
    )

    result = service.review(
        project_name="UXRay Demo",
        repo_path=str(tmp_path),
        framework="vite",
        issues=[
            IssueRecord(
                id="issue_1",
                issue_type="cta_feedback",
                title="Primary CTA did not respond",
                summary="There is no visible request feedback.",
                severity="high",
                route="/signup",
                evidence=["No loading state"],
                confidence=0.9,
                personas=["first_time_visitor"],
                screenshot_url=None,
            )
        ],
    )

    assert result.status == "failed"
    assert result.error == "Gemini source review is currently rate limited (429)."


def test_source_review_retries_rate_limit_before_succeeding() -> None:
    tmp_path = Path("apps/api/data/test-runtime") / uuid.uuid4().hex
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "demo", "scripts": {"dev": "vite"}}),
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.tsx").write_text(
        "export function App() { return <button>Start</button>; }",
        encoding="utf-8",
    )

    calls = {"count": 0}
    sleeps: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] < 3:
            return httpx.Response(429, json={"error": {"message": "rate limited"}})
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "recommendations": [
                                                {
                                                    "title": "Clarify CTA feedback",
                                                    "summary": "The main action still needs visible pending and success states.",
                                                    "likely_fix": "Update src/app.tsx so the CTA shows loading and success feedback.",
                                                }
                                            ]
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ]
            },
        )

    service = GeminiSourceReviewService(
        enabled=True,
        api_key="test-gemini-key",
        model="gemini-3.1-flash-lite-preview",
        retry_attempts=2,
        retry_backoff_seconds=0.01,
        sleep=sleeps.append,
        transport=httpx.MockTransport(handler),
    )

    result = service.review(
        project_name="UXRay Demo",
        repo_path=str(tmp_path),
        framework="vite",
        issues=[],
    )

    assert result.status == "completed"
    assert calls["count"] == 3
    assert len(sleeps) == 2


def test_source_review_repo_context_stays_tightly_scoped() -> None:
    tmp_path = Path("apps/api/data/test-runtime") / uuid.uuid4().hex
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "demo", "scripts": {"dev": "vite"}}),
        encoding="utf-8",
    )
    for relative_path in (
        "src/app/layout.tsx",
        "src/app/page.tsx",
        "src/components/hero.tsx",
        "src/components/pricing.tsx",
        "src/components/faq.tsx",
        "src/components/footer.tsx",
        "src/components/extra.tsx",
        "src/styles/global.css",
    ):
        target = tmp_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(("x" * 2600), encoding="utf-8")

    service = GeminiSourceReviewService(
        enabled=True,
        api_key="test-gemini-key",
        model="gemini-3.1-flash-lite-preview",
    )

    context = service._build_repo_context(tmp_path)

    assert "package.json" in context
    assert "src/app/layout.tsx" in context
    assert "src/components/extra.tsx" not in context
    assert len(context) < 15000
