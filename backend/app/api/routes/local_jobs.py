"""Local file-backed job manifests.

These endpoints prepare local state and output folders only. They do not submit
prompts to ComfyUI and do not require a database.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from backend.app.core.config import get_settings
from backend.app.core.errors import ValidationError
from backend.app.schemas.local_jobs import LocalJobCreate, LocalJobManifest
from backend.app.services.local_jobs import LocalJobStore


router = APIRouter(prefix="/local-jobs", tags=["local-jobs"])


def _store() -> LocalJobStore:
    return LocalJobStore(get_settings())


@router.post("", response_model=LocalJobManifest)
def create_local_job_manifest(request: LocalJobCreate) -> LocalJobManifest:
    try:
        return _store().create(request)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Configured local workflow/catalog file not found: {exc.filename}",
        ) from exc


@router.get("", response_model=list[LocalJobManifest])
def list_local_job_manifests(limit: int = Query(default=25, ge=1, le=100)) -> list[LocalJobManifest]:
    return _store().list(limit=limit)


@router.get("/{job_id}", response_model=LocalJobManifest)
def get_local_job_manifest(job_id: UUID) -> LocalJobManifest:
    return _store().get(job_id)
