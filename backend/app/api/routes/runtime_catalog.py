"""Runtime model/workflow catalog API.

Registered DB catalog endpoints never probe ComfyUI/GPU/installers.
Local-asset endpoints read the filesystem catalog registry and can trigger sync.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.db.session import get_db
from backend.app.schemas.runtime_catalog import (
    LocalAssetSyncRequest,
    LocalAssetSyncResponse,
    LocalAssetsSummary,
    LocalRuntimeAssetItem,
    LoraCatalogItem,
    ModelCatalogItem,
    ModelVariantCatalogItem,
    QuantizationCatalogItem,
    RuntimeCatalogResponse,
    RuntimeCatalogSummary,
    WorkflowCandidateRegistryResponse,
    WorkflowTemplateCatalogItem,
)
from backend.app.services import runtime_catalog as service
from backend.app.services.local_assets import catalog as local_catalog
from backend.app.services.local_assets.sync import sync_local_comfy_assets
from backend.app.services.workflows import candidate_catalog as workflow_candidates


router = APIRouter(prefix="/runtime-catalog", tags=["runtime-catalog"])


@router.get("", response_model=RuntimeCatalogResponse)
def get_full_catalog(db: Session = Depends(get_db)) -> RuntimeCatalogResponse:
    payload = service.full_catalog(db)
    return RuntimeCatalogResponse(
        summary=RuntimeCatalogSummary.model_validate(payload["summary"]),
        models=[ModelCatalogItem.model_validate(item) for item in payload["models"]],
        model_variants=[
            ModelVariantCatalogItem.model_validate(item) for item in payload["model_variants"]
        ],
        workflow_templates=[
            WorkflowTemplateCatalogItem.model_validate(item)
            for item in payload["workflow_templates"]
        ],
        quantizations=[
            QuantizationCatalogItem.model_validate(item) for item in payload["quantizations"]
        ],
        loras=[LoraCatalogItem.model_validate(item) for item in payload["loras"]],
    )


@router.get("/summary", response_model=RuntimeCatalogSummary)
def get_catalog_summary(db: Session = Depends(get_db)) -> RuntimeCatalogSummary:
    return RuntimeCatalogSummary.model_validate(service.catalog_summary(db))


@router.get("/models", response_model=list[ModelCatalogItem])
def list_models(db: Session = Depends(get_db)) -> list[ModelCatalogItem]:
    return [ModelCatalogItem.model_validate(item) for item in service.list_models(db)]


@router.get("/model-variants", response_model=list[ModelVariantCatalogItem])
def list_model_variants(
    model_id: UUID | None = None,
    db: Session = Depends(get_db),
) -> list[ModelVariantCatalogItem]:
    return [
        ModelVariantCatalogItem.model_validate(item)
        for item in service.list_model_variants(db, model_id=model_id)
    ]


@router.get("/model-variants/{variant_id}", response_model=ModelVariantCatalogItem)
def get_model_variant(
    variant_id: UUID,
    db: Session = Depends(get_db),
) -> ModelVariantCatalogItem:
    item = service.get_model_variant(db, variant_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model variant not found.")
    return ModelVariantCatalogItem.model_validate(item)


@router.get("/workflow-templates", response_model=list[WorkflowTemplateCatalogItem])
def list_workflow_templates(
    db: Session = Depends(get_db),
) -> list[WorkflowTemplateCatalogItem]:
    return [
        WorkflowTemplateCatalogItem.model_validate(item)
        for item in service.list_workflow_templates(db)
    ]


@router.get(
    "/workflow-candidates",
    response_model=WorkflowCandidateRegistryResponse,
)
def get_workflow_candidate_registry() -> WorkflowCandidateRegistryResponse:
    """Return the non-executing archetype/candidate/preset planning registry."""

    return WorkflowCandidateRegistryResponse.model_validate(
        workflow_candidates.catalog_document()
    )


@router.get(
    "/workflow-templates/{template_id}",
    response_model=WorkflowTemplateCatalogItem,
)
def get_workflow_template(
    template_id: UUID,
    db: Session = Depends(get_db),
) -> WorkflowTemplateCatalogItem:
    item = service.get_workflow_template(db, template_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow template not found."
        )
    return WorkflowTemplateCatalogItem.model_validate(item)


@router.get("/quantizations", response_model=list[QuantizationCatalogItem])
def list_quantizations(db: Session = Depends(get_db)) -> list[QuantizationCatalogItem]:
    return [
        QuantizationCatalogItem.model_validate(item) for item in service.list_quantizations(db)
    ]


@router.get("/loras", response_model=list[LoraCatalogItem])
def list_loras(db: Session = Depends(get_db)) -> list[LoraCatalogItem]:
    return [LoraCatalogItem.model_validate(item) for item in service.list_loras(db)]


# ---------------------------------------------------------------------------
# Local filesystem assets (presence-driven catalog)
# ---------------------------------------------------------------------------


@router.get("/local-assets", response_model=list[LocalRuntimeAssetItem])
def list_local_assets(
    asset_type: str | None = None,
    family: str | None = None,
    base: str | None = None,
    present: bool | None = Query(default=True),
    q: str | None = None,
    relative_prefix: str | None = None,
    duplicate_sha256: str | None = None,
    limit: int = Query(default=500, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[LocalRuntimeAssetItem]:
    items = local_catalog.list_local_assets(
        db,
        asset_type=asset_type,
        family=family,
        base=base,
        present=present,
        q=q,
        relative_prefix=relative_prefix,
        duplicate_sha256=duplicate_sha256,
        limit=limit,
        offset=offset,
    )
    return [LocalRuntimeAssetItem.model_validate(item) for item in items]


@router.get("/local-assets/summary", response_model=LocalAssetsSummary)
def get_local_assets_summary(db: Session = Depends(get_db)) -> LocalAssetsSummary:
    return LocalAssetsSummary.model_validate(local_catalog.local_assets_summary(db))


@router.get("/local-assets/{asset_id}", response_model=LocalRuntimeAssetItem)
def get_local_asset(
    asset_id: UUID,
    db: Session = Depends(get_db),
) -> LocalRuntimeAssetItem:
    item = local_catalog.get_local_asset(db, asset_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local asset not found.")
    return LocalRuntimeAssetItem.model_validate(item)


@router.get("/checkpoints", response_model=list[LocalRuntimeAssetItem])
def list_local_checkpoints(
    family: str | None = None,
    q: str | None = None,
    present: bool | None = Query(default=True),
    limit: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> list[LocalRuntimeAssetItem]:
    items = local_catalog.list_local_assets(
        db,
        asset_type="checkpoint",
        family=family,
        present=present,
        q=q,
        limit=limit,
    )
    return [LocalRuntimeAssetItem.model_validate(item) for item in items]


@router.get("/local-loras", response_model=list[LocalRuntimeAssetItem])
def list_local_loras(
    family: str | None = None,
    q: str | None = None,
    present: bool | None = Query(default=True),
    limit: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> list[LocalRuntimeAssetItem]:
    items = local_catalog.list_local_assets(
        db,
        asset_type="lora",
        family=family,
        present=present,
        q=q,
        limit=limit,
    )
    return [LocalRuntimeAssetItem.model_validate(item) for item in items]


@router.get("/local-workflows", response_model=list[LocalRuntimeAssetItem])
def list_local_workflows(
    family: str | None = None,
    q: str | None = None,
    present: bool | None = Query(default=True),
    limit: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> list[LocalRuntimeAssetItem]:
    items = local_catalog.list_local_assets(
        db,
        asset_type="workflow",
        family=family,
        present=present,
        q=q,
        limit=limit,
    )
    return [LocalRuntimeAssetItem.model_validate(item) for item in items]


@router.post("/sync", response_model=LocalAssetSyncResponse)
def sync_local_assets(
    body: LocalAssetSyncRequest | None = None,
    db: Session = Depends(get_db),
) -> LocalAssetSyncResponse:
    """Scan local ComfyUI directories and upsert the local asset registry.

    Never deletes or relocates files. Never treats unreviewed assets as hidden.
    """
    settings = get_settings()
    payload = body or LocalAssetSyncRequest()
    root = Path(payload.comfyui_root) if payload.comfyui_root else settings.comfyui_root
    try:
        summary = sync_local_comfy_assets(
            db,
            comfyui_root=root,
            compute_hash=not payload.skip_hash,
            hash_max_bytes=payload.hash_max_bytes,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return LocalAssetSyncResponse.model_validate(summary)
