from __future__ import annotations

import json
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.schemas import IssueRecord, RecommendationRecord


@dataclass(slots=True)
class SourceReviewResult:
    status: str
    recommendations: list[RecommendationRecord]
    error: str | None = None


class GPTSourceReviewService:
    def __init__(
        self,
        *,
        enabled: bool,
        api_key: str | None,
        model: str,
        timeout_seconds: float = 45.0,
        retry_attempts: int = 2,
        retry_backoff_seconds: float = 1.0,
        sleep: Callable[[float], None] | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.enabled = enabled
        self.api_key = api_key or ""
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.retry_attempts = retry_attempts
        self.retry_backoff_seconds = retry_backoff_seconds
        self.sleep = sleep or time.sleep
        self.transport = transport

    def review(
        self,
        *,
        project_name: str,
        repo_path: str,
        framework: str,
        issues: list[IssueRecord],
    ) -> SourceReviewResult:
        if not self.enabled or not self.api_key:
            return SourceReviewResult(status="skipped", recommendations=[], error=None)

        context = self._build_repo_context(Path(repo_path))
        if not context:
            return SourceReviewResult(
                status="skipped",
                recommendations=[],
                error="No supported frontend source files were found for GPT review.",
            )

        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You review frontend source code for UXRay. "
                                "Return compact, implementation-ready UX/code recommendations that "
                                "strengthen clarity, conversion feedback, trust cues, and flow polish. "
                                "Avoid security, backend, or architecture advice unless it directly "
                                "affects the current UX findings."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": self._build_user_prompt(
                                project_name=project_name,
                                framework=framework,
                                issues=issues,
                                repo_context=context,
                            ),
                        }
                    ],
                },
            ],
            "max_output_tokens": 1400,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "uxray_source_review",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "recommendations": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "title": {"type": "string"},
                                        "summary": {"type": "string"},
                                        "likely_fix": {"type": "string"},
                                    },
                                    "required": ["title", "summary", "likely_fix"],
                                    "additionalProperties": False,
                                },
                                "minItems": 2,
                                "maxItems": 5,
                            }
                        },
                        "required": ["recommendations"],
                        "additionalProperties": False,
                    },
                }
            },
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = self._post_review_request(headers=headers, payload=payload)
            parsed = self._parse_response_json(response.json())
            recommendations = [
                RecommendationRecord(
                    id="",
                    title=item["title"].strip(),
                    summary=item["summary"].strip(),
                    likely_fix=item["likely_fix"].strip(),
                    source="source_review_gpt",
                )
                for item in parsed.get("recommendations", [])
                if item.get("title") and item.get("summary") and item.get("likely_fix")
            ]
            if not recommendations:
                return SourceReviewResult(
                    status="failed",
                    recommendations=[],
                    error="GPT source review returned no actionable recommendations.",
                )
            return SourceReviewResult(status="completed", recommendations=recommendations, error=None)
        except httpx.TimeoutException:
            return SourceReviewResult(
                status="failed",
                recommendations=[],
                error="GPT source review timed out before returning recommendations.",
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                return SourceReviewResult(
                    status="failed",
                    recommendations=[],
                    error="GPT source review is currently rate limited by OpenAI (429).",
                )
            return SourceReviewResult(status="failed", recommendations=[], error=str(exc))
        except Exception as exc:
            return SourceReviewResult(status="failed", recommendations=[], error=str(exc))

    def _post_review_request(
        self,
        *,
        headers: dict[str, str],
        payload: dict,
    ) -> httpx.Response:
        last_error: httpx.HTTPStatusError | None = None
        attempts = max(self.retry_attempts, 0) + 1
        for attempt in range(1, attempts + 1):
            with httpx.Client(
                transport=self.transport,
                timeout=self.timeout_seconds,
            ) as client:
                response = client.post(
                    "https://api.openai.com/v1/responses",
                    headers=headers,
                    json=payload,
                )
            try:
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 429 or attempt >= attempts:
                    raise
                last_error = exc
                backoff_seconds = self.retry_backoff_seconds * attempt + random.uniform(0.0, 0.25)
                self.sleep(backoff_seconds)
        if last_error is not None:
            raise last_error
        raise RuntimeError("GPT source review request failed before receiving a response.")

    def _build_repo_context(self, repo_path: Path) -> str:
        package_json_path = repo_path / "package.json"
        if not package_json_path.exists():
            return ""

        snippets: list[str] = [
            f"File: package.json\n{package_json_path.read_text(encoding='utf-8')[:4000].strip()}"
        ]
        seen: set[Path] = set()
        char_budget = 14000
        for pattern in self._priority_patterns():
            for path in sorted(repo_path.glob(pattern), key=self._path_priority):
                if not path.is_file() or path in seen:
                    continue
                try:
                    content = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                snippet = f"File: {path.relative_to(repo_path).as_posix()}\n{content[:2200].strip()}"
                if sum(len(item) for item in snippets) + len(snippet) > char_budget:
                    return "\n\n".join(snippets)
                snippets.append(snippet)
                seen.add(path)
                if len(seen) >= 5:
                    return "\n\n".join(snippets)
        return "\n\n".join(snippets)

    def _path_priority(self, path: Path) -> tuple[int, str]:
        normalized = path.as_posix().lower()
        important_tokens = (
            "layout",
            "page",
            "global",
            "hero",
            "cta",
            "button",
            "form",
            "pricing",
            "faq",
            "nav",
            "header",
            "footer",
        )
        for index, token in enumerate(important_tokens):
            if token in normalized:
                return (index, normalized)
        return (len(important_tokens), normalized)

    def _priority_patterns(self) -> tuple[str, ...]:
        return (
            "app/layout.tsx",
            "src/app/layout.tsx",
            "app/page.tsx",
            "src/app/page.tsx",
            "pages/index.tsx",
            "src/pages/index.tsx",
            "app/globals.css",
            "src/app/globals.css",
            "styles/**/*.css",
            "src/styles/**/*.css",
            "app/**/*.tsx",
            "src/app/**/*.tsx",
            "pages/**/*.tsx",
            "src/pages/**/*.tsx",
            "components/**/*.tsx",
            "src/components/**/*.tsx",
            "lib/**/*.ts",
            "src/lib/**/*.ts",
        )

    def _build_user_prompt(
        self,
        *,
        project_name: str,
        framework: str,
        issues: list[IssueRecord],
        repo_context: str,
    ) -> str:
        issue_summary = "\n".join(
            f"- {issue.title} [{issue.severity}] on {issue.route}: {issue.summary}"
            for issue in issues[:8]
        )
        return (
            f"Project: {project_name}\n"
            f"Framework: {framework}\n"
            "Live UX findings from the run:\n"
            f"{issue_summary or '- No issue summary provided.'}\n\n"
            "Read the repo snippets below and return 2 to 5 frontend-only recommendations that "
            "directly improve the observed UX issues. Mention likely files or components inside "
            "the likely_fix when possible. Keep each recommendation concise and implementation-ready.\n\n"
            f"{repo_context}"
        )

    def _parse_response_json(self, payload: dict) -> dict:
        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return json.loads(output_text)

        fragments: list[str] = []
        for item in payload.get("output", []):
            for content in item.get("content", []):
                text = content.get("text") or content.get("value")
                if isinstance(text, str) and text.strip():
                    fragments.append(text)
        if not fragments:
            raise RuntimeError("OpenAI response did not include JSON output text.")
        return json.loads("\n".join(fragments))
