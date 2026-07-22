import asyncio
import logging
import socket
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.router import api_router
from backend.app.core.config import get_settings
from backend.app.core.logging import configure_logging
from backend.app.db.session import SessionLocal
from backend.app.services.comfy.runtime_manager import PinnedComfyRuntimeManager
from backend.app.services.queue.live_worker import LiveComfyQueueWorker


logger = logging.getLogger(__name__)


async def _run_local_queue_worker(settings) -> None:
    worker = LiveComfyQueueWorker(
        worker_id=f"cineforge-local-{socket.gethostname().lower()}",
        settings=settings,
    )
    while True:
        try:
            with SessionLocal() as db:
                result = await worker.run_once(db)
            if result.state in {"idle", "disabled"}:
                await asyncio.sleep(settings.comfyui_progress_poll_interval_sec)
            else:
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Local ComfyUI queue worker iteration failed")
            await asyncio.sleep(settings.comfyui_progress_poll_interval_sec)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        worker_task = None
        managed_runtime_started = False
        runtime_manager = PinnedComfyRuntimeManager(settings)
        if settings.comfyui_autostart_enabled:
            try:
                start_result = await asyncio.to_thread(runtime_manager.start, automatic=True)
                managed_runtime_started = bool(start_result.get("started"))
            except Exception:
                logger.exception("Explicitly enabled managed ComfyUI auto-start failed")
        if settings.queue_worker_enabled:
            worker_task = asyncio.create_task(
                _run_local_queue_worker(settings),
                name="cineforge-local-comfy-queue-worker",
            )
        try:
            yield
        finally:
            if worker_task is not None:
                worker_task.cancel()
                with suppress(asyncio.CancelledError):
                    await worker_task
            if managed_runtime_started:
                try:
                    await asyncio.to_thread(runtime_manager.terminate_process_tree, "CineForge shutdown")
                except Exception:
                    logger.exception("Owned ComfyUI process did not stop cleanly")

    app = FastAPI(
        title="CineForge Backend",
        version="0.1.0",
        description="Deterministic local AI video orchestration backend.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    return app


app = create_app()

