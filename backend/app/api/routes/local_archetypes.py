"""DB-free local archetype catalog routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from backend.app.schemas.local_archetypes import LocalArchetype, LocalArchetypeCatalog
from backend.app.services.local_archetypes import LocalArchetypeCatalogService


router = APIRouter(prefix="/local-archetypes", tags=["local-archetypes"])


def _service() -> LocalArchetypeCatalogService:
    return LocalArchetypeCatalogService()


@router.get("/catalog", response_model=LocalArchetypeCatalog)
def get_local_archetype_catalog() -> LocalArchetypeCatalog:
    try:
        return _service().load()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Configured local archetype catalog not found: {exc.filename}",
        ) from exc


@router.get("", response_model=list[LocalArchetype])
def list_local_archetypes(modality: str | None = Query(default=None)) -> list[LocalArchetype]:
    try:
        return _service().list_archetypes(modality=modality)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Configured local archetype catalog not found: {exc.filename}",
        ) from exc


@router.get("/{archetype_id}", response_model=LocalArchetype)
def get_local_archetype(archetype_id: str) -> LocalArchetype:
    try:
        archetype = _service().get_archetype(archetype_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Configured local archetype catalog not found: {exc.filename}",
        ) from exc
    if archetype is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local archetype not found.")
    return archetype
