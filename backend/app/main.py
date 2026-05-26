from fastapi import FastAPI

from backend.app.api.router import api_router
from backend.app.core.config import get_settings
from backend.app.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title="CineForge Backend",
        version="0.1.0",
        description="Deterministic local AI video orchestration backend.",
    )
    app.include_router(api_router)
    return app


app = create_app()

