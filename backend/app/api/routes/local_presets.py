"""DB-free local preset catalog routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from backend.app.schemas.local_presets import LocalPreset, LocalPresetCatalog, QualityProfile
from backend.app.schemas.local_readiness import LocalPresetReadinessRecord, LocalPresetReadinessReport
from backend.app.services.local_presets import LocalPresetCatalogService
from backend.app.services.local_readiness import LocalReadinessService


router = APIRouter(prefix="/local-presets", tags=["local-presets"])


def _service() -> LocalPresetCatalogService:
    return LocalPresetCatalogService()


def _readiness_service() -> LocalReadinessService:
    return LocalReadinessService()


@router.get("/catalog", response_model=LocalPresetCatalog)
def get_local_preset_catalog() -> LocalPresetCatalog:
    try:
        return _service().load()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Configured local preset catalog not found: {exc.filename}",
        ) from exc


@router.get("", response_model=list[LocalPreset])
def list_local_presets(
    quality_profile: QualityProfile | None = Query(default=None),
) -> list[LocalPreset]:
    try:
        return _service().list_presets(quality_profile=quality_profile)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Configured local preset catalog not found: {exc.filename}",
        ) from exc


@router.get("/readiness", response_model=LocalPresetReadinessReport)
def get_local_preset_readiness() -> LocalPresetReadinessReport:
    try:
        return _readiness_service().preset_report()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Configured local preset catalog not found: {exc.filename}",
        ) from exc


@router.get("/{preset_id}/readiness", response_model=LocalPresetReadinessRecord)
def get_local_preset_readiness_by_id(preset_id: str) -> LocalPresetReadinessRecord:
    try:
        readiness = _readiness_service().get_preset_readiness(preset_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Configured local preset catalog not found: {exc.filename}",
        ) from exc
    if readiness is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local preset not found.")
    return readiness


@router.get("/{preset_id}", response_model=LocalPreset)
def get_local_preset(preset_id: str) -> LocalPreset:
    try:
        preset = _service().get_preset(preset_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Configured local preset catalog not found: {exc.filename}",
        ) from exc
    if preset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local preset not found.")
    return preset
