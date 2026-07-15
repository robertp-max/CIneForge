from fastapi import APIRouter

from backend.app.api.routes import (
    assets,
    campaigns,
    health,
    jobs,
    local_archetypes,
    local_jobs,
    local_post_production,
    local_presets,
    local_runtime,
    orchestration_runs,
    projects,
    production,
    proposal_review,
    providers,
    runtime_catalog,
    storyboard,
    storyboard_crud,
    storyboard_settings,
    voices,
)


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(storyboard_settings.router)
api_router.include_router(projects.router)
api_router.include_router(production.router)
api_router.include_router(campaigns.router)
api_router.include_router(jobs.router)
api_router.include_router(local_archetypes.router)
api_router.include_router(local_jobs.router)
api_router.include_router(local_post_production.router)
api_router.include_router(local_presets.router)
api_router.include_router(local_runtime.router)
api_router.include_router(runtime_catalog.router)
api_router.include_router(providers.router)
api_router.include_router(assets.router)
api_router.include_router(voices.router)
api_router.include_router(orchestration_runs.router)
api_router.include_router(proposal_review.router)
api_router.include_router(storyboard_crud.router)
api_router.include_router(storyboard.router)
