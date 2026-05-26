from uuid import UUID

from fastapi import APIRouter

from backend.app.core.errors import not_found
from backend.app.schemas.api import ProjectCreate, ProjectRead, StubStore


router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=201)
def create_project(payload: ProjectCreate) -> ProjectRead:
    return StubStore.create_project(payload)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: UUID) -> ProjectRead:
    item = StubStore.projects.get(project_id)
    if item is None:
        raise not_found("Project not found. DB persistence wiring is scheduled after Sprint 1A foundation.")
    return item

