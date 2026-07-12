"""Voice configuration API routes (Storyboard Phase 1).

This module is owned by the voice workstream. Registration into the app router
is intentionally outside this ownership boundary.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.base import VoicePreview, VoiceProfile
from backend.app.db.session import get_db
from backend.app.schemas.voice import (
    PARLER_UNAVAILABLE_MESSAGE,
    ProviderEvidenceRead,
    VoiceApproveRequest,
    VoiceApproveResult,
    VoicePreviewRead,
    VoicePreviewRequest,
    VoicePreviewSelectRequest,
    VoiceProfileSetupCreate,
    VoiceProfileSetupRead,
    VoiceProfileSetupUpdate,
    VoiceProviderDiscoveryRead,
    VoiceRecipeCreate,
    VoiceRecipeRead,
    VoiceRoutingRecommendation,
    VoiceRoutingRequest,
)
from backend.app.services.runtime.discovery import (
    discover_all_voice_providers,
    discover_provider,
)
from backend.app.services.routing.voice_routing import recommend_voice_routing
from backend.app.services.voice_design.service import (
    VoiceDesignConflictError,
    VoiceDesignError,
    VoiceDesignService,
    resolve_preview_provider_name,
    select_preview,
)

router = APIRouter(prefix="/voices", tags=["voices"])

PREVIEW_WORKER_UNAVAILABLE_MESSAGE = (
    "Voice preview generation is unavailable until a durable preview worker is configured."
)
PREVIEW_JOB_TRACKING_UNAVAILABLE_MESSAGE = (
    "Voice preview job tracking is unavailable until a durable preview worker is configured."
)
PRIVATE_PROVIDER_DETAIL_KEYS = frozenset({"runtime_ref"})


def _http_error(error: Exception, *, not_found: bool = False) -> HTTPException:
    if isinstance(error, VoiceDesignConflictError):
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_404_NOT_FOUND if not_found else status.HTTP_422_UNPROCESSABLE_ENTITY
    return HTTPException(status_code=code, detail=str(error))


def _public_provider_details(details: dict) -> dict:
    """Keep readiness evidence while withholding local runtime locations."""
    return {
        key: value
        for key, value in details.items()
        if str(key).strip().lower() not in PRIVATE_PROVIDER_DETAIL_KEYS
    }


def _preview_unavailable(
    profile: VoiceProfile,
    requested_provider: str | None,
) -> HTTPException:
    """Return a truthful response without invoking a provider or worker.

    Parler remains optional. Discovery reads only installation/approval evidence;
    when that evidence is absent its required message takes precedence over the
    generic durable-worker message.
    """
    provider_name = resolve_preview_provider_name(profile, requested_provider)
    if provider_name.strip().lower() in {
        "parler",
        "parler_local",
        "parler-tts",
        "parler_tts",
    }:
        evidence = discover_provider("parler")
        if not evidence.available:
            return HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=PARLER_UNAVAILABLE_MESSAGE,
            )
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=PREVIEW_WORKER_UNAVAILABLE_MESSAGE,
    )


@router.get("/providers/discovery", response_model=VoiceProviderDiscoveryRead)
def discover_providers() -> VoiceProviderDiscoveryRead:
    """Factual provider discovery without loading models or downloading."""
    evidences = discover_all_voice_providers()
    providers = [
        ProviderEvidenceRead(
            provider=item.provider,
            capability="voice",
            status=item.status,  # type: ignore[arg-type]
            evidence_level=item.evidence_level,
            evidence_source=item.evidence_source,
            details=_public_provider_details(item.details),
            message=item.message,
            checked_at=item.checked_at,
        )
        for item in evidences
    ]
    return VoiceProviderDiscoveryRead(
        providers=providers,
        notes=[
            "Discovery reads configuration/module evidence only.",
            "Models are never loaded and packages are never installed during discovery.",
            "Previews are explicit only and are not triggered by discovery.",
        ],
    )


@router.post(
    "/stories/{story_id}/profiles",
    response_model=VoiceProfileSetupRead,
    status_code=status.HTTP_201_CREATED,
)
def create_profile(
    story_id: UUID,
    payload: VoiceProfileSetupCreate,
    db: Session = Depends(get_db),
):
    try:
        return VoiceDesignService(db).create_profile(story_id, payload)
    except VoiceDesignError as error:
        raise _http_error(error, not_found="not found" in str(error).lower()) from error
    except ValueError as error:
        raise _http_error(error) from error


@router.get("/stories/{story_id}/profiles", response_model=list[VoiceProfileSetupRead])
def list_profiles(story_id: UUID, db: Session = Depends(get_db)):
    try:
        return VoiceDesignService(db).list_profiles(story_id)
    except VoiceDesignError as error:
        raise _http_error(error, not_found=True) from error


@router.get("/profiles/{voice_profile_id}", response_model=VoiceProfileSetupRead)
def get_profile(voice_profile_id: UUID, db: Session = Depends(get_db)):
    try:
        return VoiceDesignService(db).get_profile(voice_profile_id)
    except VoiceDesignError as error:
        raise _http_error(error, not_found=True) from error


@router.patch("/profiles/{voice_profile_id}", response_model=VoiceProfileSetupRead)
def patch_profile(
    voice_profile_id: UUID,
    payload: VoiceProfileSetupUpdate,
    db: Session = Depends(get_db),
):
    try:
        return VoiceDesignService(db).update_profile(voice_profile_id, payload)
    except VoiceDesignError as error:
        raise _http_error(error, not_found="not found" in str(error).lower()) from error
    except ValueError as error:
        raise _http_error(error) from error


@router.delete("/profiles/{voice_profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_profile(
    voice_profile_id: UUID,
    reason: str | None = Query(default=None, max_length=500),
    db: Session = Depends(get_db),
) -> Response:
    try:
        VoiceDesignService(db).archive_profile(voice_profile_id, reason=reason)
    except VoiceDesignError as error:
        raise _http_error(error, not_found="not found" in str(error).lower()) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/profiles/{voice_profile_id}/recipes",
    response_model=VoiceRecipeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_recipe(
    voice_profile_id: UUID,
    payload: VoiceRecipeCreate,
    db: Session = Depends(get_db),
):
    try:
        return VoiceDesignService(db).create_recipe(voice_profile_id, payload)
    except VoiceDesignError as error:
        raise _http_error(error, not_found="not found" in str(error).lower()) from error
    except ValueError as error:
        raise _http_error(error) from error


@router.get("/profiles/{voice_profile_id}/recipes", response_model=list[VoiceRecipeRead])
def list_recipes(voice_profile_id: UUID, db: Session = Depends(get_db)):
    try:
        return VoiceDesignService(db).list_recipes(voice_profile_id)
    except VoiceDesignError as error:
        raise _http_error(error, not_found=True) from error


@router.post(
    "/profiles/{voice_profile_id}/previews",
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Preview execution requires a durable worker and is currently unavailable."
        }
    },
)
def request_preview(
    voice_profile_id: UUID,
    payload: VoicePreviewRequest,
    db: Session = Depends(get_db),
) -> None:
    """Reject preview execution until a durable, isolated worker is available.

    This public request never calls a provider, acquires a GPU lease, writes an
    artifact, submits Comfy work, or invokes FFmpeg in the API process.
    """
    try:
        profile = VoiceDesignService(db).get_profile(voice_profile_id)
    except VoiceDesignError as error:
        raise _http_error(error, not_found="not found" in str(error).lower()) from error
    raise _preview_unavailable(profile, payload.provider)


@router.get(
    "/preview-jobs/{job_id}",
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Durable preview-job tracking is currently unavailable."
        }
    },
)
def get_preview_job_status(job_id: str) -> None:
    del job_id
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=PREVIEW_JOB_TRACKING_UNAVAILABLE_MESSAGE,
    )


@router.get("/profiles/{voice_profile_id}/previews", response_model=list[VoicePreviewRead])
def list_profile_previews(voice_profile_id: UUID, db: Session = Depends(get_db)):
    try:
        VoiceDesignService(db).get_profile(voice_profile_id)
        stmt = (
            select(VoicePreview)
            .where(VoicePreview.voice_profile_id == voice_profile_id)
            .order_by(VoicePreview.created_at.desc())
        )
        return list(db.scalars(stmt))
    except VoiceDesignError as error:
        raise _http_error(error, not_found=True) from error


@router.post("/previews/{preview_id}/select", response_model=VoicePreviewRead)
def select_preview_route(
    preview_id: UUID,
    payload: VoicePreviewSelectRequest,
    db: Session = Depends(get_db),
):
    try:
        return select_preview(db, preview_id, selected=payload.selected)
    except VoiceDesignError as error:
        raise _http_error(error, not_found="not found" in str(error).lower()) from error


@router.post("/profiles/{voice_profile_id}/approve", response_model=VoiceApproveResult)
def approve_profile(
    voice_profile_id: UUID,
    payload: VoiceApproveRequest,
    db: Session = Depends(get_db),
):
    try:
        return VoiceDesignService(db).approve(voice_profile_id, payload)
    except VoiceDesignError as error:
        raise _http_error(error, not_found="not found" in str(error).lower()) from error


@router.post("/routing/recommend", response_model=VoiceRoutingRecommendation)
def routing_recommend(payload: VoiceRoutingRequest, db: Session = Depends(get_db)):
    return recommend_voice_routing(db, payload)
