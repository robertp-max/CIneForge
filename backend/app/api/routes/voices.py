"""Voice configuration API routes (Storyboard Phase 1).

This module is owned by the voice workstream. Registration into the app router
is intentionally outside this ownership boundary.
"""
from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.voice import (
    GpuLeaseAcquireRequest,
    GpuLeaseHeartbeatRequest,
    GpuLeaseRead,
    PlanningAssetRead,
    PlanningAssetRegisterRequest,
    ProviderEvidenceRead,
    VoiceApproveRequest,
    VoiceApproveResult,
    VoicePreviewJobRead,
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
from backend.app.services.planning_assets import (
    PlanningAssetError,
    get_planning_asset,
    register_planning_asset,
)
from backend.app.services.runtime.discovery import discover_all_voice_providers
from backend.app.services.runtime.gpu_leases import (
    GpuLeaseError,
    acquire_lease,
    heartbeat_lease,
    release_lease,
)
from backend.app.services.routing.voice_routing import recommend_voice_routing
from backend.app.services.voice_design.service import (
    VoiceDesignError,
    VoiceDesignService,
    select_preview,
)
from backend.app.workers.voice_preview import (
    get_preview_job,
    list_previews,
    run_voice_preview_job,
)

router = APIRouter(prefix="/voices", tags=["voices"])


def _http_error(error: Exception, *, not_found: bool = False) -> HTTPException:
    code = status.HTTP_404_NOT_FOUND if not_found else status.HTTP_422_UNPROCESSABLE_ENTITY
    if isinstance(error, GpuLeaseError):
        code = status.HTTP_409_CONFLICT
    return HTTPException(status_code=code, detail=str(error))


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
            details=item.details,
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
    response_model=VoicePreviewJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_preview(
    voice_profile_id: UUID,
    payload: VoicePreviewRequest,
    db: Session = Depends(get_db),
):
    """Explicit preview only. Acquires a shared GPU lease with video work."""
    try:
        # Prefer configured storage root when available without editing config module.
        storage_root: Path = Path("./storage")
        try:
            from backend.app.core.config import get_settings

            storage_root = Path(get_settings().storage_root)
        except Exception:
            pass
        return run_voice_preview_job(
            db,
            voice_profile_id,
            payload,
            storage_root=storage_root,
        )
    except VoiceDesignError as error:
        raise _http_error(error, not_found="not found" in str(error).lower()) from error
    except ValueError as error:
        raise _http_error(error) from error


@router.get("/preview-jobs/{job_id}", response_model=VoicePreviewJobRead)
def get_preview_job_status(job_id: str):
    job = get_preview_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Preview job {job_id} not found.")
    return job.to_read()


@router.get("/profiles/{voice_profile_id}/previews", response_model=list[VoicePreviewRead])
def list_profile_previews(voice_profile_id: UUID, db: Session = Depends(get_db)):
    try:
        return list_previews(db, voice_profile_id)
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


@router.post(
    "/planning-assets",
    response_model=PlanningAssetRead,
    status_code=status.HTTP_201_CREATED,
)
def create_planning_asset(payload: PlanningAssetRegisterRequest, db: Session = Depends(get_db)):
    try:
        return register_planning_asset(db, payload)
    except (PlanningAssetError, ValueError) as error:
        raise _http_error(error) from error


@router.get("/planning-assets/{asset_id}", response_model=PlanningAssetRead)
def read_planning_asset(asset_id: UUID, db: Session = Depends(get_db)):
    try:
        return get_planning_asset(db, asset_id)
    except PlanningAssetError as error:
        raise _http_error(error, not_found=True) from error


@router.post("/gpu-leases", response_model=GpuLeaseRead, status_code=status.HTTP_201_CREATED)
def create_gpu_lease(payload: GpuLeaseAcquireRequest, db: Session = Depends(get_db)):
    try:
        return acquire_lease(db, payload)
    except GpuLeaseError as error:
        raise _http_error(error) from error


@router.post("/gpu-leases/{lease_id}/heartbeat", response_model=GpuLeaseRead)
def lease_heartbeat(
    lease_id: UUID,
    payload: GpuLeaseHeartbeatRequest,
    db: Session = Depends(get_db),
):
    try:
        return heartbeat_lease(db, lease_id, extend_seconds=payload.extend_seconds)
    except GpuLeaseError as error:
        raise _http_error(error, not_found="not found" in str(error).lower()) from error


@router.post("/gpu-leases/{lease_id}/release", response_model=GpuLeaseRead)
def lease_release(lease_id: UUID, db: Session = Depends(get_db)):
    try:
        return release_lease(db, lease_id)
    except GpuLeaseError as error:
        raise _http_error(error, not_found=True) from error
