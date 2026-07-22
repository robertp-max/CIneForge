"""Local post-production manifests and separately gated operator execution.

The ``/local-post-production`` router creates and inspects offline CF-POST-01
manifests. Explicit, default-off execution lives under the separate
``/operator-post-production`` namespace and never accepts a raw command.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.errors import ValidationError
from backend.app.db.session import get_db
from backend.app.schemas.post_production import (
    PostProductionAssemblyPlanCreate,
    PostProductionPlanManifest,
    PostProductionRecipeCommandManifest,
    PostProductionExecutionRequest,
)
from backend.app.services.ffmpeg.executor import FFmpegExecutionBlocked, GatedFFmpegExecutor
from backend.app.services.post_production_manifest import PostProductionPlanStore


router = APIRouter(prefix="/local-post-production", tags=["local-post-production"])
operator_router = APIRouter(prefix="/operator-post-production", tags=["operator-post-production"])


def _store() -> PostProductionPlanStore:
    return PostProductionPlanStore(get_settings())


@router.post("/plans", response_model=PostProductionPlanManifest)
def create_post_production_plan_manifest(
    request: PostProductionAssemblyPlanCreate,
) -> PostProductionPlanManifest:
    try:
        return _store().create_from_request(request)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.get("/plans", response_model=list[PostProductionPlanManifest])
def list_post_production_plan_manifests(
    limit: int = Query(default=25, ge=1, le=100),
) -> list[PostProductionPlanManifest]:
    return _store().list(limit=limit)


@router.get("/plans/{plan_id}", response_model=PostProductionPlanManifest)
def get_post_production_plan_manifest(plan_id: UUID) -> PostProductionPlanManifest:
    return _store().get(plan_id)


@operator_router.post("/plans/{plan_id}/execute", response_model=PostProductionPlanManifest)
def execute_post_production_plan(
    plan_id: UUID,
    request: PostProductionExecutionRequest,
    db: Session = Depends(get_db),
) -> PostProductionPlanManifest:
    try:
        store = _store()
        return GatedFFmpegExecutor(settings=get_settings(), store=store).execute_plan(
            db,
            plan_id,
            requested_by=request.requested_by,
        )
    except FFmpegExecutionBlocked as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (ValidationError, FileNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except (RuntimeError, TimeoutError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/recipe-commands", response_model=list[PostProductionRecipeCommandManifest])
def list_post_production_recipe_command_manifests(
    limit: int = Query(default=25, ge=1, le=100),
) -> list[PostProductionRecipeCommandManifest]:
    return _store().list_recipe_commands(limit=limit)


@router.get("/recipe-commands/{plan_id}", response_model=PostProductionRecipeCommandManifest)
def get_post_production_recipe_command_manifest(plan_id: UUID) -> PostProductionRecipeCommandManifest:
    return _store().get_recipe_command(plan_id)


@operator_router.post("/recipe-commands/{plan_id}/execute", response_model=PostProductionRecipeCommandManifest)
def execute_post_production_recipe_command(
    plan_id: UUID,
    request: PostProductionExecutionRequest,
    db: Session = Depends(get_db),
) -> PostProductionRecipeCommandManifest:
    try:
        store = _store()
        return GatedFFmpegExecutor(settings=get_settings(), store=store).execute_recipe(
            db,
            plan_id,
            requested_by=request.requested_by,
        )
    except FFmpegExecutionBlocked as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (ValidationError, FileNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except (RuntimeError, TimeoutError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
