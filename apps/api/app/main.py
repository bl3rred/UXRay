from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.adapters.browser_use import BrowserUseAdapter
from app.auth import SupabaseAuthService
from app.config import AppConfig, ROOT_DIR
from app.db import SQLiteStore
from app.routes import projects, runs
from app.schemas import APIEnvelope
from app.services.evaluation import FetchEvaluationService
from app.services.queue import RunWorker
from app.services.repo_builder import LocalRepoBuilder
from app.services.source_review import GPTSourceReviewService


def create_app(
    config: AppConfig | None = None,
    adapter=None,
    auth_service=None,
    repo_builder=None,
    source_reviewer=None,
) -> FastAPI:
    resolved_config = config or AppConfig.from_env()
    resolved_config.validate()
    store = SQLiteStore(resolved_config.db_path)
    store.init_db()
    resolved_config.artifacts_dir.mkdir(parents=True, exist_ok=True)
    resolved_auth_service = auth_service or SupabaseAuthService(
        supabase_url=resolved_config.supabase_url,
        publishable_key=resolved_config.supabase_publishable_key,
    )

    if adapter is None:
        if not resolved_config.browser_use_api_key:
            raise RuntimeError("BROWSER_USE_API_KEY is required to run the UXRay API")
        adapter = BrowserUseAdapter(
            api_key=resolved_config.browser_use_api_key,
            model=resolved_config.browser_use_model,
            artifacts_dir=resolved_config.artifacts_dir,
            supabase_url=resolved_config.supabase_url,
            supabase_service_role_key=resolved_config.supabase_service_role_key,
            supabase_storage_bucket=resolved_config.supabase_storage_bucket,
            run_timeout_seconds=resolved_config.browser_use_run_timeout_seconds,
        )

    resolved_repo_builder = repo_builder or LocalRepoBuilder(
        enabled=resolved_config.local_repo_build_enabled,
        build_root=resolved_config.local_repo_build_root,
    )
    resolved_source_reviewer = source_reviewer or GPTSourceReviewService(
        enabled=resolved_config.source_review_enabled,
        api_key=resolved_config.source_review_api_key,
        model=resolved_config.source_review_model,
        timeout_seconds=resolved_config.source_review_timeout_seconds,
    )

    worker = RunWorker(
        store=store,
        adapter=adapter,
        evaluator=FetchEvaluationService(
            enabled=resolved_config.fetch_evaluation_enabled,
            agent_url=resolved_config.fetch_evaluation_agent_url,
            api_key=resolved_config.fetch_evaluation_api_key,
            timeout_seconds=resolved_config.fetch_evaluation_timeout_seconds,
            asi_api_key=resolved_config.fetch_evaluation_asi_api_key,
            asi_model=resolved_config.fetch_evaluation_asi_model,
        ),
        repo_builder=resolved_repo_builder,
        source_reviewer=resolved_source_reviewer,
        poll_seconds=resolved_config.queue_poll_seconds,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if resolved_config.start_worker:
            worker.start()
        try:
            yield
        finally:
            if resolved_config.start_worker:
                worker.stop()
            worker.repo_builder.close()
            resolved_auth_service.close()

    app = FastAPI(title="UXRay API", lifespan=lifespan)
    app.state.config = resolved_config
    app.state.store = store
    app.state.worker = worker
    app.state.auth_service = resolved_auth_service

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in resolved_config.frontend_origin.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=APIEnvelope)
    def healthcheck() -> APIEnvelope:
        return APIEnvelope(
            data={
                "status": "ok",
                "browser_use_model": resolved_config.browser_use_model,
                "fetch_evaluation_enabled": resolved_config.fetch_evaluation_enabled,
                "local_repo_build_enabled": resolved_config.local_repo_build_enabled,
                "source_review_enabled": resolved_config.source_review_enabled,
            }
        )

    def resolve_artifact_file(artifact_path: str) -> Path | None:
        relative = Path(artifact_path)
        if relative.is_absolute() or ".." in relative.parts:
            return None

        search_roots = [resolved_config.artifacts_dir, ROOT_DIR]
        for root in search_roots:
            resolved_root = root.resolve()
            candidate = (resolved_root / relative).resolve()
            if resolved_root not in {candidate, *candidate.parents}:
                continue
            if candidate.is_file():
                return candidate
        return None

    @app.get("/artifacts/{artifact_path:path}")
    def get_artifact(artifact_path: str) -> FileResponse:
        resolved = resolve_artifact_file(artifact_path)
        if resolved is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        return FileResponse(resolved)

    app.include_router(projects.router)
    app.include_router(runs.router)
    return app


app = create_app()
