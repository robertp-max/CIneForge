from fastapi import APIRouter

from backend.app.core.config import get_settings
from backend.app.services.comfy.client import ComfyUIClient
from backend.app.services.ffmpeg.service import FFmpegService
from backend.app.services.telemetry.gpu import GPUTelemetryService


router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "env": settings.env,
        "queue_worker_enabled": settings.queue_worker_enabled,
        "autonomy_mode": settings.autonomy_mode,
        "runtime_isolation": "comfyui_external_http_only",
    }


@router.get("/health/comfy")
async def health_comfy() -> dict:
    async with ComfyUIClient(str(get_settings().comfyui_base_url)) as client:
        return await client.health()


@router.get("/health/gpu")
def health_gpu() -> dict:
    return GPUTelemetryService().health()


@router.get("/health/ffmpeg")
def health_ffmpeg() -> dict:
    return FFmpegService().health()

