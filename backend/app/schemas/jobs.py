from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


RunMode = Literal["standard", "gpu"]
JobStatus = Literal["queued", "running", "completed", "failed"]


class RunRequest(BaseModel):
    mode: RunMode = "standard"


class RunResponse(BaseModel):
    job_id: str = Field(alias="jobId")
    mode: RunMode
    status_url: str = Field(alias="statusUrl")


class JobRecord(BaseModel):
    id: str
    mode: RunMode
    status: JobStatus
    stage: str
    progress: int
    logs: list[str]
    created_at: float = Field(alias="createdAt")
    updated_at: float = Field(alias="updatedAt")
    results: dict | None = None
    error: str | None = None
