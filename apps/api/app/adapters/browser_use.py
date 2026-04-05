from __future__ import annotations

import asyncio
import inspect
import mimetypes
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from app.schemas import (
    AdapterObservation,
    AdapterRunResult,
    BrowserUseAuditOutput,
    BrowserUseMessage,
)


ProgressCallback = Callable[[dict[str, str | None]], None]

LOW_SIGNAL_SUMMARY_FRAGMENTS = (
    "read image",
    "image file",
    "read the image",
    "opened screenshot",
    "loaded screenshot",
    "analyzed screenshot",
    "extracting text",
)

PERSONA_DISPLAY_LABELS = {
    "first_time_visitor": "First-time visitor",
    "intent_driven": "Intent-driven",
    "trust_evaluator": "Trust evaluator",
    "custom_audience": "Custom audience",
}


class BrowserUseInvalidOutputError(RuntimeError):
    def __init__(
        self,
        raw_output: str,
        attempts: int,
        *,
        messages: list[dict[str, str | None]] | None = None,
        live_url: str | None = None,
        final_url: str | None = None,
        artifacts: list[dict[str, str]] | None = None,
    ) -> None:
        self.raw_output = raw_output
        self.attempts = attempts
        self.messages = messages or []
        self.live_url = live_url
        self.final_url = final_url
        self.artifacts = artifacts or []
        snippet = raw_output.strip() or "Empty output"
        super().__init__(
            f"Browser Use returned invalid structured output after {attempts} attempts: {snippet}"
        )


def describe_persona_mission(persona_key: str, custom_audience: str | None = None) -> str:
    if persona_key == "first_time_visitor":
        return "Audit like a first-time visitor focused on orientation, clarity, and whether the next step is obvious."
    if persona_key == "intent_driven":
        return "Audit like a goal-driven user focused on speed to value, CTA clarity, and the shortest useful path."
    if persona_key == "trust_evaluator":
        return "Audit like a skeptical evaluator focused on credibility, reassurance, policy visibility, and conversion hesitation."
    custom_context = custom_audience or "a stakeholder with a strong business-risk lens"
    return f"Audit through this custom audience lens: {custom_context}."


def build_persona_task(
    *,
    project_url: str,
    project_name: str,
    persona_key: str,
    custom_audience: str | None,
    strict_json: bool = False,
) -> str:
    display_label = PERSONA_DISPLAY_LABELS.get(persona_key, persona_key.replace("_", " ").title())
    mission = describe_persona_mission(persona_key, custom_audience)
    strict_suffix = (
        " CRITICAL: Return valid JSON only. Do not include markdown fences, explanation, or any prose outside the schema. "
        "If the audit yields limited evidence, still return a valid JSON object with a concise summary and the best concrete observations you have."
        if strict_json
        else ""
    )
    shared = (
        f"Persona: {display_label}. "
        f"Mission: {mission} "
        "You are auditing a website for UX friction. "
        f"Open {project_url} for the project '{project_name}'. "
        "Inspect the homepage plus 2 to 4 additional meaningful pages, but stop early once you have enough evidence and page coverage to support 3 to 8 strong observations. "
        "Treat the timeout cap as a ceiling, not a target. "
        "If a page stalls, traps you in client-side loops, auto-signs you into remembered guest or authenticated state, or needs excessive JavaScript interaction, go around it quickly and continue to the next meaningful path. "
        "Try an alternate route before giving up: use site navigation, footer links, breadcrumbs, search, pricing/product pages, or trust/support pages instead of repeating the same stuck action. "
        "Do not spend time trying to fully complete flaky or gated flows. "
        "Treat login, sign-in, and account walls as neutral product boundaries by default. "
        "Do not record a login page as a UX issue just because credentials are required or because you cannot continue without signing in. "
        "Only report login or account-access problems if the authentication experience itself is clearly broken, misleading, or unexpectedly blocks public discovery that should be available. "
        "Assume you are auditing as a fresh visitor and do not rely on remembered sessions, cookies, or prior guest state. "
        "Return structured output only. Include 3 to 8 concrete observations with route, title, "
        "description, severity, evidence bullets, and screenshot URL if available. "
        "Focus on real friction, clarity, feedback, and trust issues. Do not propose code-level fixes."
        f"{strict_suffix}"
    )

    if persona_key == "first_time_visitor":
        return (
            f"{shared} "
            "Navigate like someone who has never seen the site before. "
            "Prioritize orientation, clarity, messaging comprehension, discoverability, and whether the next step is obvious."
        )
    if persona_key == "intent_driven":
        return (
            f"{shared} "
            "Navigate like a goal-driven user trying to complete a task quickly. "
            "Prioritize path efficiency, CTA clarity, flow speed, and blockers on the shortest route to value."
        )
    if persona_key == "trust_evaluator":
        return (
            f"{shared} "
            "Navigate like a skeptical user evaluating whether the site is credible and safe. "
            "Prioritize trust cues, reassurance, policy/support visibility, and hesitation points around conversion."
        )
    custom_context = custom_audience or "a stakeholder with a strong business-risk lens"
    return (
        f"{shared} "
        f"Navigate through the lens of this custom audience: {custom_context}. "
        "Prioritize the routes and moments most relevant to that audience's goals, concerns, and heuristics."
    )


