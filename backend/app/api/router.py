from fastapi import APIRouter

from backend.app.api.routes import campaigns, health, jobs, projects


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(projects.router)
api_router.include_router(campaigns.router)
api_router.include_router(jobs.router)

