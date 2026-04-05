from __future__ import annotations

import asyncio
import threading
import time

from app.adapters.browser_use import describe_persona_mission
from app.db import SQLiteStore
from app.schemas import AdapterRunResult, PersonaRunResult
from app.services.analyzer import analyze_adapter_result, merge_persona_run_results
from app.services.repo_builder import RepoPreviewResult


CORE_PERSONAS: tuple[tuple[str, str], ...] = (
    ("first_time_visitor", "First-time visitor"),
    ("intent_driven", "Intent-driven"),
    ("trust_evaluator", "Trust evaluator"),
)

LOW_SIGNAL_PROGRESS_FRAGMENTS = (
    "screenshot capture expired or was unavailable",
    "browser use run is capped",
)
SOURCE_REVIEW_RATE_LIMIT_ERROR = "Gemini source review is currently rate limited (429)."


class RunWorker:
    def __init__(
        self,
        store: SQLiteStore,
        adapter,
        evaluator,
        repo_builder,
        tunnel_manager,
        source_reviewer,
        poll_seconds: float = 0.5,
        source_review_queue_retry_attempts: int = 1,
        source_review_retry_delay_seconds: float = 30.0,
        sleep_fn=time.sleep,
    ) -> None:
        self.store = store
        self.adapter = adapter
        self.evaluator = evaluator
        self.repo_builder = repo_builder
        self.tunnel_manager = tunnel_manager
        self.source_reviewer = source_reviewer
        self.poll_seconds = poll_seconds
        self.source_review_queue_retry_attempts = source_review_queue_retry_attempts
        self.source_review_retry_delay_seconds = source_review_retry_delay_seconds
        self.sleep_fn = sleep_fn
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run_loop, name="uxray-run-worker", daemon=True)

    def start(self) -> None:
        if not self.thread.is_alive():
            self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread.is_alive():
            self.thread.join(timeout=5)

    def _run_loop(self) -> None:
        while not self.stop_event.is_set():
            claimed = self.store.claim_next_run()
            if claimed is None:
                self.stop_event.wait(self.poll_seconds)
                continue

            run_id = claimed["run_id"]

            def progress_callback(payload: dict[str, str | None]) -> None:
                live_url = payload.get("live_url")
                if live_url:
                    self.store.update_run_live_url(run_id, live_url)
                summary = payload.get("summary")
                if summary:
                    self.store.add_progress_event(
                        run_id=run_id,
                        summary=summary,
                        event_type=payload.get("type") or "assistant",
                        screenshot_url=payload.get("screenshot_url"),
                    )

            try:
                target_url, target_source, preview, local_preview_url, public_preview_url = self._resolve_run_target(
                    claimed, progress_callback
                )
                persona_specs = list(CORE_PERSONAS)
                custom_audience = claimed.get("custom_audience")
                if custom_audience:
                    persona_specs.append(("custom_audience", "Custom audience"))

                self.store.add_progress_event(
                    run_id=run_id,
                    summary=(
                        "Starting multi-persona Browser Use audit with "
                        f"{len(persona_specs)} persona sessions."
                    ),
                    event_type="system",
                )

                persona_results = asyncio.run(
                    self._execute_persona_runs(
                        run_id=run_id,
                        project_name=claimed["name"],
                        project_url=target_url,
                        model=claimed["browser_use_model"],
                        persona_specs=persona_specs,
                        custom_audience=custom_audience,
                        parent_progress_callback=progress_callback,
                    )
                )

                successful_results = [result for result in persona_results if result.status == "completed"]
                if not successful_results:
                    raise RuntimeError("All persona Browser Use sessions failed.")
                salvaged_results = [result for result in successful_results if result.result_mode == "salvaged"]
                if salvaged_results:
                    self.store.add_progress_event(
                        run_id=run_id,
                        summary=(
                            "Continuing with fallback persona evidence for "
                            f"{len(salvaged_results)} persona session"
                            f"{'' if len(salvaged_results) == 1 else 's'}."
                        ),
                        event_type="system",
                    )

                self.store.add_progress_event(
                    run_id=run_id,
                    summary="Persona Browser Use sessions completed. Merging findings.",
                    event_type="system",
                )
                aggregate_result: AdapterRunResult = merge_persona_run_results(successful_results)
                analysis = analyze_adapter_result(aggregate_result)
                self.store.add_progress_event(
                    run_id=run_id,
                    summary="Merged persona findings. Finalizing the run and scheduling enrichments.",
                    event_type="system",
                )
                evaluation_status = (
                    "pending"
                    if self.evaluator.enabled and analysis.issues
                    else "skipped"
                )
                source_review_status = (
                    "pending"
                    if preview is not None and self.source_reviewer.enabled
                    else "skipped"
                )
                self.store.complete_run(
                    run_id=run_id,
                    live_url=aggregate_result.live_url,
                    final_url=aggregate_result.final_url,
                    target_url=target_url,
                    local_preview_url=local_preview_url,
                    public_preview_url=public_preview_url,
                    target_source=target_source,
                    summary=aggregate_result.summary,
                    analysis=analysis,
                    evaluation_status=evaluation_status,
                    evaluation_error=None,
                    source_review_status=source_review_status,
                    source_review_error=None,
                )
                self._spawn_fetch_enrichment(
                    run_id=run_id,
                    project_name=claimed["name"],
                    project_url=target_url,
                    analysis=analysis,
                    total_persona_count=len(persona_results),
                    successful_persona_count=len(successful_results),
                )
                self._spawn_source_review_enrichment(
                    run_id=run_id,
                    project_name=claimed["name"],
                    preview=preview,
                    analysis=analysis,
                )
            except Exception as exc:
                self.store.fail_run(run_id, str(exc))

    def _resolve_run_target(
        self,
        claimed: dict[str, str],
        progress_callback,
    ) -> tuple[str, str, RepoPreviewResult | None, str | None, str | None]:
        repo_url = claimed.get("repo_url")
        site_url = claimed.get("url")
        if not repo_url:
            target_url = site_url
            if not target_url:
                raise RuntimeError("Project has no website URL to audit.")
            self.store.update_repo_build_state(
                claimed["run_id"],
                repo_build_status="not_requested",
                repo_build_error=None,
                target_url=target_url,
                local_preview_url=None,
                public_preview_url=None,
                target_source="site",
            )
            return target_url, "site", None, None, None

        self.store.update_repo_build_state(
            claimed["run_id"],
            repo_build_status="running",
            repo_build_error=None,
        )
        progress_callback(
            {
                "summary": "Preparing a local preview from the linked public repository.",
                "type": "system",
                "screenshot_url": None,
                "live_url": None,
            }
        )
        try:
            preview = self.repo_builder.ensure_preview(
                project_id=claimed["project_id"],
                repo_url=repo_url,
                progress=lambda message: progress_callback(
                    {
                        "summary": message,
                        "type": "system",
                        "screenshot_url": None,
                        "live_url": None,
                    }
                ),
            )
        except Exception as exc:
            fallback_url = site_url
            self.store.update_repo_build_state(
                claimed["run_id"],
                repo_build_status="failed",
                repo_build_error=str(exc),
            )
            if fallback_url:
                progress_callback(
                    {
                        "summary": f"Repo preview failed. Falling back to the provided website URL. {exc}",
                        "type": "system",
                        "screenshot_url": None,
                        "live_url": None,
                    }
                )
                self.store.update_repo_build_state(
                    claimed["run_id"],
                    repo_build_status="failed",
                    repo_build_error=str(exc),
                    target_url=fallback_url,
                    local_preview_url=None,
                    public_preview_url=None,
                    target_source="site",
                )
                return fallback_url, "site", None, None, None
            raise RuntimeError(f"Public repo preview failed and no website URL fallback exists. {exc}") from exc

        progress_callback(
            {
                "summary": "Exposing the local repo preview through a temporary public URL for Browser Use.",
                "type": "system",
                "screenshot_url": None,
                "live_url": None,
            }
        )
        try:
            public_preview_url = self.tunnel_manager.expose(preview.preview_url)
        except Exception as exc:
            fallback_url = site_url
            self.store.update_repo_build_state(
                claimed["run_id"],
                repo_build_status="failed",
                repo_build_error=str(exc),
                local_preview_url=preview.preview_url,
                public_preview_url=None,
            )
            if fallback_url:
                progress_callback(
                    {
                        "summary": f"Repo preview tunnel failed. Falling back to the provided website URL. {exc}",
                        "type": "system",
                        "screenshot_url": None,
                        "live_url": None,
                    }
                )
                self.store.update_repo_build_state(
                    claimed["run_id"],
                    repo_build_status="failed",
                    repo_build_error=str(exc),
                    target_url=fallback_url,
                    local_preview_url=preview.preview_url,
                    public_preview_url=None,
                    target_source="site",
                )
                return fallback_url, "site", None, None, None
            raise RuntimeError(
                f"Public repo preview tunnel failed and no website URL fallback exists. {exc}"
            ) from exc

        self.store.update_repo_build_state(
            claimed["run_id"],
            repo_build_status="completed",
            repo_build_error=None,
            target_url=public_preview_url,
            local_preview_url=preview.preview_url,
            public_preview_url=public_preview_url,
            target_source="repo_preview",
        )
        progress_callback(
            {
                "summary": (
                    f"Using tunneled repo preview at {public_preview_url} "
                    f"(local preview {preview.preview_url})."
                ),
                "type": "system",
                "screenshot_url": None,
                "live_url": None,
            }
        )
        return public_preview_url, "repo_preview", preview, preview.preview_url, public_preview_url

    def _spawn_fetch_enrichment(
        self,
        *,
        run_id: str,
        project_name: str,
        project_url: str,
        analysis,
        total_persona_count: int,
        successful_persona_count: int,
    ) -> None:
        if not self.evaluator.enabled or not analysis.issues:
            self.store.update_evaluation_status(run_id, "skipped", None)
            return

        self.store.update_evaluation_status(run_id, "running", None)
        self.store.add_progress_event(
            run_id=run_id,
            summary="Fetch.ai review started in the background.",
            event_type="system",
        )

        def runner() -> None:
            evaluations = self.evaluator.evaluate(
                project_name=project_name,
                project_url=project_url,
                issues=analysis.issues,
            )
            if evaluations.status == "completed":
                self.store.save_evaluations(run_id, evaluations)
                self.store.update_evaluation_status(run_id, "completed", None)
                used_asi_fallback = any(
                    evaluation.source == "fetch_ai_asi_fallback"
                    for evaluation in evaluations.evaluations
                )
                self.store.add_progress_event(
                    run_id=run_id,
                    summary=(
                        "Fetch.ai review completed through ASI fallback."
                        if used_asi_fallback
                        else "Fetch.ai review completed."
                    ),
                    event_type="system",
                )
                return

            partial_note = ""
            if successful_persona_count != total_persona_count:
                partial_note = (
                    f" Persona evidence was partial: {successful_persona_count} of "
                    f"{total_persona_count} persona sessions succeeded."
                )
            error_message = evaluations.error or "Unknown relay or orchestrator error."
            self.store.update_evaluation_status(run_id, evaluations.status, error_message)
            self.store.add_progress_event(
                run_id=run_id,
                summary=f"Fetch.ai review failed: {error_message}{partial_note}",
                event_type="system",
            )

        threading.Thread(
            target=runner,
            name=f"uxray-fetch-review-{run_id}",
            daemon=True,
        ).start()

    def _spawn_source_review_enrichment(
        self,
        *,
        run_id: str,
        project_name: str,
        preview: RepoPreviewResult | None,
        analysis,
    ) -> None:
        if preview is None:
            self.store.update_source_review_status(run_id, "skipped", None)
            return
        if not self.source_reviewer.enabled:
            self.store.update_source_review_status(run_id, "skipped", None)
            return

        self.store.update_source_review_status(run_id, "running", None)
        self.store.add_progress_event(
            run_id=run_id,
            summary="Gemini source review started in the background.",
            event_type="system",
        )

        def runner() -> None:
            queued_retries_remaining = self.source_review_queue_retry_attempts
            while True:
                result = self.source_reviewer.review(
                    project_name=project_name,
                    repo_path=preview.repo_path,
                    framework=preview.framework,
                    issues=analysis.issues,
                )
                if result.status == "completed":
                    self.store.add_recommendations(run_id, result.recommendations)
                    self.store.update_source_review_status(run_id, "completed", None)
                    self.store.add_progress_event(
                        run_id=run_id,
                        summary="Gemini source review completed.",
                        event_type="system",
                    )
                    return

                is_rate_limited = (result.error or "") == SOURCE_REVIEW_RATE_LIMIT_ERROR
                if is_rate_limited and queued_retries_remaining > 0:
                    queued_retries_remaining -= 1
                    wait_seconds = int(self.source_review_retry_delay_seconds)
                    queued_message = (
                        "Gemini source review hit a rate limit. "
                        f"Queued one retry in {wait_seconds} seconds."
                    )
                    self.store.update_source_review_status(run_id, "pending", queued_message)
                    self.store.add_progress_event(
                        run_id=run_id,
                        summary=queued_message,
                        event_type="system",
                    )
                    self.sleep_fn(self.source_review_retry_delay_seconds)
                    self.store.update_source_review_status(
                        run_id,
                        "running",
                        "Retrying Gemini source review after rate limit.",
                    )
                    self.store.add_progress_event(
                        run_id=run_id,
                        summary="Retrying Gemini source review after rate limit.",
                        event_type="system",
                    )
                    continue

                self.store.update_source_review_status(run_id, result.status, result.error)
                if result.error:
                    self.store.add_progress_event(
                        run_id=run_id,
                        summary=f"Gemini source review failed: {result.error}",
                        event_type="system",
                    )
                return

        threading.Thread(
            target=runner,
            name=f"uxray-source-review-{run_id}",
            daemon=True,
        ).start()

    def schedule_fetch_retry(self, run_id: str) -> bool:
        context = self.store.get_run_enrichment_context(run_id)
        if (
            not context
            or not context["issues"]
            or not context.get("target_url")
            or not self.evaluator.enabled
        ):
            return False
        self.store.update_evaluation_status(run_id, "pending", None)
        self._spawn_fetch_enrichment(
            run_id=run_id,
            project_name=context["project_name"],
            project_url=context["target_url"] or "",
            analysis=type("AnalysisCarrier", (), {"issues": context["issues"]})(),
            total_persona_count=len(context["issues"]),
            successful_persona_count=len(context["issues"]),
        )
        return True

    @staticmethod
    def _should_persist_persona_progress(payload: dict[str, str | None]) -> bool:
        summary = (payload.get("summary") or "").strip()
        if not summary:
            return False
        lowered = summary.lower()
        if any(fragment in lowered for fragment in LOW_SIGNAL_PROGRESS_FRAGMENTS):
            return False
        event_type = payload.get("type") or "assistant"
        if event_type == "system":
            return True
        high_signal_markers = (
            "submitting ",
            "opened ",
            "opening ",
            "navigating",
            "reviewed ",
            "checking ",
            "checked ",
            "attempting ",
            "skipping ",
            "skipped ",
            "blocked ",
            "fallback",
            "login",
            "guest",
            "pricing",
            "signup",
            "cart",
            "trust",
            "support",
        )
        return any(marker in lowered for marker in high_signal_markers)

    async def _execute_persona_runs(
        self,
        *,
        run_id: str,
        project_name: str,
        project_url: str,
        model: str,
        persona_specs: list[tuple[str, str]],
        custom_audience: str | None,
        parent_progress_callback,
    ) -> list[PersonaRunResult]:
        persona_sessions = {
            persona_key: self.store.create_persona_session(
                run_id,
                persona_key,
                display_label,
                describe_persona_mission(
                    persona_key,
                    custom_audience if persona_key == "custom_audience" else None,
                ),
            )
            for persona_key, display_label in persona_specs
        }

        async def run_persona(persona_key: str, display_label: str) -> PersonaRunResult:
            persona_session = persona_sessions[persona_key]
            persona_session_id = persona_session.id
            self.store.start_persona_session(persona_session_id)
            parent_progress_callback(
                {
                    "summary": f"{display_label} session started.",
                    "type": "system",
                    "screenshot_url": None,
                    "live_url": None,
                }
            )

            def session_progress_callback(payload: dict[str, str | None]) -> None:
                live_url = payload.get("live_url")
                if live_url:
                    self.store.update_persona_session_live_url(persona_session_id, live_url)
                    self.store.update_run_live_url(run_id, live_url)
                summary = payload.get("summary")
                if summary and self._should_persist_persona_progress(payload):
                    self.store.add_persona_progress_event(
                        persona_session_id,
                        summary=summary,
                        event_type=payload.get("type") or "assistant",
                        screenshot_url=payload.get("screenshot_url"),
                    )

            try:
                result = await self.adapter.execute_run(
                    run_id=run_id,
                    project_name=project_name,
                    project_url=project_url,
                    model=model,
                    progress_callback=session_progress_callback,
                    persona_key=persona_key,
                    custom_audience=custom_audience if persona_key == "custom_audience" else None,
                )
                self.store.complete_persona_session(
                    persona_session_id,
                    result_mode=result.result_mode,
                    live_url=result.live_url,
                    final_url=result.final_url,
                    summary=result.summary,
                    observations=[observation.model_dump() for observation in result.observations],
                    artifacts=result.artifacts,
                )
                if result.live_url:
                    self.store.update_run_live_url(run_id, result.live_url)
                parent_progress_callback(
                    {
                        "summary": f"{display_label} session completed.",
                        "type": "system",
                        "screenshot_url": None,
                        "live_url": None,
                    }
                )
                return PersonaRunResult(
                    persona_key=persona_key,
                    display_label=display_label,
                    mission=persona_session.mission,
                    status="completed",
                    result_mode=result.result_mode,
                    live_url=result.live_url,
                    final_url=result.final_url,
                    summary=result.summary,
                    observations=result.observations,
                    artifacts=result.artifacts,
                )
            except Exception as exc:
                error_message = str(exc)
                self.store.fail_persona_session(persona_session_id, error_message)
                parent_progress_callback(
                    {
                        "summary": f"{display_label} session failed: {error_message}",
                        "type": "system",
                        "screenshot_url": None,
                        "live_url": None,
                    }
                )
                return PersonaRunResult(
                    persona_key=persona_key,
                    display_label=display_label,
                    mission=persona_session.mission,
                    status="failed",
                    result_mode="failed",
                    error_message=error_message,
                )

        tasks = [run_persona(persona_key, display_label) for persona_key, display_label in persona_specs]
        return await asyncio.gather(*tasks)