class BrowserUseAdapter:
    def __init__(
        self,
        api_key: str,
        model: str,
        artifacts_dir: Path,
        supabase_url: str | None = None,
        supabase_service_role_key: str | None = None,
        supabase_storage_bucket: str | None = None,
        run_timeout_seconds: float = 240.0,
    ) -> None:
        self.api_key = api_key
        self.default_model = model
        self.artifacts_dir = artifacts_dir
        self.supabase_url = (supabase_url or "").rstrip("/")
        self.supabase_service_role_key = supabase_service_role_key or ""
        self.supabase_storage_bucket = supabase_storage_bucket or ""
        self.run_timeout_seconds = run_timeout_seconds

    @property
    def storage_enabled(self) -> bool:
        return bool(
            self.supabase_url and self.supabase_service_role_key and self.supabase_storage_bucket
        )

    @staticmethod
    def display_label_for_persona(persona_key: str) -> str:
        return PERSONA_DISPLAY_LABELS.get(persona_key, persona_key.replace("_", " ").title())

    @staticmethod
    def _extract_live_url(run_result: Any) -> str | None:
        live_url = getattr(run_result, "live_url", None)
        if isinstance(live_url, str) and live_url:
            return live_url
        return None

    @staticmethod
    def _extract_session_id(run_handle: Any) -> str | None:
        session_id = getattr(run_handle, "session_id", None)
        return str(session_id) if session_id else None

    @staticmethod
    def _normalize_raw_message(raw_message: Any) -> BrowserUseMessage | None:
        hidden = raw_message.get("hidden") if isinstance(raw_message, dict) else getattr(raw_message, "hidden", False)
        if hidden:
            return None

        payload = {
            "summary": raw_message.get("summary") if isinstance(raw_message, dict) else getattr(raw_message, "summary", None),
            "type": raw_message.get("type") if isinstance(raw_message, dict) else getattr(raw_message, "type", None),
            "screenshot_url": raw_message.get("screenshot_url") if isinstance(raw_message, dict) else getattr(raw_message, "screenshot_url", None),
        }
        try:
            parsed = BrowserUseMessage.model_validate(payload)
        except Exception:
            return None
        if not parsed.summary:
            return None
        summary_lower = parsed.summary.lower()
        if any(fragment in summary_lower for fragment in LOW_SIGNAL_SUMMARY_FRAGMENTS):
            return None
        return parsed

    @staticmethod
    def _normalize_output_payload(output: Any) -> BrowserUseAuditOutput:
        if isinstance(output, BrowserUseAuditOutput):
            return output
        if isinstance(output, dict):
            return BrowserUseAuditOutput.model_validate(output)
        if isinstance(output, str):
            return BrowserUseAuditOutput.model_validate_json(output)
        if output is None:
            raise ValueError("Empty output")
        return BrowserUseAuditOutput.model_validate(output, from_attributes=True)

    @staticmethod
    def _extract_route_from_url(url: str | None) -> str:
        if not url:
            return "/"
        path = urlparse(url).path or "/"
        return path if path.startswith("/") else f"/{path}"

    @staticmethod
    def _infer_salvage_severity(summary: str) -> str:
        lowered = summary.lower()
        high_markers = (
            "blocked",
            "failed",
            "error",
            "stuck",
            "unable",
            "cannot",
            "can't",
            "timed out",
            "timeout",
        )
        if any(marker in lowered for marker in high_markers):
            return "high"
        return "medium"

    @staticmethod
    def _is_auth_wall_observation(
        route: str,
        title: str,
        description: str,
        evidence: list[str],
    ) -> bool:
        haystack = " ".join([route, title, description, *evidence]).lower()
        auth_route_markers = (
            "/login",
            "/signin",
            "/sign-in",
            "/account/login",
            "/auth",
        )
        auth_problem_markers = (
            "broken login",
            "incorrect password",
            "form error",
            "validation missing",
            "captcha",
            "redirect loop",
            "reset password",
            "sign in button did nothing",
        )
        auth_wall_markers = (
            "must sign in",
            "must log in",
            "requires login",
            "requires sign in",
            "authentication wall",
            "account wall",
            "cannot continue without logging in",
            "could not log in",
            "unable to log in",
            "guest mode",
            "login required",
            "sign in required",
        )
        if any(marker in haystack for marker in auth_problem_markers):
            return False
        if any(marker in haystack for marker in auth_wall_markers):
            return True
        return any(marker in route.lower() for marker in auth_route_markers) and "public" not in haystack

    @staticmethod
    def _title_from_summary(summary: str) -> str:
        candidate = summary.strip().rstrip(".")
        if len(candidate) <= 96:
            return candidate
        return f"{candidate[:93].rstrip()}..."

    @staticmethod
    def _guess_extension(source_url: str, content_type: str | None) -> str:
        parsed = urlparse(source_url)
        suffix = Path(parsed.path).suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
            return suffix

        if content_type:
            guessed = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
            if guessed:
                if guessed == ".jpe":
                    return ".jpg"
                return guessed
        return ".png"

    async def _download_remote_asset(
        self,
        source_url: str,
    ) -> tuple[bytes, str | None]:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await client.get(source_url)
            response.raise_for_status()
        return response.content, response.headers.get("content-type")

    def _write_asset_to_disk(self, relative_path: Path, content: bytes) -> str:
        target_dir = self.artifacts_dir / relative_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = self.artifacts_dir / relative_path
        target_path.write_bytes(content)
        return relative_path.as_posix()

    def _build_supabase_public_asset_url(self, object_path: str) -> str:
        encoded_path = quote(object_path, safe="/")
        return (
            f"{self.supabase_url}/storage/v1/object/public/"
            f"{self.supabase_storage_bucket}/{encoded_path}"
        )

    async def _upload_asset_to_supabase(
        self,
        *,
        object_path: str,
        content: bytes,
        content_type: str | None,
    ) -> str:
        if not self.storage_enabled:
            raise RuntimeError("Supabase Storage is not configured")

        upload_url = (
            f"{self.supabase_url}/storage/v1/object/"
            f"{self.supabase_storage_bucket}/{quote(object_path, safe='/')}"
        )
        headers = {
            "Authorization": f"Bearer {self.supabase_service_role_key}",
            "apikey": self.supabase_service_role_key,
            "x-upsert": "true",
            "Content-Type": (content_type or "application/octet-stream").split(";", 1)[0].strip(),
        }
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await client.post(upload_url, headers=headers, content=content)
            response.raise_for_status()

        return self._build_supabase_public_asset_url(object_path)

    async def _persist_remote_asset(
        self,
        source_url: str | None,
        run_id: str,
        persona_key: str,
        prefix: str,
        index: int,
    ) -> str | None:
        if not source_url:
            return None
        if not source_url.lower().startswith(("http://", "https://")):
            return source_url

        content, content_type = await self._download_remote_asset(source_url)
        relative = Path("browser-use") / run_id / persona_key
        extension = self._guess_extension(source_url, content_type)
        filename = f"{prefix}-{index:03d}{extension}"
        object_path = (relative / filename).as_posix()

        if self.storage_enabled:
            try:
                return await self._upload_asset_to_supabase(
                    object_path=object_path,
                    content=content,
                    content_type=content_type,
                )
            except (httpx.HTTPError, OSError):
                pass

        return self._write_asset_to_disk(relative / filename, content)

    async def _try_persist_remote_asset(
        self,
        source_url: str | None,
        run_id: str,
        persona_key: str,
        prefix: str,
        index: int,
    ) -> tuple[str | None, str | None]:
        try:
            persisted = await self._persist_remote_asset(
                source_url,
                run_id,
                persona_key,
                prefix,
                index,
            )
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response is not None else "unknown"
            return None, f"Screenshot capture expired or was unavailable ({status_code}) while saving {prefix} evidence."
        except httpx.HTTPError:
            return None, f"Screenshot capture was unavailable while saving {prefix} evidence."
        except OSError:
            return None, f"Local artifact persistence failed while saving {prefix} evidence."
        return persisted, None

    async def _materialize_message(
        self,
        raw_message: Any,
        run_id: str,
        persona_key: str,
        index: int,
    ) -> tuple[dict[str, str | None] | None, str | None]:
        parsed = self._normalize_raw_message(raw_message)
        if parsed is None:
            return None, None

        screenshot_url, warning = await self._try_persist_remote_asset(
            parsed.screenshot_url,
            run_id,
            persona_key,
            prefix="progress",
            index=index,
        )
        return (
            {
                "summary": parsed.summary,
                "type": parsed.type or "assistant",
                "screenshot_url": screenshot_url,
                "live_url": None,
            },
            warning,
        )

    async def _lookup_live_url(self, run_handle: Any) -> str | None:
        session_id = self._extract_session_id(run_handle)
        sessions = getattr(run_handle, "_sessions", None)
        if not session_id or sessions is None:
            return None

        try:
            session = await sessions.get(session_id)
        except Exception:
            return None
        return self._extract_live_url(session)

    async def _build_result_artifacts(
        self,
        *,
        result: Any,
        messages: list[dict[str, str | None]],
        run_id: str,
        persona_key: str,
        display_label: str,
        live_url: str | None,
        progress_callback: ProgressCallback,
    ) -> list[dict[str, str]]:
        artifacts: list[dict[str, str]] = []
        if live_url:
            artifacts.append(
                {
                    "kind": "live_url",
                    "label": f"{display_label} live session",
                    "path_or_url": str(live_url),
                }
            )

        session_screenshot, warning = await self._try_persist_remote_asset(
            getattr(result, "screenshot_url", None),
            run_id,
            persona_key,
            prefix="session",
            index=1,
        )
        if warning:
            progress_callback(
                {
                    "summary": f"{display_label}: {warning}",
                    "type": "system",
                    "screenshot_url": None,
                    "live_url": None,
                }
            )
        if session_screenshot:
            artifacts.append(
                {
                    "kind": "screenshot",
                    "label": f"{display_label} final session screenshot",
                    "path_or_url": session_screenshot,
                }
            )

        for index, message in enumerate(messages, start=1):
            screenshot_url = message.get("screenshot_url")
            summary = (message.get("summary") or "").strip()
            if not screenshot_url or not summary:
                continue
            artifacts.append(
                {
                    "kind": "screenshot",
                    "label": f"{display_label} progress evidence {index}: {summary[:96]}",
                    "path_or_url": screenshot_url,
                }
            )

        for index, recording_url in enumerate(getattr(result, "recording_urls", []) or [], start=1):
            if recording_url:
                artifacts.append(
                    {
                        "kind": "recording",
                        "label": f"{display_label} recording {index}",
                        "path_or_url": str(recording_url),
                    }
                )
        return artifacts

    def _salvage_result_from_messages(
        self,
        *,
        persona_key: str,
        display_label: str,
        project_url: str,
        invalid_output: BrowserUseInvalidOutputError,
    ) -> AdapterRunResult | None:
        unique_messages: list[dict[str, str | None]] = []
        seen_summaries: set[str] = set()
        for message in invalid_output.messages:
            summary = (message.get("summary") or "").strip()
            if not summary or summary in seen_summaries:
                continue
            seen_summaries.add(summary)
            unique_messages.append(message)

        candidates = unique_messages[-3:]
        if not candidates:
            return None

        final_url = invalid_output.final_url or project_url
        fallback_route = self._extract_route_from_url(final_url)
        observations: list[AdapterObservation] = []
        for message in candidates:
            summary = (message.get("summary") or "").strip()
            if not summary:
                continue
            observations.append(
                AdapterObservation(
                    route=fallback_route,
                    title=self._title_from_summary(summary),
                    description=(
                        "Recovered from streamed Browser Use progress after structured output failed: "
                        f"{summary}"
                    ),
                    severity=self._infer_salvage_severity(summary),
                    evidence=[
                        summary,
                        "Synthesized from streamed Browser Use progress after three invalid structured-output attempts.",
                    ],
                    screenshot_url=message.get("screenshot_url"),
                    personas=[persona_key],
                )
            )

        if not observations:
            return None

        return AdapterRunResult(
            result_mode="salvaged",
            live_url=invalid_output.live_url,
            final_url=final_url,
            summary=(
                f"{display_label} recovered fallback persona evidence from streamed Browser Use progress."
            ),
            observations=observations,
            artifacts=invalid_output.artifacts,
            messages=invalid_output.messages,
        )

    async def _close_run_handle(self, run_handle: Any) -> None:
        for method_name in ("close", "stop", "cancel", "shutdown"):
            method = getattr(run_handle, method_name, None)
            if not callable(method):
                continue
            try:
                result = method()
                if inspect.isawaitable(result):
                    await result
                return
            except Exception:
                continue

    async def execute_run(
        self,
        run_id: str,
        project_name: str,
        project_url: str,
        model: str,
        progress_callback: ProgressCallback,
        *,
        persona_key: str,
        custom_audience: str | None = None,
    ) -> AdapterRunResult:
        return await self._execute_run_with_retry(
            run_id=run_id,
            project_name=project_name,
            project_url=project_url,
            model=model,
            progress_callback=progress_callback,
            persona_key=persona_key,
            custom_audience=custom_audience,
        )

    async def _execute_run_with_retry(
        self,
        *,
        run_id: str,
        project_name: str,
        project_url: str,
        model: str,
        progress_callback: ProgressCallback,
        persona_key: str,
        custom_audience: str | None,
    ) -> AdapterRunResult:
        attempts = 3
        best_invalid_output: BrowserUseInvalidOutputError | None = None
        for attempt in range(1, attempts + 1):
            try:
                return await self._execute_run_once(
                    run_id=run_id,
                    project_name=project_name,
                    project_url=project_url,
                    model=model,
                    progress_callback=progress_callback,
                    persona_key=persona_key,
                    custom_audience=custom_audience,
                    attempt=attempt,
                    strict_json=attempt == attempts,
                )
            except BrowserUseInvalidOutputError as exc:
                if best_invalid_output is None or len(exc.messages) >= len(best_invalid_output.messages):
                    best_invalid_output = exc
                if attempt >= attempts:
                    display_label = self.display_label_for_persona(persona_key)
                    salvage = self._salvage_result_from_messages(
                        persona_key=persona_key,
                        display_label=display_label,
                        project_url=project_url,
                        invalid_output=best_invalid_output or exc,
                    )
                    if salvage is not None:
                        progress_callback(
                            {
                                "summary": (
                                    f"{display_label}: salvaging persona evidence from streamed "
                                    "Browser Use progress after invalid structured output."
                                ),
                                "type": "system",
                                "screenshot_url": None,
                                "live_url": None,
                            }
                        )
                        return salvage
                    raise RuntimeError(
                        "Browser Use returned invalid structured output after 3 attempts and no "
                        "salvageable evidence was available."
                    ) from exc
                display_label = self.display_label_for_persona(persona_key)
                progress_callback(
                    {
                        "summary": (
                            f"{display_label} retrying with strict JSON-only fallback after invalid "
                            "Browser Use output."
                            if attempt + 1 == attempts
                            else f"{display_label} retrying after invalid Browser Use output."
                        ),
                        "type": "system",
                        "screenshot_url": None,
                        "live_url": None,
                    }
                )
        raise RuntimeError(
            "Browser Use returned invalid structured output after 3 attempts and no salvageable evidence was available."
        )

    async def _execute_run_once(
        self,
        *,
        run_id: str,
        project_name: str,
        project_url: str,
        model: str,
        progress_callback: ProgressCallback,
        persona_key: str,
        custom_audience: str | None,
        attempt: int,
        strict_json: bool,
    ) -> AdapterRunResult:
        from browser_use_sdk.v3 import AsyncBrowserUse

        display_label = self.display_label_for_persona(persona_key)
        mission = describe_persona_mission(persona_key, custom_audience)
        os.environ["BROWSER_USE_API_KEY"] = self.api_key
        client = AsyncBrowserUse()
        task = build_persona_task(
            project_url=project_url,
            project_name=project_name,
            persona_key=persona_key,
            custom_audience=custom_audience,
            strict_json=strict_json,
        )

        progress_callback(
            {
                "summary": f"{display_label} mission: {mission}",
                "type": "system",
                "screenshot_url": None,
                "live_url": None,
            }
        )
        progress_callback(
            {
                "summary": f"{display_label}: submitting Browser Use cloud run request",
                "type": "system",
                "screenshot_url": None,
                "live_url": None,
            }
        )
        if attempt > 1:
            progress_callback(
                {
                    "summary": (
                        f"{display_label}: retry attempt {attempt} started with strict JSON-only fallback."
                        if strict_json
                        else f"{display_label}: retry attempt {attempt} started."
                    ),
                    "type": "system",
                    "screenshot_url": None,
                    "live_url": None,
                }
            )
        progress_callback(
            {
                "summary": f"{display_label}: Browser Use run is capped at {int(self.run_timeout_seconds)} seconds.",
                "type": "system",
                "screenshot_url": None,
                "live_url": None,
            }
        )

        run_handle = client.run(
            task=task,
            model=model or self.default_model,
            output_schema=BrowserUseAuditOutput,
            enable_recording=True,
            keep_alive=False,
        )
        if hasattr(run_handle, "_timeout"):
            run_handle._timeout = self.run_timeout_seconds
        if hasattr(run_handle, "_interval"):
            run_handle._interval = 1

        live_url: str | None = None
        live_announced = False
        messages: list[dict[str, str | None]] = []

        try:
            async with asyncio.timeout(self.run_timeout_seconds):
                async for raw_message in run_handle:
                    if not live_announced:
                        live_url = await self._lookup_live_url(run_handle)
                        if live_url:
                            progress_callback(
                                {
                                    "summary": f"{display_label}: Browser Use live session is available.",
                                    "type": "system",
                                    "screenshot_url": None,
                                    "live_url": live_url,
                                }
                            )
                            live_announced = True

                    next_message, warning = await self._materialize_message(
                        raw_message,
                        run_id,
                        persona_key,
                        index=len(messages) + 1,
                    )
                    if warning:
                        progress_callback(
                            {
                                "summary": f"{display_label}: {warning}",
                                "type": "system",
                                "screenshot_url": None,
                                "live_url": None,
                            }
                        )
                    if next_message is None:
                        continue
                    messages.append(next_message)
                    progress_callback(next_message)
        except TimeoutError as exc:
            raise TimeoutError(
                f"{display_label} Browser Use run timed out after {int(self.run_timeout_seconds)} seconds."
            ) from exc
        finally:
            await self._close_run_handle(run_handle)

        result: Any = getattr(run_handle, "result", None)
        if result is None:
            raise RuntimeError(f"{display_label} Browser Use did not return a final session result.")

        live_url = live_url or self._extract_live_url(result)
        if live_url and not live_announced:
            progress_callback(
                {
                    "summary": f"{display_label}: Browser Use live session is available.",
                    "type": "system",
                    "screenshot_url": None,
                    "live_url": live_url,
                }
            )

        artifacts = await self._build_result_artifacts(
            result=result,
            messages=messages,
            run_id=run_id,
            persona_key=persona_key,
            display_label=display_label,
            live_url=live_url,
            progress_callback=progress_callback,
        )

        raw_output = getattr(result, "output", None)
        try:
            output = self._normalize_output_payload(raw_output)
        except Exception:
            if isinstance(raw_output, str):
                raw_text = raw_output
            elif raw_output is None:
                raw_text = "Empty output"
            else:
                raw_text = str(raw_output)
            raise BrowserUseInvalidOutputError(
                raw_text,
                attempt,
                messages=messages,
                live_url=str(live_url) if live_url else None,
                final_url=project_url,
                artifacts=artifacts,
            )
        observations: list[AdapterObservation] = []
        for index, observation in enumerate(output.observations, start=1):
            if self._is_auth_wall_observation(
                observation.route,
                observation.title,
                observation.description,
                observation.evidence,
            ):
                continue
            screenshot_url, warning = await self._try_persist_remote_asset(
                observation.screenshot_url,
                run_id,
                persona_key,
                prefix="observation",
                index=index,
            )
            if warning:
                progress_callback(
                    {
                        "summary": f"{display_label}: {warning}",
                        "type": "system",
                        "screenshot_url": None,
                        "live_url": None,
                    }
                )
            observations.append(
                AdapterObservation(
                    route=observation.route,
                    title=observation.title,
                    description=observation.description,
                    severity=observation.severity,
                    evidence=observation.evidence,
                    screenshot_url=screenshot_url,
                    personas=[persona_key],
                )
            )

        return AdapterRunResult(
            result_mode="structured",
            live_url=str(live_url) if live_url else None,
            final_url=output.final_url or project_url,
            summary=output.summary,
            observations=observations,
            artifacts=artifacts,
            messages=messages,
        )
