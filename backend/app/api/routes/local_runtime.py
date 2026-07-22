"""DB-free local runtime catalog and output policy routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from backend.app.core.config import get_settings
from backend.app.core.errors import ValidationError
from backend.app.schemas.benchmark_ladder import BenchmarkLadderManifest
from backend.app.schemas.ffmpeg_recipes import FFmpegCommandTemplateRecord
from backend.app.schemas.local_checkpoint_watchdog import LocalCheckpointWatchdogReport
from backend.app.schemas.local_mvp_readiness import LocalMVPReadinessReport
from backend.app.schemas.local_public_readiness import LocalPublicReadinessReport
from backend.app.schemas.local_runtime import LocalRuntimeCatalog, OutputPolicy
from backend.app.schemas.local_runtime_control import (
    LocalRuntimeActionRequest,
    LocalRuntimeActionResponse,
    LocalRuntimeProbeRequest,
    LocalRuntimeStatus,
)
from backend.app.schemas.local_safe_boundary import LocalSafeBoundaryReport
from backend.app.schemas.local_runtime_evidence import LocalRuntimeEvidence
from backend.app.schemas.local_runtime_m4 import M4HardwarePreflightReport
from backend.app.services.ffmpeg.service import ffmpeg_command_template_catalog
from backend.app.services.local_checkpoint_watchdog import LocalCheckpointWatchdogService
from backend.app.services.local_mvp_readiness import LocalMVPReadinessService
from backend.app.services.local_public_readiness import LocalPublicReadinessService
from backend.app.services.local_runtime import local_runtime_catalog, output_policy
from backend.app.services.local_safe_boundary import LocalSafeBoundaryService
from backend.app.services.local_runtime_evidence import LocalRuntimeEvidenceService
from backend.app.services.local_runtime_m4 import M4HardwarePreflightService
from backend.app.services.benchmarks.ladder import BenchmarkLadderService
from backend.app.services.comfy.runtime_manager import (
    ComfyRuntimeMutationBlocked,
    PinnedComfyRuntimeManager,
)


router = APIRouter(prefix="/local-runtime", tags=["local-runtime"])
operator_router = APIRouter(prefix="/operator-runtime", tags=["operator-runtime"])


def _runtime_manager() -> PinnedComfyRuntimeManager:
    return PinnedComfyRuntimeManager(get_settings())


def _runtime_status(*, probe: bool) -> LocalRuntimeStatus:
    payload = _runtime_manager().status(probe=probe).as_dict()
    return LocalRuntimeStatus(**payload, live_probe_performed=probe)


@router.get("/catalog", response_model=LocalRuntimeCatalog)
def get_local_runtime_catalog() -> LocalRuntimeCatalog:
    return local_runtime_catalog(get_settings())


@router.get("/live-status", response_model=LocalRuntimeStatus)
def get_local_runtime_live_status() -> LocalRuntimeStatus:
    """Return configuration/process ownership without making a network probe."""

    return _runtime_status(probe=False)


@operator_router.post("/probe", response_model=LocalRuntimeStatus)
def probe_local_runtime(_request: LocalRuntimeProbeRequest) -> LocalRuntimeStatus:
    return _runtime_status(probe=True)


def _runtime_action_error(exc: Exception) -> HTTPException:
    code = status.HTTP_409_CONFLICT if isinstance(exc, ComfyRuntimeMutationBlocked) else status.HTTP_422_UNPROCESSABLE_CONTENT
    return HTTPException(status_code=code, detail=str(exc))


@operator_router.post("/start", response_model=LocalRuntimeActionResponse)
def start_local_runtime(request: LocalRuntimeActionRequest) -> LocalRuntimeActionResponse:
    try:
        result = _runtime_manager().start(automatic=False)
    except Exception as exc:
        raise _runtime_action_error(exc) from exc
    return LocalRuntimeActionResponse(action="start", requested_by=request.requested_by, result=result)


@operator_router.post("/restart", response_model=LocalRuntimeActionResponse)
def restart_local_runtime(request: LocalRuntimeActionRequest) -> LocalRuntimeActionResponse:
    try:
        result = _runtime_manager().restart_pinned_runtime()
    except Exception as exc:
        raise _runtime_action_error(exc) from exc
    return LocalRuntimeActionResponse(action="restart", requested_by=request.requested_by, result=result)


@operator_router.post("/stop", response_model=LocalRuntimeActionResponse)
def stop_local_runtime(request: LocalRuntimeActionRequest) -> LocalRuntimeActionResponse:
    try:
        result = _runtime_manager().terminate_process_tree("explicit local operator stop")
    except Exception as exc:
        raise _runtime_action_error(exc) from exc
    return LocalRuntimeActionResponse(action="stop", requested_by=request.requested_by, result=result)


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


@router.get("/checkpoint-watchdog", response_model=LocalCheckpointWatchdogReport)
def get_local_checkpoint_watchdog() -> LocalCheckpointWatchdogReport:
    return LocalCheckpointWatchdogService().report()


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
