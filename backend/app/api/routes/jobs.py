from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.errors import not_found
from backend.app.db.base import ComfyJob, QueueStatus
from backend.app.db.session import get_db
from backend.app.schemas.api import JobRead


router = APIRouter(prefix="/jobs", tags=["jobs"])


def job_to_response(job: ComfyJob) -> JobRead:
    status = job.status.value if isinstance(job.status, QueueStatus) else str(job.status)
    return JobRead(
        id=job.id,
        status=status,
        workflow_run_id=job.workflow_run_id,
        comfy_prompt_id=job.prompt_id,
        error_message=job.error_message,
        detail="Job read from database.",
    )


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: UUID, db: Session = Depends(get_db)) -> JobRead:
    job = db.get(ComfyJob, job_id)
    if job is None:
        raise not_found("Job not found.")
    return job_to_response(job)
