from uuid import UUID

from fastapi import APIRouter

from backend.app.core.errors import not_found
from backend.app.schemas.api import JobRead, StubStore


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: UUID) -> JobRead:
    item = StubStore.jobs.get(job_id)
    if item is None:
        raise not_found("Job not found. Queue persistence is scaffolded but no worker runs in Sprint 1A.")
    return item

