"""Proposal review / reject / apply / diff API routes (Storyboard Phase 1).

Router is defined here only; wiring into the app main/router is intentionally
out of scope for this change set.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.proposals import (
    ProposalApplyRequest,
    ProposalApplyResult,
    ProposalCreateRequest,
    ProposalDiffResponse,
    ProposalRead,
    ProposalRejectRequest,
    ProposalReviewRequest,
    ProposalValidationResponse,
)
from backend.app.services import proposal_apply as apply_service
from backend.app.services import proposal_service as service


router = APIRouter(prefix="/proposal-review", tags=["proposal-review"])


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, service.ProposalNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, service.ProposalStateError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, service.ProposalServiceError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/validate", response_model=ProposalValidationResponse)
def validate_proposal(
    payload: ProposalCreateRequest,
    db: Session = Depends(get_db),
) -> ProposalValidationResponse:
    try:
        return service.validate_create_request(db, payload)
    except service.ProposalServiceError as exc:
        raise _http_error(exc) from exc


@router.post("", response_model=ProposalRead, status_code=status.HTTP_201_CREATED)
def create_proposal(
    payload: ProposalCreateRequest,
    db: Session = Depends(get_db),
) -> ProposalRead:
    try:
        record = service.create_proposal(db, payload)
        return ProposalRead.model_validate(record)
    except service.ProposalServiceError as exc:
        raise _http_error(exc) from exc


@router.get("/story/{story_id}", response_model=list[ProposalRead])
def list_story_proposals(story_id: UUID, db: Session = Depends(get_db)) -> list[ProposalRead]:
    records = service.list_proposals_for_story(db, story_id)
    return [ProposalRead.model_validate(item) for item in records]


@router.get("/{proposal_id}", response_model=ProposalRead)
def get_proposal(proposal_id: UUID, db: Session = Depends(get_db)) -> ProposalRead:
    try:
        return ProposalRead.model_validate(service.get_proposal(db, proposal_id))
    except service.ProposalServiceError as exc:
        raise _http_error(exc) from exc


@router.get("/{proposal_id}/diff", response_model=ProposalDiffResponse)
def get_proposal_diff(proposal_id: UUID, db: Session = Depends(get_db)) -> ProposalDiffResponse:
    try:
        return service.build_diff(db, proposal_id)
    except service.ProposalServiceError as exc:
        raise _http_error(exc) from exc


@router.post("/{proposal_id}/review", response_model=ProposalRead)
def review_proposal(
    proposal_id: UUID,
    payload: ProposalReviewRequest,
    db: Session = Depends(get_db),
) -> ProposalRead:
    try:
        return ProposalRead.model_validate(service.review_proposal(db, proposal_id, payload))
    except service.ProposalServiceError as exc:
        raise _http_error(exc) from exc


@router.post("/{proposal_id}/reject", response_model=ProposalRead)
def reject_proposal(
    proposal_id: UUID,
    payload: ProposalRejectRequest,
    db: Session = Depends(get_db),
) -> ProposalRead:
    try:
        return ProposalRead.model_validate(service.reject_proposal(db, proposal_id, payload))
    except service.ProposalServiceError as exc:
        raise _http_error(exc) from exc


@router.post("/{proposal_id}/apply", response_model=ProposalApplyResult)
def apply_proposal(
    proposal_id: UUID,
    payload: ProposalApplyRequest,
    db: Session = Depends(get_db),
) -> ProposalApplyResult:
    try:
        return apply_service.apply_proposal(db, proposal_id, payload)
    except service.ProposalServiceError as exc:
        raise _http_error(exc) from exc
