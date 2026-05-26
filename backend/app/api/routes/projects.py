from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.errors import not_found
from backend.app.db.base import Project
from backend.app.db.session import get_db
from backend.app.schemas.api import ProjectCreate, ProjectRead


router = APIRouter(prefix="/projects", tags=["projects"])


def project_to_response(project: Project) -> ProjectRead:
    return ProjectRead(
        id=project.id,
        name=project.name,
        description=project.description,
        created_at=project.created_at,
        persistence="db",
    )


@router.post("", response_model=ProjectRead, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> ProjectRead:
    project = Project(name=payload.name, description=payload.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project_to_response(project)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: UUID, db: Session = Depends(get_db)) -> ProjectRead:
    project = db.get(Project, project_id)
    if project is None:
        raise not_found("Project not found.")
    return project_to_response(project)
