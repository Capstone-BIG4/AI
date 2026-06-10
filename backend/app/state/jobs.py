from __future__ import annotations

import threading
import time
import uuid

from backend.app.schemas.jobs import RunMode


class JobStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, dict] = {}

    def create(self, mode: RunMode) -> str:
        job_id = uuid.uuid4().hex[:12]
        now = time.time()
        with self._lock:
            self._jobs[job_id] = {
                "id": job_id,
                "mode": mode,
                "status": "queued",
                "stage": "queued",
                "progress": 0,
                "logs": [],
                "createdAt": now,
                "updatedAt": now,
                "results": None,
            }
        return job_id

    def update(self, job_id: str, **updates) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.update(updates)
            job["updatedAt"] = time.time()

    def append_log(self, job_id: str, message: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            logs = job.setdefault("logs", [])
            logs.append(message[-2400:])
            del logs[:-12]
            job["updatedAt"] = time.time()

    def get(self, job_id: str) -> dict:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            return dict(job)


job_store = JobStore()
