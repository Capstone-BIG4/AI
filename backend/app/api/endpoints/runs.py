from __future__ import annotations

from fastapi import APIRouter

from backend.app.schemas.jobs import RunRequest, RunResponse
from backend.app.services.pipeline_runner import start_job


router = APIRouter()


@router.post("/run", response_model=RunResponse)
def run_pipeline(request: RunRequest) -> RunResponse:
    job_id = start_job(request.mode)
    return RunResponse(jobId=job_id, mode=request.mode, statusUrl=f"/api/jobs/{job_id}")
