"""Resolve local asset IDs for generation requests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.db.base import LocalRuntimeAsset
from backend.app.services.local_assets.catalog import resolve_asset_id


class AssetResolutionError(Exception):
    """Raised when a selected local asset cannot be used at runtime."""


@dataclass(frozen=True)
class ResolvedLora:
    asset_id: UUID
    selector_value: str
    file_path: str
    strength_model: float
    strength_clip: float
    name: str


@dataclass(frozen=True)
class ResolvedGenerationAssets:
    checkpoint: LocalRuntimeAsset | None
    workflow: LocalRuntimeAsset | None
    loras: list[ResolvedLora]


def resolve_generation_assets(
    db: Session,
    *,
    checkpoint_asset_id: UUID | None = None,
    workflow_asset_id: UUID | None = None,
    loras: list[dict] | None = None,
) -> ResolvedGenerationAssets:
    checkpoint = None
    if checkpoint_asset_id is not None:
        checkpoint = resolve_asset_id(db, checkpoint_asset_id)
        if checkpoint is None:
            raise AssetResolutionError(f"Checkpoint asset not found or missing: {checkpoint_asset_id}")
        if checkpoint.asset_type != "checkpoint":
            raise AssetResolutionError(
                f"Asset {checkpoint_asset_id} is type {checkpoint.asset_type}, expected checkpoint"
            )
        if not Path(checkpoint.file_path).is_file():
            raise AssetResolutionError(f"Checkpoint file missing on disk: {checkpoint.file_path}")

    workflow = None
    if workflow_asset_id is not None:
        workflow = resolve_asset_id(db, workflow_asset_id)
        if workflow is None:
            raise AssetResolutionError(f"Workflow asset not found or missing: {workflow_asset_id}")
        if not str(workflow.asset_type).startswith("workflow"):
            raise AssetResolutionError(
                f"Asset {workflow_asset_id} is type {workflow.asset_type}, expected workflow_*"
            )
        if not Path(workflow.file_path).is_file():
            raise AssetResolutionError(f"Workflow file missing on disk: {workflow.file_path}")

    resolved_loras: list[ResolvedLora] = []
    for entry in loras or []:
        aid = entry.get("asset_id")
        if aid is None:
            continue
        if not isinstance(aid, UUID):
            aid = UUID(str(aid))
        row = resolve_asset_id(db, aid)
        if row is None:
            raise AssetResolutionError(f"LoRA asset not found or missing: {aid}")
        if row.asset_type != "lora":
            raise AssetResolutionError(f"Asset {aid} is type {row.asset_type}, expected lora")
        if not Path(row.file_path).is_file():
            raise AssetResolutionError(f"LoRA file missing on disk: {row.file_path}")
        sm = float(entry.get("strength_model", 1.0))
        sc = float(entry.get("strength_clip", entry.get("strength_model", 1.0)))
        resolved_loras.append(
            ResolvedLora(
                asset_id=row.id,
                selector_value=row.selector_value,
                file_path=row.file_path,
                strength_model=sm,
                strength_clip=sc,
                name=row.name,
            )
        )

    return ResolvedGenerationAssets(
        checkpoint=checkpoint,
        workflow=workflow,
        loras=resolved_loras,
    )


def as_provenance(resolved: ResolvedGenerationAssets) -> dict:
    return {
        "checkpoint": (
            {
                "asset_id": str(resolved.checkpoint.id),
                "selector_value": resolved.checkpoint.selector_value,
                "file_path": resolved.checkpoint.file_path,
                "name": resolved.checkpoint.name,
            }
            if resolved.checkpoint
            else None
        ),
        "workflow": (
            {
                "asset_id": str(resolved.workflow.id),
                "selector_value": resolved.workflow.selector_value,
                "file_path": resolved.workflow.file_path,
                "name": resolved.workflow.name,
            }
            if resolved.workflow
            else None
        ),
        "loras": [
            {
                "asset_id": str(x.asset_id),
                "selector_value": x.selector_value,
                "file_path": x.file_path,
                "name": x.name,
                "strength_model": x.strength_model,
                "strength_clip": x.strength_clip,
            }
            for x in resolved.loras
        ],
    }
