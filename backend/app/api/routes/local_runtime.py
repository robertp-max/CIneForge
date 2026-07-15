"""DB-free local runtime catalog and output policy routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from backend.app.core.config import get_settings
from backend.app.schemas.local_runtime import LocalRuntimeCatalog, OutputPolicy
from backend.app.schemas.local_runtime_evidence import LocalRuntimeEvidence
from backend.app.services.local_runtime import local_runtime_catalog, output_policy
from backend.app.services.local_runtime_evidence import LocalRuntimeEvidenceService


router = APIRouter(prefix="/local-runtime", tags=["local-runtime"])


@router.get("/catalog", response_model=LocalRuntimeCatalog)
def get_local_runtime_catalog() -> LocalRuntimeCatalog:
    return local_runtime_catalog(get_settings())


@router.get("/output-policy", response_model=OutputPolicy)
def get_output_policy() -> OutputPolicy:
    return output_policy(get_settings())


@router.get("/evidence", response_model=list[LocalRuntimeEvidence])
def list_local_runtime_evidence() -> list[LocalRuntimeEvidence]:
    return LocalRuntimeEvidenceService(get_settings()).list_evidence()


@router.get("/evidence/cf-vid-01-smoke", response_model=LocalRuntimeEvidence)
def get_cf_vid01_smoke_evidence() -> LocalRuntimeEvidence:
    try:
        return LocalRuntimeEvidenceService(get_settings()).get_cf_vid01_smoke()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Local runtime evidence not found: {exc.filename}",
        ) from exc
