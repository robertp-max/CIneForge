"""Local offline semantic generation handoff manifests.

These endpoints persist semantic generation intent and gate evidence only. They
are not a public prompt API and do not expose execution, submission, or runtime
control paths.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.errors import ValidationError
from backend.app.db.session import get_db
from backend.app.schemas.local_generation import (
    SemanticGenerationRequestManifest,
    StoryboardHandoffReport,
    StoryboardHandoffRequest,
)
from backend.app.schemas.production import SemanticGenerationRequest
from backend.app.services.local_generation import (
    SemanticGenerationRequestManifestStore,
    StoryboardSemanticHandoffService,
)


router = APIRouter(prefix="/local-generation", tags=["local-generation"])


def _store() -> SemanticGenerationRequestManifestStore:
    return SemanticGenerationRequestManifestStore(get_settings())


@router.post("/storyboard-handoffs", response_model=StoryboardHandoffReport)
def create_storyboard_handoff(
    request: StoryboardHandoffRequest,
    db: Session = Depends(get_db),
) -> StoryboardHandoffReport:
    try:
        return StoryboardSemanticHandoffService(_store()).create_handoff(db, request)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Configured local generation catalog/workflow file not found: {exc.filename}",
        ) from exc


@router.post("/semantic-requests", response_model=SemanticGenerationRequestManifest)
def create_semantic_generation_request_manifest(
    request: SemanticGenerationRequest,
) -> SemanticGenerationRequestManifest:
    try:
        return _store().create(request)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Configured local generation catalog/workflow file not found: {exc.filename}",
        ) from exc


@router.get("/semantic-requests", response_model=list[SemanticGenerationRequestManifest])
def list_semantic_generation_request_manifests(
    limit: int = Query(default=25, ge=1, le=100),
) -> list[SemanticGenerationRequestManifest]:
    return _store().list(limit=limit)


@router.get("/semantic-requests/{request_id}", response_model=SemanticGenerationRequestManifest)
def get_semantic_generation_request_manifest(request_id: UUID) -> SemanticGenerationRequestManifest:
    return _store().get(request_id)
