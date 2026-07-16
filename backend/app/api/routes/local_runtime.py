"""DB-free local runtime catalog and output policy routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from backend.app.core.config import get_settings
from backend.app.core.errors import ValidationError
from backend.app.schemas.benchmark_ladder import BenchmarkLadderManifest
from backend.app.schemas.ffmpeg_recipes import FFmpegCommandTemplateRecord
from backend.app.schemas.local_mvp_readiness import LocalMVPReadinessReport
from backend.app.schemas.local_public_readiness import LocalPublicReadinessReport
from backend.app.schemas.local_runtime import LocalRuntimeCatalog, OutputPolicy
from backend.app.schemas.local_safe_boundary import LocalSafeBoundaryReport
from backend.app.schemas.local_runtime_evidence import LocalRuntimeEvidence
from backend.app.schemas.local_runtime_m4 import M4HardwarePreflightReport
from backend.app.services.ffmpeg.service import ffmpeg_command_template_catalog
from backend.app.services.local_mvp_readiness import LocalMVPReadinessService
from backend.app.services.local_public_readiness import LocalPublicReadinessService
from backend.app.services.local_runtime import local_runtime_catalog, output_policy
from backend.app.services.local_safe_boundary import LocalSafeBoundaryService
from backend.app.services.local_runtime_evidence import LocalRuntimeEvidenceService
from backend.app.services.local_runtime_m4 import M4HardwarePreflightService
from backend.app.services.benchmarks.ladder import BenchmarkLadderService


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


@router.get("/m4-preflight", response_model=M4HardwarePreflightReport)
def get_m4_hardware_preflight() -> M4HardwarePreflightReport:
    return M4HardwarePreflightService(get_settings()).report()


@router.get("/local-mvp-readiness", response_model=LocalMVPReadinessReport)
def get_local_mvp_readiness() -> LocalMVPReadinessReport:
    return LocalMVPReadinessService(get_settings()).report()


@router.get("/public-readiness", response_model=LocalPublicReadinessReport)
def get_local_public_readiness() -> LocalPublicReadinessReport:
    return LocalPublicReadinessService(get_settings()).report()


@router.get("/safe-boundary", response_model=LocalSafeBoundaryReport)
def get_local_safe_boundary() -> LocalSafeBoundaryReport:
    return LocalSafeBoundaryService().report()


@router.get("/ffmpeg-recipes", response_model=list[FFmpegCommandTemplateRecord])
def list_ffmpeg_recipes() -> list[FFmpegCommandTemplateRecord]:
    return ffmpeg_command_template_catalog()


@router.get("/m4-ladder", response_model=BenchmarkLadderManifest)
def get_m4_benchmark_ladder() -> BenchmarkLadderManifest:
    try:
        return BenchmarkLadderService(get_settings()).get_m4_ladder()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"M4 benchmark ladder manifest not found: {exc.filename}",
        ) from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.get("/evidence/cf-vid-01-smoke", response_model=LocalRuntimeEvidence)
def get_cf_vid01_smoke_evidence() -> LocalRuntimeEvidence:
    try:
        return LocalRuntimeEvidenceService(get_settings()).get_cf_vid01_smoke()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Local runtime evidence not found: {exc.filename}",
        ) from exc
