from __future__ import annotations

from fastapi import APIRouter

from backend.app.services.results import current_results


router = APIRouter()


@router.get("/results")
def results() -> dict:
    return current_results()
