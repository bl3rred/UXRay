from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.auth import resolve_request_identity
from app.schemas import APIEnvelope


router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/{run_id}", response_model=APIEnvelope)
def get_run(run_id: str, request: Request) -> APIEnvelope:
    identity = resolve_request_identity(request)
    run = request.app.state.store.get_run_detail(
        run_id,
        owner_id=identity.user_id,
        guest_session_id=identity.guest_session_id,
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return APIEnvelope(data=run)


@router.post("/{run_id}/retry-fetch", response_model=APIEnvelope)
def retry_fetch_review(run_id: str, request: Request) -> APIEnvelope:
    identity = resolve_request_identity(request)
    run = request.app.state.store.get_run_detail(
        run_id,
        owner_id=identity.user_id,
        guest_session_id=identity.guest_session_id,
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if not request.app.state.worker.schedule_fetch_retry(run_id):
        raise HTTPException(status_code=400, detail="Fetch review could not be retried for this run")
    refreshed = request.app.state.store.get_run_detail(
        run_id,
        owner_id=identity.user_id,
        guest_session_id=identity.guest_session_id,
    )
    return APIEnvelope(data=refreshed)
