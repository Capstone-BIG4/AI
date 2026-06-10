from __future__ import annotations

import shutil
import subprocess

from backend.app.core.paths import ROOT


def gpu_status() -> dict:
    if not shutil.which("nvidia-smi"):
        return {"available": False, "name": None}
    proc = subprocess.run(
        ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return {"available": False, "name": None}
    names = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return {"available": bool(names), "name": names[0] if names else None}
