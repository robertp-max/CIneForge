"""Project storyboard settings routes (Phase 1)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.storyboard_settings import (
    ProjectStoryboardSettingsRead,
    ProjectStoryboardSettingsUpdate,
)
from backend.app.services import storyboard_settings as service


router = APIRouter(prefix="/projects", tags=["storyboard-settings"])


@router.get(
    "/{project_id}/storyboard-settings",
    response_model=ProjectStoryboardSettingsRead,
)
def get_project_storyboard_settings(
    project_id: UUID, db: Session = Depends(get_db)
) -> ProjectStoryboardSettingsRead:
    try:
        return service.get_settings(db, project_id)
    except service.StoryboardSettingsError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.put(
    "/{project_id}/storyboard-settings",
    response_model=ProjectStoryboardSettingsRead,
)
def put_project_storyboard_settings(
    project_id: UUID,
    payload: ProjectStoryboardSettingsUpdate,
    db: Session = Depends(get_db),
) -> ProjectStoryboardSettingsRead:
    try:
        return service.put_settings(db, project_id, payload)
    except service.StoryboardSettingsConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except service.StoryboardSettingsError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
