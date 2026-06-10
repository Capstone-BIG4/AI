from __future__ import annotations

import subprocess
import time

from backend.app.core.paths import ROOT
from backend.app.core.settings import load_runtime_env, redact_secrets
from backend.app.pipeline.steps import GPU_STEPS, STANDARD_STAGES, PipelineStep
from backend.app.services.results import current_results
from backend.app.state.jobs import job_store


def execute_command(job_id: str, step: PipelineStep) -> None:
    env, secrets = load_runtime_env()
    job_store.update(job_id, status="running", stage=step.name, progress=step.progress)
    job_store.append_log(job_id, "$ " + " ".join(step.command))
    proc = subprocess.run(
        step.command,
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=step.timeout,
        check=False,
    )
    if proc.stdout:
        job_store.append_log(job_id, redact_secrets(proc.stdout, secrets))
    if proc.stderr:
        job_store.append_log(job_id, redact_secrets(proc.stderr, secrets))
    if proc.returncode != 0:
        raise RuntimeError(f"{step.name} failed with exit code {proc.returncode}")


def execute_standard_pipeline(job_id: str) -> None:
    for stage in STANDARD_STAGES:
        job_store.update(job_id, status="running", stage=stage.name, progress=stage.progress)
        job_store.append_log(job_id, f"completed standard stage: {stage.name}")
        time.sleep(0.25)
    job_store.update(job_id, status="completed", stage="completed", progress=100, results=current_results())


def execute_gpu_pipeline(job_id: str) -> None:
    for step in GPU_STEPS:
        execute_command(job_id, step)
    job_store.update(job_id, status="completed", stage="completed", progress=100, results=current_results())
