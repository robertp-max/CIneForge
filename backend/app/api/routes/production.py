"""Seven-phase production contract routes; Phase 1 is the only executable phase here."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.production import (
    PhaseOneGenerationInput,
    PhaseOneMutationResponse,
    PhaseOneRevisionRequest,
    ProductionPipelineRead,
)
from backend.app.services import production_phases


router = APIRouter(prefix="/production", tags=["production"])


def _error(exc: production_phases.ProductionPhaseError) -> HTTPException:
    if isinstance(exc, production_phases.ProductionPhaseConflictError):
        code = status.HTTP_409_CONFLICT
    elif str(exc) == "Story not found.":
        code = status.HTTP_404_NOT_FOUND
    else:
        code = status.HTTP_422_UNPROCESSABLE_ENTITY
    return HTTPException(status_code=code, detail=str(exc))


@router.get("/stories/{story_id}", response_model=ProductionPipelineRead)
def get_production_pipeline(
    story_id: UUID, db: Session = Depends(get_db)
) -> ProductionPipelineRead:
    try:
        return production_phases.get_pipeline(db, story_id)
    except production_phases.ProductionPhaseError as exc:
        raise _error(exc) from exc


@router.post(
    "/stories/{story_id}/phases/1/generate",
    response_model=PhaseOneMutationResponse,
)
def generate_phase_one(
    story_id: UUID,
    payload: PhaseOneGenerationInput,
    db: Session = Depends(get_db),
) -> PhaseOneMutationResponse:
    try:
        return production_phases.generate_phase_one(db, story_id, payload)
    except production_phases.ProductionPhaseError as exc:
        db.rollback()
        raise _error(exc) from exc


@router.put(
    "/stories/{story_id}/phases/1",
    response_model=PhaseOneMutationResponse,
)
def revise_phase_one(
    story_id: UUID,
    payload: PhaseOneRevisionRequest,
    db: Session = Depends(get_db),
) -> PhaseOneMutationResponse:
    try:
        return production_phases.revise_phase_one(db, story_id, payload)
    except production_phases.ProductionPhaseError as exc:
        db.rollback()
        raise _error(exc) from exc
