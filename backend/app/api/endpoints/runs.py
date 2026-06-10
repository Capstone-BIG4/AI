from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.schemas.jobs import RunRequest, RunResponse
from backend.app.services.uploads import required_inputs_ready
from backend.app.services.pipeline_runner import start_job


router = APIRouter()


@router.post("/run", response_model=RunResponse)
def run_pipeline(request: RunRequest) -> RunResponse:
    return create_run(request)


@router.post("/runs", response_model=RunResponse)
def create_run(request: RunRequest) -> RunResponse:
    if not required_inputs_ready():
        raise HTTPException(status_code=400, detail="all five required photos must be uploaded first")
    job_id = start_job(request.mode)
    return RunResponse(jobId=job_id, mode=request.mode, statusUrl=f"/api/jobs/{job_id}")
