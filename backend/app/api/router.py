from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.endpoints import health, jobs, results, runs, uploads


api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(results.router)
api_router.include_router(uploads.router)
api_router.include_router(runs.router)
api_router.include_router(jobs.router)
