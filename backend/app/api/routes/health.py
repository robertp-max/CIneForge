from fastapi import APIRouter, Response, status

from backend.app.core.config import get_settings
from backend.app.services.comfy.client import ComfyUIClient
from backend.app.services.ffmpeg.service import FFmpegService
from backend.app.services.telemetry.gpu import GPUTelemetryService


router = APIRouter(tags=["health"])
CURRENT_PHASE = "Phase 2 controlled ComfyUI submission backend capability"


@router.get("/")
def root_status() -> dict:
    return {
        "app": "CineForge",
        "status": "ok",
        "message": "CineForge backend is running.",
        "docs_url": "/docs",
        "frontend_dev_url": "http://localhost:5173",
        "generation_enabled": False,
        "prompt_submission_publicly_accessible": False,
        "current_phase": CURRENT_PHASE,
    }


@router.get("/favicon.ico", status_code=status.HTTP_204_NO_CONTENT)
def favicon() -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@router.get("/runtime/status")
async def runtime_status() -> dict:
    settings = get_settings()
    comfy_status = await health_comfy()
    object_info = {
        "status": "not_checked",
        "available": False,
        "class_count": None,
        "error": None,
    }

    async with ComfyUIClient(str(settings.comfyui_base_url)) as client:
        try:
            object_info_payload = await client.get_object_info()
            object_info = {
                "status": "ok",
                "available": True,
                "class_count": len(object_info_payload),
                "error": None,
            }
        except Exception as exc:
            object_info = {
                "status": "unavailable",
                "available": False,
                "class_count": None,
                "error": str(exc),
            }

    return {
        "status": "ok" if comfy_status.get("status") == "ok" else "degraded",
        "environment": settings.env,
        "current_phase": CURRENT_PHASE,
        "comfyui": comfy_status,
        "object_info": object_info,
        "gpu": health_gpu(),
        "ffmpeg": health_ffmpeg(),
        "queue": {
            "worker_enabled": settings.queue_worker_enabled,
            "submission_enabled": False,
            "controlled_submission_enabled": True,
            "public_submission_enabled": False,
            "supported_states": [
                "pending",
                "reserved",
                "validating",
                "submitted",
                "running",
                "collecting_outputs",
                "complete",
                "validation_failed",
                "comfy_rejected",
                "runtime_failed",
                "timeout",
                "interrupted",
                "oom",
                "postprocess_failed",
                "canceled",
            ],
        },
        "disabled_actions": {
            "public_submit_prompt": "disabled",
            "websocket_monitor": "disabled_until_future_phase",
            "output_collection": "disabled_until_future_phase",
            "ffmpeg_assembly": "disabled_until_future_phase",
        },
    }

