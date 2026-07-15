"""DB-free local preset catalog routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from backend.app.schemas.local_presets import LocalPreset, LocalPresetCatalog, QualityProfile
from backend.app.services.local_presets import LocalPresetCatalogService


router = APIRouter(prefix="/local-presets", tags=["local-presets"])


def _service() -> LocalPresetCatalogService:
    return LocalPresetCatalogService()


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
