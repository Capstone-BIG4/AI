from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.state.jobs import job_store


router = APIRouter()


@router.get("/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    try:
        return job_store.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
