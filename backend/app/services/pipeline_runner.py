from __future__ import annotations

import threading

from backend.app.pipeline.executor import execute_gpu_pipeline, execute_standard_pipeline
from backend.app.schemas.jobs import RunMode
from backend.app.services.results import current_results
from backend.app.state.jobs import job_store


def run_job(job_id: str, mode: RunMode) -> None:
    try:
        if mode == "gpu":
            execute_gpu_pipeline(job_id)
        else:
            execute_standard_pipeline(job_id)
    except Exception as exc:
        job_store.append_log(job_id, str(exc))
        job_store.update(job_id, status="failed", stage="failed", progress=100, error=str(exc), results=current_results())


def start_job(mode: RunMode) -> str:
    job_id = job_store.create(mode)
    thread = threading.Thread(target=run_job, args=(job_id, mode), daemon=True)
    thread.start()
    return job_id
