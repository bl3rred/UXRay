from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.auth import resolve_request_identity
from app.schemas import APIEnvelope, ProjectCreate, RunCreate


router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=APIEnvelope, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, request: Request) -> APIEnvelope:
    identity = resolve_request_identity(request)
    project = request.app.state.store.create_project(
        name=payload.name,
        url=str(payload.url) if payload.url else None,
        repo_url=str(payload.repo_url) if payload.repo_url else None,
        owner_id=identity.user_id,
        guest_session_id=identity.guest_session_id,
    )
    detail = request.app.state.store.get_project(
        project.id,
        owner_id=identity.user_id,
        guest_session_id=identity.guest_session_id,
    )
    return APIEnvelope(data=detail)


@router.get("", response_model=APIEnvelope)
def list_projects(request: Request) -> APIEnvelope:
    identity = resolve_request_identity(request)
    return APIEnvelope(
        data=request.app.state.store.list_projects(
            owner_id=identity.user_id,
            guest_session_id=identity.guest_session_id,
        )
    )


@router.get("/{project_id}", response_model=APIEnvelope)
def get_project(project_id: str, request: Request) -> APIEnvelope:
    identity = resolve_request_identity(request)
    project = request.app.state.store.get_project(
        project_id,
        owner_id=identity.user_id,
        guest_session_id=identity.guest_session_id,
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return APIEnvelope(data=project)


@router.post("/{project_id}/runs", response_model=APIEnvelope, status_code=status.HTTP_201_CREATED)
def create_run(
    project_id: str,
    request: Request,
    payload: RunCreate | None = None,
) -> APIEnvelope:
    identity = resolve_request_identity(request)
    project = request.app.state.store.get_project(
        project_id,
        owner_id=identity.user_id,
        guest_session_id=identity.guest_session_id,
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    run = request.app.state.store.create_run(
        project_id,
        request.app.state.config.browser_use_model,
        repo_build_requested=bool(project.repo_url),
        source_review_requested=bool(
            project.repo_url and request.app.state.config.source_review_enabled
        ),
        custom_audience=(payload.custom_audience.strip() if payload and payload.custom_audience else None),
    )
    return APIEnvelope(data=run)


@router.get("/{project_id}/runs", response_model=APIEnvelope)
def list_runs(project_id: str, request: Request) -> APIEnvelope:
    identity = resolve_request_identity(request)
    project = request.app.state.store.get_project(
        project_id,
        owner_id=identity.user_id,
        guest_session_id=identity.guest_session_id,
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return APIEnvelope(
        data=request.app.state.store.list_runs(
            project_id,
            owner_id=identity.user_id,
            guest_session_id=identity.guest_session_id,
        )
    )
