"""Local file-backed post-production plan manifests.

These endpoints create and inspect offline CF-POST-01 manifests and expose
read-only access to already-persisted generic recipe command manifests. They do
not execute FFmpeg and do not expose a command-submission API.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from backend.app.core.config import get_settings
from backend.app.core.errors import ValidationError
from backend.app.schemas.post_production import (
    PostProductionAssemblyPlanCreate,
    PostProductionPlanManifest,
    PostProductionRecipeCommandManifest,
)
from backend.app.services.post_production_manifest import PostProductionPlanStore


router = APIRouter(prefix="/local-post-production", tags=["local-post-production"])


def _store() -> PostProductionPlanStore:
    return PostProductionPlanStore(get_settings())


@router.post("/plans", response_model=PostProductionPlanManifest)
def create_post_production_plan_manifest(
    request: PostProductionAssemblyPlanCreate,
) -> PostProductionPlanManifest:
    try:
        return _store().create_from_request(request)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/plans", response_model=list[PostProductionPlanManifest])
def list_post_production_plan_manifests(
    limit: int = Query(default=25, ge=1, le=100),
) -> list[PostProductionPlanManifest]:
    return _store().list(limit=limit)


@router.get("/plans/{plan_id}", response_model=PostProductionPlanManifest)
def get_post_production_plan_manifest(plan_id: UUID) -> PostProductionPlanManifest:
    return _store().get(plan_id)


@router.get("/recipe-commands", response_model=list[PostProductionRecipeCommandManifest])
def list_post_production_recipe_command_manifests(
    limit: int = Query(default=25, ge=1, le=100),
) -> list[PostProductionRecipeCommandManifest]:
    return _store().list_recipe_commands(limit=limit)


@router.get("/recipe-commands/{plan_id}", response_model=PostProductionRecipeCommandManifest)
def get_post_production_recipe_command_manifest(plan_id: UUID) -> PostProductionRecipeCommandManifest:
    return _store().get_recipe_command(plan_id)
