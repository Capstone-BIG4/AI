from __future__ import annotations

from fastapi import APIRouter

from backend.app.services.gpu import gpu_status
from backend.app.services.results import current_results


router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "virtual-fitting-studio",
        "gpu": gpu_status(),
        "resultsReady": current_results()["ready"],
    }
